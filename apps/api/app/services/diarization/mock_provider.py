"""Mock/Fake Speaker Diarization provider for testing and local development."""

import logging
import os
from typing import List, Optional

from app.services.diarization.base import (
    BaseDiarizationProvider,
    DiarizationPermanentError,
    DiarizationResult,
    SpeakerInterval,
)

logger = logging.getLogger(__name__)


class MockDiarizationProvider(BaseDiarizationProvider):
    """Deterministic mock diarization provider producing multi-speaker intervals for testing."""

    async def diarize(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None,
    ) -> DiarizationResult:
        """Simulate speaker diarization by returning structured intervals across audio timeline."""
        if not audio_path or not os.path.exists(audio_path):
            raise DiarizationPermanentError(f"Audio file does not exist at path: {audio_path}")

        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            raise DiarizationPermanentError("Audio file is empty (0 bytes).")

        # Estimate duration based on file size or fixed simulation length
        # Assuming ~32KB per second for 16kHz 16-bit mono PCM WAV
        estimated_duration = max(30.0, float(file_size) / 32000.0)

        intervals: List[SpeakerInterval] = []
        speaker_count = num_speakers or 2
        labels = [f"speaker_{i}" for i in range(speaker_count)]

        # Generate realistic alternating speaker segments (e.g. 8-15s per turn)
        chunk_duration = 10.0
        current_start = 0.0

        step_idx = 0
        while current_start < estimated_duration:
            current_end = min(current_start + chunk_duration, estimated_duration)
            spk_label = labels[step_idx % len(labels)]

            intervals.append(
                SpeakerInterval(
                    speaker_label=spk_label,
                    start_time=round(current_start, 2),
                    end_time=round(current_end, 2),
                    confidence=0.95,
                )
            )

            current_start = current_end
            step_idx += 1

        logger.info(
            f"[MockDiarizationProvider] Generated {len(intervals)} intervals "
            f"across {estimated_duration:.1f}s audio with {speaker_count} speakers."
        )

        return DiarizationResult(
            segments=intervals,
            num_speakers_detected=speaker_count,
            duration_seconds=round(estimated_duration, 2),
            provider_name="mock",
        )
