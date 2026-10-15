"""Celery worker tasks for asynchronous email dispatch and periodic reminder checks."""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models.email_log import EmailLog
from app.models.enums import EmailStatus
from app.models.meeting import Meeting, MeetingParticipant
from app.services.email import get_email_provider
from app.services.email.base import EmailProviderError
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _async_send_email(email_log_id_str: str) -> Dict[str, Any]:
    """Asynchronously execute email delivery for a given EmailLog ID."""
    try:
        log_id = uuid.UUID(email_log_id_str)
    except Exception as exc:
        logger.error(f"[EmailWorker] Invalid email_log_id format: {email_log_id_str} ({exc})")
        return {"status": "invalid_id"}

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(EmailLog).where(EmailLog.id == log_id)
            res = await session.execute(stmt)
            email_log = res.scalar_one_or_none()

            if not email_log:
                logger.error(f"[EmailWorker] EmailLog record {log_id} not found.")
                return {"status": "not_found"}

            if email_log.status == EmailStatus.SENT:
                logger.info(f"[EmailWorker] EmailLog {log_id} already marked as SENT. Idempotency skip.")
                return {"status": "already_sent"}

            email_log.status = EmailStatus.SENDING
            email_log.attempts += 1
            await session.commit()
            await session.refresh(email_log)

            provider = get_email_provider()
            try:
                # Synchronous SMTP call run inside asyncio loop or direct call if provider handles it
                if asyncio.iscoroutinefunction(provider.send_email):
                    success = await provider.send_email(
                        to_email=email_log.recipient_email,
                        subject=email_log.subject,
                        body_text=email_log.body_text or "",
                        body_html=email_log.body_html,
                    )
                else:
                    success = provider.send_email(
                        to_email=email_log.recipient_email,
                        subject=email_log.subject,
                        body_text=email_log.body_text or "",
                        body_html=email_log.body_html,
                    )

                if success:
                    email_log.status = EmailStatus.SENT
                    email_log.sent_at = datetime.now(timezone.utc)
                    email_log.last_error = None
                    await session.commit()
                    logger.info(f"[EmailWorker] EmailLog {log_id} successfully delivered to {email_log.recipient_email}")
                    return {"status": "sent"}
                else:
                    email_log.status = EmailStatus.FAILED
                    email_log.last_error = "Email provider returned failure status."
                    await session.commit()
                    return {"status": "failed", "error": email_log.last_error}

            except EmailProviderError as provider_err:
                email_log.status = EmailStatus.FAILED
                email_log.last_error = str(provider_err)
                await session.commit()
                logger.error(f"[EmailWorker] Delivery failed for EmailLog {log_id}: {provider_err}")
                raise provider_err
            except Exception as exc:
                email_log.status = EmailStatus.FAILED
                email_log.last_error = str(exc)
                await session.commit()
                logger.error(f"[EmailWorker] Unexpected failure for EmailLog {log_id}: {exc}")
                raise exc
    finally:
        import sys
        if "pytest" not in sys.modules and not os.getenv("TESTING"):
            try:
                await engine.dispose()
            except Exception:
                pass


import concurrent.futures


def _run_sync_coro(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    else:
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.email_tasks.send_email_async",
    max_retries=3,
    default_retry_delay=30,
)
def send_email_async(self, email_log_id: str) -> Dict[str, Any]:
    """Celery task wrapper to process async email delivery with backoff retries."""
    try:
        return _run_sync_coro(_async_send_email(email_log_id))
    except Exception as exc:
        logger.warning(f"[EmailWorker] Task attempt {self.request.retries + 1} failed for log {email_log_id}: {exc}")
        if self.request.retries < self.max_retries:
            countdown = 30 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)
        raise exc


async def _async_check_meeting_reminders() -> Dict[str, int]:
    """Query upcoming meetings due in ~24 hours or ~1 hour and queue reminder emails."""
    from app.services.email.dispatch import EmailDispatchService

    now = datetime.now(timezone.utc)
    sent_count = 0

    try:
        async with AsyncSessionLocal() as session:
            # Query active scheduled meetings
            stmt = select(Meeting).where(
                Meeting.scheduled_start_time.isnot(None),
                Meeting.scheduled_start_time > now,
            )
            meetings = list((await session.execute(stmt)).scalars().all())

            for meeting in meetings:
                start_dt = meeting.scheduled_start_time
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)

                time_until = start_dt - now
                time_until_hours = time_until.total_seconds() / 3600.0

                label = None
                if 23.0 <= time_until_hours <= 25.0:
                    label = "24 hours"
                elif 0.5 <= time_until_hours <= 1.25:
                    label = "1 hour"

                if not label:
                    continue

                # Query participants
                part_stmt = select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting.id)
                participants = list((await session.execute(part_stmt)).scalars().all())

                for p in participants:
                    if not p.email:
                        continue

                    # Idempotent key
                    idempotency_key = f"reminder:{meeting.id}:{p.email}:{label}"
                    
                    log = await EmailDispatchService.enqueue_email(
                        db=session,
                        recipient_email=p.email,
                        recipient_name=p.name or p.email,
                        event_type="meeting_reminder",
                        template_data={
                            "meeting_id": str(meeting.id),
                            "meeting_title": meeting.title,
                            "time_until": label,
                            "scheduled_at": start_dt.strftime("%Y-%m-%d %H:%M UTC"),
                            "agenda": meeting.agenda or "",
                        },
                        user_id=p.user_id,
                        workspace_id=meeting.workspace_id,
                        meeting_id=meeting.id,
                        idempotency_key=idempotency_key,
                        check_preference=True,
                    )
                    if log:
                        sent_count += 1

            return {"reminders_enqueued": sent_count}
    finally:
        import sys
        if "pytest" not in sys.modules and not os.getenv("TESTING"):
            try:
                await engine.dispose()
            except Exception:
                pass


@celery_app.task(
    name="app.workers.tasks.email_tasks.check_meeting_reminders",
)
def check_meeting_reminders() -> Dict[str, int]:
    """Periodic Celery task to send 24-hour and 1-hour meeting reminders."""
    return _run_sync_coro(_async_check_meeting_reminders())
