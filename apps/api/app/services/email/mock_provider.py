"""Mock Email Provider for testing and local development."""

import logging
from typing import Dict, List, Optional
from app.services.email.base import BaseEmailProvider

logger = logging.getLogger(__name__)


class MockEmailProvider(BaseEmailProvider):
    """In-memory mock email provider recording dispatched emails for automated tests."""

    def __init__(self):
        self.sent_emails: List[Dict[str, str]] = []

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Record dispatched email message in memory."""
        record = {
            "to_email": to_email,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html or "",
        }
        self.sent_emails.append(record)
        logger.info(f"[MockEmailProvider] Sent email to={to_email} subject='{subject}'")
        return True

    def clear(self):
        """Clear sent email record buffer."""
        self.sent_emails.clear()


_mock_email_provider_instance: Optional[MockEmailProvider] = None


def get_mock_email_provider() -> MockEmailProvider:
    """Return singleton MockEmailProvider instance for assertion checks in tests."""
    global _mock_email_provider_instance
    if _mock_email_provider_instance is None:
        _mock_email_provider_instance = MockEmailProvider()
    return _mock_email_provider_instance
