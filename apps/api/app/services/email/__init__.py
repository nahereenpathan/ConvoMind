"""Email provider package exports."""

from app.services.email.base import BaseEmailProvider, EmailProviderError
from app.services.email.factory import get_email_provider
from app.services.email.mock_provider import MockEmailProvider, get_mock_email_provider
from app.services.email.smtp_provider import SmtpEmailProvider
from app.services.email.templates import render_email_template
from app.services.email.dispatch import EmailDispatchService

__all__ = [
    "BaseEmailProvider",
    "EmailProviderError",
    "MockEmailProvider",
    "SmtpEmailProvider",
    "get_email_provider",
    "get_mock_email_provider",
    "render_email_template",
    "EmailDispatchService",
]
