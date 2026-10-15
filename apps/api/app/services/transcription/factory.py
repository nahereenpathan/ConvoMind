"""Factory for resolving the configured transcription provider."""

import logging
from typing import Optional

from app.core.config import settings
from app.services.transcription.base import TranscriptionProvider
from app.services.transcription.mock_provider import MockTranscriptionProvider
from app.services.transcription.whisper_provider import WhisperProvider

logger = logging.getLogger(__name__)

_active_provider: Optional[TranscriptionProvider] = None


def get_transcription_provider(provider_override: Optional[str] = None) -> TranscriptionProvider:
    """Resolve and return the appropriate TranscriptionProvider instance.

    Args:
        provider_override: Optional explicit provider name ('mock', 'whisper', etc.).
    """
    global _active_provider
    import os
    if os.getenv("TESTING") and not provider_override:
        provider_name = "mock"
    else:
        provider_name = (provider_override or settings.TRANSCRIPTION_PROVIDER or "whisper").lower().strip()

    if provider_override is not None:
        if provider_name == "whisper":
            return WhisperProvider()
        return MockTranscriptionProvider()

    expected_class = WhisperProvider if provider_name == "whisper" else MockTranscriptionProvider
    if _active_provider is None or not isinstance(_active_provider, expected_class):
        logger.info(f"Initializing transcription provider: {provider_name}")
        if provider_name == "whisper":
            _active_provider = WhisperProvider()
        elif provider_name == "mock":
            if settings.ENVIRONMENT == "production":
                raise TranscriptionPermanentError(
                    "Mock transcription provider is disabled in production environment.",
                    provider="factory",
                )
            _active_provider = MockTranscriptionProvider()
        else:
            raise TranscriptionPermanentError(
                f"Unknown TRANSCRIPTION_PROVIDER '{provider_name}'. Real speech-to-text requires 'whisper'.",
                provider="factory",
            )

    return _active_provider



def reset_transcription_provider() -> None:
    """Reset the cached singleton provider (useful in tests)."""
    global _active_provider
    _active_provider = None
