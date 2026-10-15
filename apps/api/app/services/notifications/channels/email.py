"""Email notification delivery channel."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.services.email import get_email_provider
from app.services.notifications.channels.base import BaseNotificationChannel

logger = logging.getLogger(__name__)


class EmailChannel(BaseNotificationChannel):
    """Email notification channel dispatching messages via configured EmailProvider."""

    def _should_send_email(
        self,
        notification_type: NotificationType,
        preference: NotificationPreference,
    ) -> bool:
        """Evaluate whether email delivery is permitted for notification type according to user preferences."""
        if not preference.email_enabled:
            return False

        if notification_type in (
            NotificationType.MEETING_PROCESSING_COMPLETED,
            NotificationType.MEETING_PROCESSING_FAILED,
        ):
            return preference.notify_on_meeting_complete
        elif notification_type in (
            NotificationType.AI_ANALYSIS_COMPLETED,
            NotificationType.AI_ANALYSIS_FAILED,
        ):
            return preference.notify_on_ai_complete
        elif notification_type in (
            NotificationType.ACTION_ITEM_ASSIGNED,
            NotificationType.ACTION_ITEM_UPDATED,
        ):
            return preference.notify_on_action_item_assigned
        elif notification_type in (
            NotificationType.ACTION_ITEM_DUE_SOON,
            NotificationType.ACTION_ITEM_OVERDUE,
        ):
            return preference.notify_on_action_item_due
        elif notification_type == NotificationType.FOLLOW_UP_READY:
            return preference.notify_on_follow_up_ready

        return True

    async def send(
        self,
        db: AsyncSession,
        notification: Notification,
        user: User,
        preference: NotificationPreference,
    ) -> bool:
        """Deliver email notification to user inbox if permitted."""
        if not self._should_send_email(notification.type, preference):
            logger.info(f"[EmailChannel] Email notifications suppressed by preferences for user {user.id}")
            return False

        from app.services.email.dispatch import EmailDispatchService

        event_type_map = {
            NotificationType.MEETING_PROCESSING_COMPLETED: "post_meeting_summary",
            NotificationType.AI_ANALYSIS_COMPLETED: "ai_insights_ready",
            NotificationType.ACTION_ITEM_ASSIGNED: "action_item_assigned",
            NotificationType.ACTION_ITEM_DUE_SOON: "meeting_reminder",
            NotificationType.ACTION_ITEM_OVERDUE: "meeting_reminder",
            NotificationType.FOLLOW_UP_READY: "follow_up_draft",
        }
        event_type = event_type_map.get(notification.type, "general_notification")

        try:
            log = await EmailDispatchService.enqueue_email(
                db=db,
                recipient_email=user.email,
                recipient_name=user.full_name,
                event_type=event_type,
                template_data={
                    "meeting_id": str(notification.entity_id) if notification.entity_id else "",
                    "meeting_title": notification.title,
                    "summary": notification.message,
                    "task_description": notification.message,
                    "assignee_name": user.full_name,
                },
                user_id=user.id,
                workspace_id=notification.workspace_id,
                meeting_id=notification.entity_id if notification.entity_type == "meeting" else None,
                idempotency_key=f"notification:{notification.id}:{user.id}",
                check_preference=False,  # Already checked above in _should_send_email
            )
            logger.info(f"[EmailChannel] Enqueued async email notification to {user.email}")
            return log is not None
        except Exception as exc:
            logger.error(f"[EmailChannel] Failed to enqueue email notification: {exc}")
            return False
