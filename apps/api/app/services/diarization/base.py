"""Abstract Base Class and domain models for Speaker Diarization providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


class DiarizationError(Exception):
    """Base exception for speaker diarization failures."""
    pass


class DiarizationTransientError(DiarizationError):
    """Transient error suitable for retry (e.g. rate limit, temporary timeout)."""
    pass


class DiarizationPermanentError(DiarizationError):
    """Permanent error where retrying will not help (e.g. invalid audio format, corrupt file)."""
    pass


@dataclass
class SpeakerInterval:
    """Individual speaker interval/segment returned by diarization provider."""

    speaker_label: str
    start_time: float
    end_time: float
    confidence: Optional[float] = 1.0


@dataclass
class DiarizationResult:
    """Consolidated response from speaker diarization process."""

    segments: List[SpeakerInterval] = field(default_factory=list)
    num_speakers_detected: int = 0
    duration_seconds: float = 0.0
    provider_name: str = "unknown"


class BaseDiarizationProvider(ABC):
    """Abstract base class defining speaker diarization contract."""

    @abstractmethod
    async def diarize(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None,
    ) -> DiarizationResult:
        """Process an audio file and return identified speaker intervals.

        Args:
            audio_path: Absolute filesystem path to normalized WAV audio.
            num_speakers: Optional hint for expected number of speakers.

        Returns:
            DiarizationResult containing identified speaker intervals and metadata.

        Raises:
            DiarizationTransientError: On recoverable temporary errors.
            DiarizationPermanentError: On unrecoverable input or configuration errors.
        """
        pass
