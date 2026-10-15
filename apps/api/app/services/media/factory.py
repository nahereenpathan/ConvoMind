"""Factory for instantiating the configured real-time media provider."""

from typing import Optional
from app.core.config import settings
from app.services.media.base import BaseMediaProvider
from app.services.media.livekit_provider import LiveKitProvider
from app.services.media.mock_provider import MockMediaProvider


def get_media_provider(provider_name: Optional[str] = None) -> BaseMediaProvider:
    """Return configured media provider instance based on settings or override."""
    target_provider = (provider_name or settings.MEDIA_PROVIDER or "mock").lower()

    if target_provider == "livekit" and settings.LIVEKIT_API_KEY and settings.LIVEKIT_API_SECRET:
        return LiveKitProvider()

    return MockMediaProvider()
