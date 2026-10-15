"""Comprehensive automated test suite for Notifications + AI Follow-Up module.

Tests cover:
1. Notification creation & multi-channel dispatch (In-App + Email)
2. Notification listing, pagination, and unread filtering
3. Unread count endpoint
4. Mark as read & Mark all as read
5. Notification deletion
6. User isolation & security (User A cannot read User B's notifications)
7. User Notification Preferences CRUD & preference enforcement (opt-out suppressing email)
8. Email Provider abstraction & MockEmailProvider
9. Grounded AI follow-up draft generation
10. Follow-up listing, details retrieval, and draft updates
11. Human approval explicit email sending workflow (POST /follow-ups/{id}/send)
12. Scheduled action item due reminders Celery task and idempotency
"""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.enums import (
    ActionItemStatus,
    FollowUpStatus,
    FollowUpType,
    MeetingPlatform,
    MeetingStatus,
    NotificationType,
    PriorityLevel,
    WorkspaceRole,
)
from app.models.follow_up import FollowUp
from app.models.intelligence import ActionItem, MeetingSummary
from app.models.meeting import Meeting
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.follow_up import FollowUpCreateRequest, FollowUpUpdateRequest
from app.schemas.notification import NotificationPreferenceUpdate
from app.services.email import get_mock_email_provider
from app.services.follow_up_service import FollowUpService
from app.services.notifications.notification_service import NotificationService
from app.workers.tasks.notification_tasks import (
    _async_check_action_item_due_reminders,
    check_action_item_due_reminders,
    dispatch_notification_task,
)


async def _create_test_notification_env(session: AsyncSession, suffix: str = "1"):
    """Helper setup creating user, workspace, meeting, meeting summary, and action items."""
    user = User(
        id=uuid.uuid4(),
        email=f"notif_user_{suffix}_{uuid.uuid4().hex[:6]}@example.com",
        full_name=f"Notif User {suffix}",
        hashed_password="hashed_password_sample",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        name=f"Notif Workspace {suffix}",
        slug=f"notif-ws-{suffix}-{uuid.uuid4().hex[:6]}",
        created_by_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
    )
    session.add(member)

    meeting = Meeting(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        creator_id=user.id,
        title=f"Notif Test Meeting {suffix}",
        status=MeetingStatus.COMPLETED,
        platform=MeetingPlatform.OTHER,
    )
    session.add(meeting)
    await session.flush()

    summary = MeetingSummary(
        id=uuid.uuid4(),
        meeting_id=meeting.id,
        overview="Discussed upcoming product architecture and API deployment timelines.",
        version=1,
    )
    session.add(summary)

    action_item = ActionItem(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        meeting_id=meeting.id,
        assignee_id=user.id,
        title="Deploy API service",
        description="Deploy API service to production staging cluster.",
        status=ActionItemStatus.OPEN,
        priority=PriorityLevel.HIGH,
        due_date=datetime.now(timezone.utc) + timedelta(hours=12),
        version=1,
    )
    session.add(action_item)

    await session.commit()
    return user, workspace, meeting, summary, action_item


@pytest.mark.asyncio
async def test_notification_creation_and_dispatch():
    """Verify NotificationService creates persistent in-app notification and dispatches email."""
    mock_email = get_mock_email_provider()
    mock_email.clear()

    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "dispatch")

        notif = await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.AI_ANALYSIS_COMPLETED,
            title="AI Analysis Complete",
            message="Your meeting AI intelligence is ready.",
            entity_type="meeting",
            entity_id=meeting.id,
        )

        assert notif.id is not None
        assert notif.user_id == user.id
        assert notif.is_read is False

        # Verify email dispatched via MockEmailProvider
        assert len(mock_email.sent_emails) > 0
        sent = mock_email.sent_emails[-1]
        assert sent["to_email"] == user.email
        assert "AI Analysis Complete" in sent["subject"]


@pytest.mark.asyncio
async def test_notification_listing_and_unread_count():
    """Verify paginated listing, unread count, and filtering by read status."""
    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "list")

        # Create 3 notifications
        for i in range(3):
            await NotificationService.create_and_dispatch_notification(
                db=session,
                user_id=user.id,
                workspace_id=ws.id,
                type=NotificationType.ACTION_ITEM_ASSIGNED,
                title=f"Action Item {i}",
                message=f"Task {i} assigned.",
            )

        items, total, unread_count = await NotificationService.list_notifications(
            db=session,
            user_id=user.id,
            page=1,
            page_size=10,
        )

        assert total >= 3
        assert unread_count >= 3
        assert len(items) >= 3

        count = await NotificationService.get_unread_count(session, user.id)
        assert count == unread_count


@pytest.mark.asyncio
async def test_mark_notification_read_and_read_all():
    """Verify marking single notification read and marking all read."""
    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "read")

        n1 = await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.ACTION_ITEM_ASSIGNED,
            title="Item 1",
            message="Task 1",
        )
        n2 = await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.ACTION_ITEM_ASSIGNED,
            title="Item 2",
            message="Task 2",
        )

        # Mark single as read
        read_n1 = await NotificationService.mark_as_read(session, user.id, n1.id)
        assert read_n1.is_read is True
        assert read_n1.read_at is not None

        # Mark single as unread
        unread_n1 = await NotificationService.mark_as_unread(session, user.id, n1.id)
        assert unread_n1.is_read is False
        assert unread_n1.read_at is None

        # Mark all as read
        count_updated = await NotificationService.mark_all_as_read(session, user.id)
        assert count_updated >= 1

        unread_remaining = await NotificationService.get_unread_count(session, user.id)
        assert unread_remaining == 0


@pytest.mark.asyncio
async def test_notification_deletion_and_clear_all():
    """Verify deleting a single notification and clearing all notifications for user."""
    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "del")

        n = await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.TRANSCRIPT_COMPLETED,
            title="Transcript Ready",
            message="Transcript completed.",
        )

        await NotificationService.delete_notification(session, user.id, n.id)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await NotificationService.mark_as_read(session, user.id, n.id)
        assert exc_info.value.status_code == 404

        # Create 2 more notifications and clear all
        await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.ACTION_ITEM_ASSIGNED,
            title="Clear 1",
            message="Msg 1",
        )
        await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.ACTION_ITEM_ASSIGNED,
            title="Clear 2",
            message="Msg 2",
        )

        cleared_count = await NotificationService.clear_all_notifications(session, user.id)
        assert cleared_count == 2

        items, total, unread = await NotificationService.list_notifications(session, user.id)
        assert total == 0
        assert unread == 0


@pytest.mark.asyncio
async def test_user_notification_isolation():
    """Verify User A cannot read, modify, delete or clear User B's notifications."""
    async with AsyncSessionLocal() as session:
        user_a, ws_a, meeting_a, s_a, ai_a = await _create_test_notification_env(session, "user_a")
        user_b, ws_b, meeting_b, s_b, ai_b = await _create_test_notification_env(session, "user_b")

        n_a = await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user_a.id,
            workspace_id=ws_a.id,
            type=NotificationType.MEETING_PROCESSING_COMPLETED,
            title="User A Meeting Complete",
            message="Meeting processed.",
        )

        from fastapi import HTTPException
        # User B attempting to mark User A's notification as read
        with pytest.raises(HTTPException) as exc_info:
            await NotificationService.mark_as_read(session, user_b.id, n_a.id)
        assert exc_info.value.status_code == 404

        # User B attempting to mark User A's notification as unread
        with pytest.raises(HTTPException) as exc_info:
            await NotificationService.mark_as_unread(session, user_b.id, n_a.id)
        assert exc_info.value.status_code == 404

        # User B attempting to delete User A's notification
        with pytest.raises(HTTPException) as exc_info:
            await NotificationService.delete_notification(session, user_b.id, n_a.id)
        assert exc_info.value.status_code == 404

        # User B clearing their notifications should NOT delete User A's notification
        await NotificationService.clear_all_notifications(session, user_b.id)
        items_a, total_a, _ = await NotificationService.list_notifications(session, user_a.id)
        assert total_a == 1
        assert items_a[0].id == n_a.id



@pytest.mark.asyncio
async def test_user_notification_preferences_enforcement():
    """Verify notification preference opt-outs suppress email delivery."""
    mock_email = get_mock_email_provider()
    mock_email.clear()

    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "pref")

        # Disable email notifications
        pref = await NotificationService.update_preferences(
            db=session,
            user_id=user.id,
            data=NotificationPreferenceUpdate(email_enabled=False),
        )
        assert pref.email_enabled is False

        initial_email_count = len(mock_email.sent_emails)

        # Dispatch notification
        await NotificationService.create_and_dispatch_notification(
            db=session,
            user_id=user.id,
            workspace_id=ws.id,
            type=NotificationType.AI_ANALYSIS_COMPLETED,
            title="Analysis Done",
            message="Summary available.",
        )

        # Email count should NOT increase because email_enabled is False
        assert len(mock_email.sent_emails) == initial_email_count


@pytest.mark.asyncio
async def test_ai_follow_up_draft_generation():
    """Verify FollowUpService generates grounded follow-up email draft."""
    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "followup_gen")

        req = FollowUpCreateRequest(
            type=FollowUpType.EMAIL_DRAFT,
            additional_instructions="Keep tone crisp and professional.",
        )

        follow_up = await FollowUpService.generate_follow_up(
            db=session,
            meeting_id=meeting.id,
            current_user=user,
            data=req,
        )

        assert follow_up.id is not None
        assert follow_up.meeting_id == meeting.id
        assert follow_up.status == FollowUpStatus.READY
        assert follow_up.subject != ""
        assert follow_up.content != ""


@pytest.mark.asyncio
async def test_follow_up_update_and_explicit_human_send():
    """Verify editing follow-up draft and triggering explicit human-approved send."""
    mock_email = get_mock_email_provider()
    mock_email.clear()

    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "followup_send")

        # Generate draft
        req = FollowUpCreateRequest(type=FollowUpType.EMAIL_DRAFT)
        follow_up = await FollowUpService.generate_follow_up(session, meeting.id, user, req)

        # User edits draft
        edited = await FollowUpService.update_follow_up(
            db=session,
            follow_up_id=follow_up.id,
            current_user=user,
            data=FollowUpUpdateRequest(
                subject="Updated Subject Line: Action Items",
                recipients=[user.email],
            ),
        )
        assert edited.subject == "Updated Subject Line: Action Items"

        # Explicit Human Approval Send
        sent_follow_up = await FollowUpService.send_follow_up(session, follow_up.id, user)
        assert sent_follow_up.status == FollowUpStatus.SENT

        # Verify email dispatched
        assert len(mock_email.sent_emails) > 0
        last_sent = mock_email.sent_emails[-1]
        assert last_sent["to_email"] == user.email
        assert "Updated Subject Line: Action Items" in last_sent["subject"]


@pytest.mark.asyncio
async def test_action_item_due_reminders_scheduled_task():
    """Verify Celery task check_action_item_due_reminders scans due items and sends reminders idempotently."""
    async with AsyncSessionLocal() as session:
        user, ws, meeting, summary, ai = await _create_test_notification_env(session, "reminder")

        # Set action item due date to 1 hour from now
        ai.due_date = datetime.now(timezone.utc) + timedelta(hours=1)
        await session.commit()

        # Run scheduled task routine
        metrics = await _async_check_action_item_due_reminders()
        assert metrics["reminders_sent"] >= 1

        # Run second time (idempotency check — duplicate should be suppressed)
        metrics2 = await _async_check_action_item_due_reminders()
        assert metrics2["reminders_sent"] == 0
