"""Factory for EmailProvider instantiation."""

import logging
from app.core.config import settings
from app.services.email.base import BaseEmailProvider
from app.services.email.mock_provider import get_mock_email_provider
from app.services.email.smtp_provider import SmtpEmailProvider

logger = logging.getLogger(__name__)


def get_email_provider() -> BaseEmailProvider:
    """Instantiate active EmailProvider based on application settings."""
    provider_type = (settings.EMAIL_PROVIDER or "mock").strip().lower()

    if provider_type == "smtp":
        logger.info("Initializing SmtpEmailProvider")
        return SmtpEmailProvider()
    else:
        logger.info("Initializing MockEmailProvider")
        return get_mock_email_provider()
