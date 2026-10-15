"""In-app notification delivery channel."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.services.notifications.channels.base import BaseNotificationChannel

logger = logging.getLogger(__name__)


class InAppChannel(BaseNotificationChannel):
    """In-app channel persisting notifications in database."""

    async def send(
        self,
        db: AsyncSession,
        notification: Notification,
        user: User,
        preference: NotificationPreference,
    ) -> bool:
        """Persist in-app notification if user enabled in-app notifications."""
        if not preference.in_app_enabled:
            logger.info(f"[InAppChannel] In-app notifications disabled for user {user.id}")
            return False

        db.add(notification)
        await db.flush()
        logger.info(f"[InAppChannel] Saved in-app notification for user {user.id}: {notification.title}")
        return True
