"""Base contracts, data transfer objects, and exceptions for STT providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class TranscriptionError(Exception):
    """Base exception for transcription failures."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message)
        self.provider = provider


class TranscriptionTransientError(TranscriptionError):
    """Temporary failure suitable for Celery retry (network, rate limit, provider 5xx)."""

    pass


class TranscriptionPermanentError(TranscriptionError):
    """Non-recoverable failure that should not be retried (invalid format, auth error)."""

    pass


@dataclass
class TranscriptSegmentData:
    """Standardized representation of a single timestamped speech segment."""

    sequence_order: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    speaker_label: Optional[str] = None


@dataclass
class TranscriptionResult:
    """Standardized result returned by all transcription providers."""

    full_text: str
    segments: List[TranscriptSegmentData]
    language: str = "en"
    duration: Optional[float] = None
    provider: str = "unknown"
    word_count: int = 0
    confidence_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.word_count and self.full_text:
            self.word_count = len(self.full_text.split())


class TranscriptionProvider(ABC):
    """Abstract interface for pluggable speech-to-text providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file into text with timestamped segments.

        Args:
            audio_path: Local filesystem path to the normalized WAV audio file.
            options: Optional provider-specific configuration (language, prompt, etc.).

        Returns:
            TranscriptionResult containing full text and timestamped segments.

        Raises:
            TranscriptionTransientError: For transient/retriable errors.
            TranscriptionPermanentError: For permanent/unrecoverable errors.
        """
        pass
