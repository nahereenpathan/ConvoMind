"""Notification and user notification preferences API endpoints."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import NotificationType
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notifications.notification_service import NotificationService

router = APIRouter()


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user notifications",
    description="Retrieve paginated notifications for the current authenticated user.",
)
async def list_notifications(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(default=False, description="Filter only unread notifications"),
    notification_type: Optional[NotificationType] = Query(default=None, description="Filter by notification type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """List user notifications."""
    items, total, unread_count = await NotificationService.list_notifications(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
        notification_type=notification_type,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get unread notification count",
    description="Get total number of unread notifications for the current user.",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Get unread notification count."""
    count = await NotificationService.get_unread_count(db=db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.get(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification preferences",
    description="Retrieve notification settings and channel preferences for the current user.",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceResponse:
    """Get notification preferences."""
    pref = await NotificationService.get_or_create_preferences(db=db, user_id=current_user.id)
    return NotificationPreferenceResponse.model_validate(pref)


@router.patch(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update notification preferences",
    description="Update notification channel and event type preferences for the current user.",
)
async def update_notification_preferences(
    data: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceResponse:
    """Update notification preferences."""
    pref = await NotificationService.update_preferences(db=db, user_id=current_user.id, data=data)
    return NotificationPreferenceResponse.model_validate(pref)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Mark a single notification as read.",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Mark notification as read."""
    notification = await NotificationService.mark_as_read(
        db=db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    return NotificationResponse.model_validate(notification)


@router.patch(
    "/{notification_id}/unread",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as unread",
    description="Mark a single notification as unread.",
)
async def mark_notification_unread(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Mark notification as unread."""
    notification = await NotificationService.mark_as_unread(
        db=db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    return NotificationResponse.model_validate(notification)


@router.patch(
    "/read-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Mark all unread notifications for the current user as read.",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Mark all notifications as read."""
    count = await NotificationService.mark_all_as_read(db=db, user_id=current_user.id)
    return MessageResponse(message=f"Marked {count} notifications as read.")


@router.delete(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear all notifications",
    description="Clear all notifications belonging to the current user.",
)
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Clear all notifications for the current user."""
    count = await NotificationService.clear_all_notifications(db=db, user_id=current_user.id)
    return MessageResponse(message=f"Cleared {count} notifications.")


@router.delete(
    "/{notification_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete notification",
    description="Delete a notification belonging to the current user.",
)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete notification."""
    await NotificationService.delete_notification(
        db=db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    return MessageResponse(message="Notification deleted successfully.")


from pydantic import BaseModel
from datetime import datetime, timezone
import asyncio
from app.services.email import get_email_provider, EmailProviderError, MockEmailProvider
from app.services.email.templates import render_email_template


class TestSmtpRequest(BaseModel):
    target_email: Optional[str] = None


@router.post(
    "/test-smtp",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Test SMTP connection and email delivery",
    description="Verify SMTP host, credentials, TLS handshake, and dispatch a test email.",
)
async def test_smtp_connection(
    req: TestSmtpRequest = TestSmtpRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Test SMTP connection and email dispatch."""
    recipient = req.target_email or current_user.email
    if not recipient or "@" not in recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recipient email address for SMTP test.",
        )

    provider = get_email_provider()
    if isinstance(provider, MockEmailProvider):
        return MessageResponse(
            message=f"Mock email provider is active (EMAIL_PROVIDER=mock). Test email logged for {recipient}."
        )

    try:
        subject, text_body, html_body = render_email_template("general_notification", {
            "subject": "Production SMTP Connection Test",
            "body": f"Hello {current_user.full_name or 'User'},<br><br>This is an automated test email confirming your ConvoMind SMTP delivery pipeline is active and working properly."
        })
        if asyncio.iscoroutinefunction(provider.send_email):
            await provider.send_email(
                to_email=recipient,
                subject=f"[ConvoMind] {subject}",
                body_text=text_body,
                body_html=html_body,
            )
        else:
            provider.send_email(
                to_email=recipient,
                subject=f"[ConvoMind] {subject}",
                body_text=text_body,
                body_html=html_body,
            )
        return MessageResponse(message=f"SMTP connection verified and test email successfully delivered to {recipient}.")
    except EmailProviderError as epe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SMTP delivery failed: {epe}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_530_SERVICE_UNAVAILABLE,
            detail=f"SMTP error: {exc}",
        )

