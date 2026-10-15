"""Abstract base class and contract for email delivery providers."""

from abc import ABC, abstractmethod
from typing import Optional


class EmailProviderError(Exception):
    """Base exception for email provider errors."""
    pass


class BaseEmailProvider(ABC):
    """Abstract interface for sending email notifications."""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Send an email message.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            body_text: Plain text email body.
            body_html: Optional HTML formatted body.

        Returns:
            True if email dispatched successfully, False otherwise.
        """
        pass
