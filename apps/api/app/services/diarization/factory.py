"""Factory function for instantiating configured DiarizationProvider."""

import logging

from app.core.config import settings
from app.services.diarization.base import BaseDiarizationProvider
from app.services.diarization.mock_provider import MockDiarizationProvider
from app.services.diarization.pyannote_provider import PyannoteDiarizationProvider

logger = logging.getLogger(__name__)


def get_diarization_provider() -> BaseDiarizationProvider:
    """Instantiate and return the active DiarizationProvider based on application settings."""
    provider_type = (settings.DIARIZATION_PROVIDER or "mock").strip().lower()

    if provider_type == "pyannote":
        logger.info("Initializing PyannoteDiarizationProvider")
        return PyannoteDiarizationProvider()
    else:
        logger.info("Initializing MockDiarizationProvider")
        return MockDiarizationProvider()
