"""Abstract base class for notification delivery channels."""

from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPreference
from app.models.user import User


class BaseNotificationChannel(ABC):
    """Abstract interface for a notification delivery channel (in-app, email, etc.)."""

    @abstractmethod
    async def send(
        self,
        db: AsyncSession,
        notification: Notification,
        user: User,
        preference: NotificationPreference,
    ) -> bool:
        """Deliver notification via channel if user preference permits."""
        pass
