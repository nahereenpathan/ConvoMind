"""SMTP Email Provider implementation."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from typing import Optional

from app.core.config import settings
from app.services.email.base import BaseEmailProvider, EmailProviderError

logger = logging.getLogger(__name__)


class SmtpEmailProvider(BaseEmailProvider):
    """Production SMTP Email provider with TLS/SSL support and robust error handling."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: Optional[bool] = None,
    ):
        self.host = host or settings.SMTP_HOST
        self.port = port or settings.SMTP_PORT
        self.user = user or settings.SMTP_USER
        self.password = password or settings.SMTP_PASSWORD
        self.from_email = from_email or settings.SMTP_FROM_EMAIL or self.user or "noreply@convomind.ai"
        self.use_tls = use_tls if use_tls is not None else settings.SMTP_USE_TLS

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP server, raising EmailProviderError on failure."""
        if not self.host or (self.host in ("localhost", "127.0.0.1", "") and not self.user):
            raise EmailProviderError("SMTP server host is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD in .env.")

        sender = self.from_email or self.user or "noreply@convomind.ai"
        from_name = getattr(settings, "SMTP_FROM_NAME", "ConvoMind")
        formatted_from = f"{from_name} <{sender}>" if from_name else sender
        domain = to_email.split("@")[-1] if "@" in to_email else "unknown"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formatted_from
            msg["To"] = to_email

            part1 = MIMEText(body_text, "plain", "utf-8")
            msg.attach(part1)

            if body_html:
                part2 = MIMEText(body_html, "html", "utf-8")
                msg.attach(part2)

            # SSL connection for port 465, TLS for 587/25
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=12)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=12)

            with server:
                if self.port != 465 and self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(sender, [to_email], msg.as_string())

            logger.info(f"[SmtpEmailProvider] Delivered message to recipient domain '{domain}'.")
            return True

        except smtplib.SMTPAuthenticationError as auth_err:
            logger.error(f"[SmtpEmailProvider] SMTP authentication failed for user: {self.user}")
            raise EmailProviderError("SMTP authentication failed. Please verify SMTP_USER and SMTP_PASSWORD.")
        except smtplib.SMTPException as smtp_err:
            logger.error(f"[SmtpEmailProvider] SMTP server rejected message to domain '{domain}': {smtp_err}")
            raise EmailProviderError(f"SMTP server error: {smtp_err}")
        except Exception as exc:
            logger.error(f"[SmtpEmailProvider] SMTP connection failure to {self.host}:{self.port}: {exc}")
            raise EmailProviderError(f"SMTP connection failure ({exc})")

