"""Core Notification domain service handling notification creation, preferences, and multi-channel dispatch."""

from datetime import datetime, timezone
import logging
import uuid
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.schemas.notification import NotificationPreferenceUpdate
from app.services.notifications.channels.email import EmailChannel
from app.services.notifications.channels.in_app import InAppChannel

logger = logging.getLogger(__name__)


class NotificationService:
    """Domain service managing user notifications, preferences, and channel delivery."""

    @classmethod
    async def get_or_create_preferences(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> NotificationPreference:
        """Fetch user notification preferences or instantiate default preferences if none exist."""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        res = await db.execute(stmt)
        pref = res.scalar_one_or_none()

        if not pref:
            try:
                pref = NotificationPreference(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    email_enabled=True,
                    in_app_enabled=True,
                    notify_on_meeting_invitation=True,
                    notify_on_meeting_reminder=True,
                    notify_on_meeting_update=True,
                    notify_on_meeting_cancellation=True,
                    notify_on_meeting_complete=True,
                    notify_on_ai_complete=True,
                    notify_on_recording_ready=True,
                    notify_on_action_item_assigned=True,
                    notify_on_action_item_due=True,
                    notify_on_follow_up_ready=True,
                )
                db.add(pref)
                await db.commit()
                await db.refresh(pref)
            except Exception:
                await db.rollback()
                stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
                res = await db.execute(stmt)
                pref = res.scalar_one_or_none()

        return pref

    @classmethod
    async def update_preferences(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        """Update notification preferences for a user."""
        pref = await cls.get_or_create_preferences(db, user_id)

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(pref, key, value)

        await db.commit()
        await db.refresh(pref)
        return pref

    @classmethod
    async def create_and_dispatch_notification(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        type: NotificationType,
        title: str,
        message: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        notification_metadata: Optional[dict] = None,
    ) -> Notification:
        """Instantiate a notification and dispatch across active channels (In-App, Email)."""
        user_stmt = select(User).where(User.id == user_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} does not exist.")

        pref = await cls.get_or_create_preferences(db, user_id)

        notification = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            workspace_id=workspace_id,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            notification_metadata=notification_metadata,
            is_read=False,
        )

        # 1. In-App Delivery
        in_app_channel = InAppChannel()
        await in_app_channel.send(db, notification, user, pref)

        # 2. Email Delivery
        email_channel = EmailChannel()
        await email_channel.send(db, notification, user, pref)

        await db.commit()
        await db.refresh(notification)
        return notification

    @classmethod
    async def list_notifications(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
        notification_type: Optional[NotificationType] = None,
    ) -> Tuple[List[Notification], int, int]:
        """List notifications for current user with pagination and filters."""
        query = select(Notification).where(Notification.user_id == user_id)

        if unread_only:
            query = query.where(Notification.is_read == False)
        if notification_type:
            query = query.where(Notification.type == notification_type)

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        unread_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
        unread_count = (await db.execute(unread_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)

        res = await db.execute(query)
        notifications = list(res.scalars().all())

        return notifications, total, unread_count

    @classmethod
    async def get_unread_count(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Get unread notification count for user."""
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
        return (await db.execute(stmt)).scalar() or 0

    @classmethod
    async def mark_as_read(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification:
        """Mark a single notification as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        res = await db.execute(stmt)
        notification = res.scalar_one_or_none()

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(notification)

        return notification

    @classmethod
    async def mark_as_unread(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification:
        """Mark a single notification as unread."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        res = await db.execute(stmt)
        notification = res.scalar_one_or_none()

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        if notification.is_read:
            notification.is_read = False
            notification.read_at = None
            await db.commit()
            await db.refresh(notification)

        return notification

    @classmethod
    async def mark_all_as_read(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Mark all unread notifications for a user as read."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True, read_at=now)
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0

    @classmethod
    async def delete_notification(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> None:
        """Delete a notification belonging to user."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        res = await db.execute(stmt)
        notification = res.scalar_one_or_none()

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        await db.delete(notification)
        await db.commit()

    @classmethod
    async def clear_all_notifications(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Clear all notifications belonging to current user."""
        stmt = delete(Notification).where(Notification.user_id == user_id)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0
