"""Celery tasks for asynchronous notification delivery and action item due reminders."""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models.enums import ActionItemStatus, NotificationType
from app.models.intelligence import ActionItem
from app.models.notification import Notification
from app.services.notifications.notification_service import NotificationService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _async_dispatch_notification(
    user_id_str: str,
    workspace_id_str: str,
    type_str: str,
    title: str,
    message: str,
    entity_type: Optional[str] = None,
    entity_id_str: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Dict[str, Any]:
    """Execute async notification creation and channel delivery."""
    try:
        user_id = uuid.UUID(user_id_str)
        workspace_id = uuid.UUID(workspace_id_str)
        entity_id = uuid.UUID(entity_id_str) if entity_id_str else None
        n_type = NotificationType(type_str)
    except Exception as exc:
        logger.error(f"Invalid parameters passed to notification worker: {exc}")
        return {"status": "invalid_parameters"}

    try:
        async with AsyncSessionLocal() as session:
            notification = await NotificationService.create_and_dispatch_notification(
                db=session,
                user_id=user_id,
                workspace_id=workspace_id,
                type=n_type,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                notification_metadata=metadata,
            )
            return {"status": "dispatched", "notification_id": str(notification.id)}
    finally:
        try:
            await engine.dispose()
        except Exception:
            pass


@celery_app.task(
    bind=True,
    name="app.workers.tasks.notification_tasks.dispatch_notification_task",
    max_retries=3,
)
def dispatch_notification_task(
    self,
    user_id: str,
    workspace_id: str,
    type: str,
    title: str,
    message: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Dict[str, Any]:
    """Celery task wrapper to asynchronously dispatch notifications."""
    try:
        return asyncio.run(
            _async_dispatch_notification(
                user_id_str=user_id,
                workspace_id_str=workspace_id,
                type_str=type,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id_str=entity_id,
                metadata=metadata,
            )
        )
    except Exception as exc:
        logger.error(f"Failed dispatching notification task for user {user_id}: {exc}")
        raise


async def _async_check_action_item_due_reminders() -> Dict[str, int]:
    """Scan open action items due within 24 hours or overdue and send idempotent reminder notifications."""
    now = datetime.now(timezone.utc)
    due_threshold = now + timedelta(hours=24)
    sent_reminders = 0

    try:
        async with AsyncSessionLocal() as session:
            # Query open/in-progress action items with due dates and assigned users
            stmt = select(ActionItem).where(
                ActionItem.status.in_([ActionItemStatus.OPEN, ActionItemStatus.IN_PROGRESS]),
                ActionItem.due_date.isnot(None),
                ActionItem.assignee_id.isnot(None),
            )
            items = list((await session.execute(stmt)).scalars().all())

            for item in items:
                if not item.due_date or not item.assignee_id:
                    continue

                # Ensure due_date is timezone-aware
                due_dt = item.due_date
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)

                is_overdue = due_dt < now
                is_due_soon = now <= due_dt <= due_threshold

                if not (is_overdue or is_due_soon):
                    continue

                n_type = NotificationType.ACTION_ITEM_OVERDUE if is_overdue else NotificationType.ACTION_ITEM_DUE_SOON
                title = f"Action Item Overdue: {item.description[:40]}" if is_overdue else f"Action Item Due Soon: {item.description[:40]}"

                # Idempotency check: Don't resend if reminder was sent in last 24 hours
                recent_cutoff = now - timedelta(hours=24)
                dup_stmt = select(Notification).where(
                    Notification.user_id == item.assignee_id,
                    Notification.entity_type == "action_item",
                    Notification.entity_id == item.id,
                    Notification.type == n_type,
                    Notification.created_at >= recent_cutoff,
                )
                dup_exists = (await session.execute(dup_stmt)).scalars().first()
                if dup_exists:
                    continue

                msg = f"Your assigned action item '{item.description}' is {'overdue' if is_overdue else 'due soon'}."
                await NotificationService.create_and_dispatch_notification(
                    db=session,
                    user_id=item.assignee_id,
                    workspace_id=item.workspace_id,
                    type=n_type,
                    title=title,
                    message=msg,
                    entity_type="action_item",
                    entity_id=item.id,
                )
                sent_reminders += 1

            return {"reminders_sent": sent_reminders}
    finally:
        try:
            await engine.dispose()
        except Exception:
            pass


@celery_app.task(
    name="app.workers.tasks.notification_tasks.check_action_item_due_reminders",
)
def check_action_item_due_reminders() -> Dict[str, int]:
    """Celery scheduled task to check action item deadlines and send reminders."""
    return asyncio.run(_async_check_action_item_due_reminders())
