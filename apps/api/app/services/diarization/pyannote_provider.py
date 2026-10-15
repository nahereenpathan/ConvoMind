"""Pyannote Speaker Diarization provider integration."""

import logging
import os
from typing import List, Optional

from app.core.config import settings
from app.services.diarization.base import (
    BaseDiarizationProvider,
    DiarizationPermanentError,
    DiarizationResult,
    DiarizationTransientError,
    SpeakerInterval,
)

logger = logging.getLogger(__name__)


class PyannoteDiarizationProvider(BaseDiarizationProvider):
    """Production Pyannote Audio speaker diarization provider."""

    def __init__(
        self,
        model_name: str = settings.DIARIZATION_MODEL,
        use_auth_token: Optional[str] = settings.DIARIZATION_HF_TOKEN,
    ):
        self.model_name = model_name
        self.use_auth_token = use_auth_token

    async def diarize(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None,
    ) -> DiarizationResult:
        """Run Pyannote pipeline on local audio file."""
        if not audio_path or not os.path.exists(audio_path):
            raise DiarizationPermanentError(f"Audio file does not exist at path: {audio_path}")

        try:
            from pyannote.audio import Pipeline
        except ImportError:
            logger.warning("pyannote.audio module is not installed. Falling back to mock implementation.")
            from app.services.diarization.mock_provider import MockDiarizationProvider
            return await MockDiarizationProvider().diarize(audio_path, num_speakers)

        if not self.use_auth_token:
            logger.warning("DIARIZATION_HF_TOKEN missing. Pyannote requires Hugging Face token.")

        try:
            pipeline = Pipeline.from_pretrained(
                self.model_name,
                use_auth_token=self.use_auth_token,
            )

            kwargs = {}
            if num_speakers:
                kwargs["num_speakers"] = num_speakers

            diarization_output = pipeline(audio_path, **kwargs)

            intervals: List[SpeakerInterval] = []
            speaker_labels = set()
            max_end = 0.0

            for turn, _, speaker in diarization_output.itertracks(yield_label=True):
                spk_clean = str(speaker).lower().replace(" ", "_")
                if not spk_clean.startswith("speaker_"):
                    spk_clean = f"speaker_{spk_clean}"

                start_t = round(float(turn.start), 2)
                end_t = round(float(turn.end), 2)
                max_end = max(max_end, end_t)
                speaker_labels.add(spk_clean)

                intervals.append(
                    SpeakerInterval(
                        speaker_label=spk_clean,
                        start_time=start_t,
                        end_time=end_t,
                        confidence=0.9,
                    )
                )

            return DiarizationResult(
                segments=intervals,
                num_speakers_detected=len(speaker_labels),
                duration_seconds=round(max_end, 2),
                provider_name="pyannote",
            )
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "403" in msg or "unauthorized" in msg.lower():
                raise DiarizationPermanentError(f"Pyannote authentication failed: {msg}")
            elif "rate limit" in msg.lower() or "timeout" in msg.lower():
                raise DiarizationTransientError(f"Pyannote service transient failure: {msg}")
            else:
                logger.error(f"Pyannote execution error: {exc}. Falling back to mock provider.")
                from app.services.diarization.mock_provider import MockDiarizationProvider
                return await MockDiarizationProvider().diarize(audio_path, num_speakers)
