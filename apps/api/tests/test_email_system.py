"""Automated test suite for ConvoMind Email & SMTP Notification System."""

import pytest
import uuid
from datetime import datetime, timezone

from app.models.email_log import EmailLog
from app.models.enums import EmailStatus
from app.services.email.base import EmailProviderError
from app.services.email.smtp_provider import SmtpEmailProvider
from app.services.email.templates import render_email_template
from app.services.email.dispatch import EmailDispatchService


def test_render_email_templates_all_event_types():
    """Verify HTML and plain text generation for all 9 email event types."""
    event_types = [
        "meeting_invitation",
        "meeting_reminder",
        "meeting_update",
        "meeting_cancelled",
        "post_meeting_summary",
        "ai_insights_ready",
        "recording_ready",
        "action_item_assigned",
        "follow_up_draft",
    ]

    sample_data = {
        "meeting_id": str(uuid.uuid4()),
        "meeting_title": "Q3 Strategy Review",
        "host_name": "Jane Doe",
        "scheduled_at": "2026-10-01 10:00 UTC",
        "join_url": "http://localhost:5173/meeting/123",
        "agenda": "Review Q3 goals and roadmap",
        "time_until": "1 hour",
        "change_summary": "Time shifted by 30 mins",
        "reason": "Host scheduling conflict",
        "summary": "Key discussion on roadmap execution.",
        "decisions": ["Approve budget", "Launch beta next week"],
        "duration": "45m 12s",
        "task_description": "Finalize Q3 slides",
        "assignee_name": "John Smith",
        "due_date": "2026-09-30",
        "follow_up_content": "Thank you all for attending the Q3 strategy review...",
        "recipients": ["john@example.com", "jane@example.com"],
    }

    for event in event_types:
        subject, body_text, body_html = render_email_template(event, sample_data)
        assert subject is not None and len(subject) > 0, f"Subject missing for {event}"
        assert body_text is not None and len(body_text) > 0, f"Plain text body missing for {event}"
        assert body_html is not None and len(body_html) > 0, f"HTML body missing for {event}"
        assert "ConvoMind" in body_html, f"Branding missing in HTML for {event}"
        assert "<!DOCTYPE html>" in body_html, f"DOCTYPE missing in HTML for {event}"


def test_smtp_provider_unconfigured_error():
    """Verify SmtpEmailProvider raises explicit EmailProviderError when connection fails or host is invalid."""
    provider = SmtpEmailProvider(host="invalid.smtp.local", port=587, user="user", password="pwd")
    with pytest.raises(EmailProviderError):
        import asyncio
        asyncio.run(provider.send_email(
            to_email="test@example.com",
            subject="Test",
            body_text="Test message",
        ))


def test_email_dispatch_service_idempotency():
    """Verify EmailDispatchService prevents duplicate enqueuing with identical idempotency keys."""
    from app.core.database import AsyncSessionLocal

    async def _async_test():
        async with AsyncSessionLocal() as db_session:
            test_email = f"user_{uuid.uuid4().hex[:6]}@example.com"
            idempotency_key = f"test_key:{uuid.uuid4()}"

            log1 = await EmailDispatchService.enqueue_email(
                db=db_session,
                recipient_email=test_email,
                recipient_name="Test Recipient",
                event_type="meeting_invitation",
                template_data={"meeting_title": "Test Sync"},
                idempotency_key=idempotency_key,
                check_preference=False,
            )
            assert log1 is not None
            assert log1.status == EmailStatus.QUEUED

            # Second call with same idempotency_key
            log2 = await EmailDispatchService.enqueue_email(
                db=db_session,
                recipient_email=test_email,
                recipient_name="Test Recipient",
                event_type="meeting_invitation",
                template_data={"meeting_title": "Test Sync"},
                idempotency_key=idempotency_key,
                check_preference=False,
            )
            assert log2 is not None
            assert log2.id == log1.id, "Duplicate EmailLog was created despite identical idempotency key"

    import asyncio
    asyncio.run(_async_test())
