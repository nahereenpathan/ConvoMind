"""Mock transcription provider for local development, CI pipelines, and automated tests."""

import logging
import os
from typing import Any, Dict, List, Optional

from app.services.ffmpeg_service import get_ffmpeg_service
from app.services.transcription.base import (
    TranscriptSegmentData,
    TranscriptionPermanentError,
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionTransientError,
)

logger = logging.getLogger(__name__)

DEFAULT_MOCK_UTTERANCES = [
    "Audio recording session started.",
    "Discussed agenda topics and reviewed progress.",
    "Identified next steps and action items.",
    "Meeting concluded successfully.",
]


class MockTranscriptionProvider(TranscriptionProvider):
    """Simulated STT provider that produces deterministic, realistic transcripts."""

    def __init__(
        self,
        simulate_transient_error: bool = False,
        simulate_permanent_error: bool = False,
        fixed_language: str = "en",
    ):
        self.simulate_transient_error = simulate_transient_error
        self.simulate_permanent_error = simulate_permanent_error
        self.fixed_language = fixed_language

    async def transcribe(
        self,
        audio_path: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionResult:
        """Simulate transcribing an audio file."""
        options = options or {}

        # Allow test overrides via options
        if options.get("simulate_transient_error") or self.simulate_transient_error:
            raise TranscriptionTransientError(
                "Mock provider simulated transient rate limit error (429)",
                provider="mock",
            )

        if options.get("simulate_permanent_error") or self.simulate_permanent_error:
            raise TranscriptionPermanentError(
                "Mock provider simulated permanent invalid format error (400)",
                provider="mock",
            )

        if not os.path.exists(audio_path):
            raise TranscriptionPermanentError(
                f"Audio file does not exist: {audio_path}",
                provider="mock",
            )

        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            raise TranscriptionPermanentError(
                "Audio file is empty",
                provider="mock",
            )

        # Estimate duration using FFprobe or calculate from WAV file size (16kHz 16-bit mono = 32000 bytes/sec)
        ffmpeg_service = get_ffmpeg_service()
        probe_data = ffmpeg_service.probe_media(audio_path)
        probed_duration = probe_data.get("duration_seconds")

        if probed_duration and probed_duration > 0:
            total_duration = float(probed_duration)
        else:
            # Fallback estimation based on 16kHz mono WAV size
            total_duration = max(5.0, round(file_size / 32000.0, 2))

        # Generate realistic segments bounded by total duration
        utterances = options.get("utterances")
        if not utterances:
            title = options.get("meeting_title", "").strip()
            desc = options.get("meeting_description", "").strip()

            if title or desc:
                full_desc_context = f"{title}. {desc}".strip()
                # Split description into clean topic sentences or generate grounded sentences
                desc_sentences = [s.strip() for s in desc.split(".") if s.strip()]
                if desc_sentences:
                    utterances = [f"Welcome to our session on {title}."]
                    for sentence in desc_sentences:
                        utterances.append(f"We need to discuss {sentence.lower() if not sentence.startswith('http') else sentence}.")
                    utterances.append("Let's summarize our action items and decisions before concluding.")
                else:
                    utterances = [
                        f"Welcome everyone to our session on {title}.",
                        f"Today we are reviewing key initiatives regarding {title}.",
                        "Let's outline our primary goals, schedule, and team commitments.",
                        "We need to ensure all deliverables are completed on schedule.",
                        f"Thank you everyone for joining this discussion on {title}.",
                    ]
            else:
                utterances = DEFAULT_MOCK_UTTERANCES

        num_segments = min(len(utterances), max(3, int(total_duration // 3)))
        segment_duration = total_duration / max(1, num_segments)

        segments: List[TranscriptSegmentData] = []
        full_text_parts: List[str] = []

        current_time = 0.0
        for idx in range(num_segments):
            text = utterances[idx % len(utterances)]
            start_time = round(current_time, 2)
            end_time = round(min(total_duration, current_time + segment_duration), 2)

            segments.append(
                TranscriptSegmentData(
                    sequence_order=idx,
                    start_time=start_time,
                    end_time=end_time,
                    text=text,
                    confidence=0.96,
                    speaker_label=None,
                )
            )
            full_text_parts.append(text)
            current_time = end_time

        full_text = " ".join(full_text_parts)

        return TranscriptionResult(
            full_text=full_text,
            segments=segments,
            language=self.fixed_language,
            duration=round(total_duration, 2),
            provider="mock",
            confidence_score=0.96,
            metadata={
                "provider": "mock",
                "model": "mock-transcriber-v1",
                "audio_size_bytes": file_size,
                "segments_count": len(segments),
            },
        )
