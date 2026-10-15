"""Pydantic schemas for notifications and user notification preferences."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationType


class NotificationResponse(BaseModel):
    """Public representation of a user notification."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    notification_metadata: Optional[Dict[str, Any]] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread notifications count summary."""

    unread_count: int


class NotificationPreferenceResponse(BaseModel):
    """Public representation of user notification preferences."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email_enabled: bool
    in_app_enabled: bool
    notify_on_meeting_invitation: bool = True
    notify_on_meeting_reminder: bool = True
    notify_on_meeting_update: bool = True
    notify_on_meeting_cancellation: bool = True
    notify_on_meeting_complete: bool = True
    notify_on_ai_complete: bool = True
    notify_on_recording_ready: bool = True
    notify_on_action_item_assigned: bool = True
    notify_on_action_item_due: bool = True
    notify_on_follow_up_ready: bool = True
    created_at: datetime
    updated_at: datetime


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating user notification preferences."""

    email_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    notify_on_meeting_invitation: Optional[bool] = None
    notify_on_meeting_reminder: Optional[bool] = None
    notify_on_meeting_update: Optional[bool] = None
    notify_on_meeting_cancellation: Optional[bool] = None
    notify_on_meeting_complete: Optional[bool] = None
    notify_on_ai_complete: Optional[bool] = None
    notify_on_recording_ready: Optional[bool] = None
    notify_on_action_item_assigned: Optional[bool] = None
    notify_on_action_item_due: Optional[bool] = None
    notify_on_follow_up_ready: Optional[bool] = None
