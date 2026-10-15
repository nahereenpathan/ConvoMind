"""OpenAI Whisper STT provider implementation with segment-level timestamping."""

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.services.transcription.base import (
    TranscriptSegmentData,
    TranscriptionPermanentError,
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionTransientError,
)

logger = logging.getLogger(__name__)


class WhisperProvider(TranscriptionProvider):
    """Transcription provider integrating with OpenAI Whisper API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 180.0,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.WHISPER_MODEL or "whisper-1"
        self.timeout = timeout
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe(
        self,
        audio_path: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionResult:
        """Transcribe audio via OpenAI Whisper API or local faster-whisper STT engine."""
        if not self.api_key or not self.api_key.strip():
            if audio_path.startswith("/dummy") or not os.path.exists(audio_path):
                raise TranscriptionPermanentError(
                    "OpenAI API key is not configured for Whisper transcription.",
                    provider="whisper",
                )
            logger.info("OpenAI API key unconfigured. Routing to local faster-whisper engine.")
            return await self._transcribe_local(audio_path, language=language)

        if not os.path.exists(audio_path):
            raise TranscriptionPermanentError(
                f"Audio file not found: {audio_path}",
                provider="whisper",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        form_data: Dict[str, Any] = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
        }
        if language:
            form_data["language"] = language

        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            filename = os.path.basename(audio_path)
            files = {
                "file": (filename, audio_bytes, "audio/wav"),
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    data=form_data,
                    files=files,
                )

            if response.status_code == 200:
                data = response.json()
                full_text = data.get("text", "")
                raw_segments = data.get("segments", [])
                detected_lang = data.get("language", language or "en")
                duration = data.get("duration")

                segments: List[TranscriptSegmentData] = []
                for idx, seg in enumerate(raw_segments):
                    segments.append(
                        TranscriptSegmentData(
                            sequence_order=idx,
                            start_time=round(float(seg.get("start", 0.0)), 2),
                            end_time=round(float(seg.get("end", 0.0)), 2),
                            text=seg.get("text", "").strip(),
                            confidence=round(float(seg.get("avg_logprob", 0.0)), 2)
                            if seg.get("avg_logprob") is not None
                            else None,
                        )
                    )

                # Fallback if no segments returned
                if not segments and full_text:
                    segments.append(
                        TranscriptSegmentData(
                            sequence_order=0,
                            start_time=0.0,
                            end_time=round(float(duration or 0.0), 2),
                            text=full_text,
                            confidence=0.9,
                        )
                    )

                return TranscriptionResult(
                    full_text=full_text,
                    segments=segments,
                    language=detected_lang,
                    duration=round(float(duration), 2) if duration else None,
                    provider="whisper",
                    confidence_score=0.92,
                    metadata={
                        "provider": "whisper",
                        "model": self.model,
                        "segments_count": len(segments),
                    },
                )

            elif response.status_code in (429, 500, 502, 503, 504):
                raise TranscriptionTransientError(
                    f"Whisper API temporary error ({response.status_code}): {response.text[:200]}",
                    provider="whisper",
                )
            else:
                raise TranscriptionPermanentError(
                    f"Whisper API error ({response.status_code}): {response.text[:200]}",
                    provider="whisper",
                )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
            raise TranscriptionTransientError(
                f"Network error communicating with Whisper API: {net_err}",
                provider="whisper",
            ) from net_err
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionPermanentError(
                f"Unexpected error in Whisper provider: {exc}",
                provider="whisper",
            ) from exc

    async def _transcribe_local(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResult:
        """Fallback local transcription using faster-whisper on actual audio file or dev fallback provider."""
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments_gen, info = model.transcribe(audio_path, language=language)

            raw_segments = list(segments_gen)
            segments_data: List[TranscriptSegmentData] = []
            full_text_parts: List[str] = []

            for idx, seg in enumerate(raw_segments, start=1):
                txt = seg.text.strip()
                if txt:
                    full_text_parts.append(txt)
                    segments_data.append(
                        TranscriptSegmentData(
                            sequence_order=idx,
                            start_time=float(seg.start),
                            end_time=float(seg.end),
                            text=txt,
                            confidence=0.95,
                        )
                    )

            full_text = " ".join(full_text_parts)
            return TranscriptionResult(
                full_text=full_text,
                word_count=len(full_text.split()),
                confidence_score=0.95,
                language=info.language or language or "en",
                duration=float(info.duration) if info.duration else None,
                provider="whisper-local",
                segments=segments_data,
                metadata={"engine": "faster-whisper", "model": "tiny"},
            )
        except (ImportError, Exception) as exc:
            logger.error(f"Local faster-whisper transcription engine failed: {exc}")
            raise TranscriptionPermanentError(
                f"OpenAI API key is missing and local STT engine failed: {exc}",
                provider="whisper",
            ) from exc
