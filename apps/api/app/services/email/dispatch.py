"""Unified Email Dispatch Service for scheduling and triggering transactional and notification emails."""

from datetime import datetime, timezone
import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailLog
from app.models.enums import EmailStatus, NotificationType
from app.models.notification import NotificationPreference
from app.services.email.templates import render_email_template
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDispatchService:
    """High-level service managing email generation, preference verification, idempotency, logging, and async Celery dispatch."""

    @classmethod
    async def should_send_email_for_user(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_type: str,
    ) -> bool:
        """Check user notification preference to verify if email dispatch is allowed."""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        res = await db.execute(stmt)
        pref = res.scalar_one_or_none()

        if not pref:
            return True

        if not pref.email_enabled:
            return False

        # Map event_type to specific user notification preference flag
        if event_type == "meeting_invitation":
            return getattr(pref, "notify_on_meeting_invitation", True)
        elif event_type == "meeting_reminder":
            return getattr(pref, "notify_on_meeting_reminder", True)
        elif event_type == "meeting_update":
            return getattr(pref, "notify_on_meeting_update", True)
        elif event_type == "meeting_cancelled":
            return getattr(pref, "notify_on_meeting_cancellation", True)
        elif event_type == "post_meeting_summary":
            return pref.notify_on_meeting_complete
        elif event_type == "ai_insights_ready":
            return pref.notify_on_ai_complete
        elif event_type == "recording_ready":
            return getattr(pref, "notify_on_recording_ready", True)
        elif event_type == "action_item_assigned":
            return pref.notify_on_action_item_assigned
        elif event_type == "follow_up_draft":
            return pref.notify_on_follow_up_ready

        return True

    @classmethod
    async def enqueue_email(
        cls,
        db: AsyncSession,
        recipient_email: str,
        recipient_name: Optional[str],
        event_type: str,
        template_data: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None,
        workspace_id: Optional[uuid.UUID] = None,
        meeting_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
        check_preference: bool = True,
    ) -> Optional[EmailLog]:
        """Enqueue an email dispatch request: render template, persist EmailLog, and enqueue Celery task."""
        if not recipient_email or "@" not in recipient_email:
            logger.warning(f"[EmailDispatch] Skipped email enqueue: invalid recipient '{recipient_email}'")
            return None

        # 1. Check user preferences if user_id is supplied
        if user_id and check_preference:
            allowed = await cls.should_send_email_for_user(db, user_id, event_type)
            if not allowed:
                logger.info(f"[EmailDispatch] Skipped email for user {user_id} due to notification preferences.")
                return None

        # 2. Render email content from templates
        subject, body_text, body_html = render_email_template(event_type, template_data)

        # 3. Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = f"{event_type}:{meeting_id or 'none'}:{recipient_email}:{int(datetime.now(timezone.utc).timestamp() / 60)}"

        # 4. Check for existing EmailLog with same idempotency key
        stmt = select(EmailLog).where(EmailLog.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        existing_log = res.scalar_one_or_none()
        if existing_log:
            logger.info(f"[EmailDispatch] Duplicate email dispatch suppressed by idempotency key '{idempotency_key}'")
            return existing_log

        # 5. Create EmailLog record
        email_log = EmailLog(
            id=uuid.uuid4(),
            user_id=user_id,
            workspace_id=workspace_id,
            meeting_id=meeting_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name or recipient_email,
            subject=subject,
            event_type=event_type,
            status=EmailStatus.QUEUED,
            provider=settings.EMAIL_PROVIDER,
            attempts=0,
            idempotency_key=idempotency_key,
            body_text=body_text,
            body_html=body_html,
            queued_at=datetime.now(timezone.utc),
        )
        db.add(email_log)
        await db.commit()
        await db.refresh(email_log)

        # 6. Trigger Celery task
        try:
            from app.workers.celery_app import celery_app
            from app.workers.tasks.email_tasks import send_email_async
            inspector = celery_app.control.inspect(timeout=0.5)
            ping_res = inspector.ping() if inspector else None
            if ping_res and len(ping_res) > 0:
                send_email_async.delay(str(email_log.id))
                logger.info(f"[EmailDispatch] Enqueued Celery email task for EmailLog {email_log.id}")
            else:
                logger.info(f"[EmailDispatch] Celery broker/worker unavailable; EmailLog {email_log.id} remains QUEUED.")
        except Exception as exc:
            logger.error(f"[EmailDispatch] Failed to launch Celery task for EmailLog {email_log.id}: {exc}")
            # Even if Celery fails to enqueue, the log remains QUEUED for retry/inspect

        return email_log
