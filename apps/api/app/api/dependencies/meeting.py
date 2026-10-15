"""Meeting authorization and workspace membership dependencies."""

import uuid
from typing import Tuple
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import WorkspaceRole
from app.models.meeting import Meeting
from app.models.user import User
from app.models.workspace import WorkspaceMember


async def get_meeting_and_membership(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Meeting, WorkspaceMember]:
    """Verify that the active (non-trashed) meeting exists and the authenticated user belongs to its workspace.

    Returns 404 Not Found if the meeting does not exist, is in Trash, OR if the user is not
    a member of the workspace, completely preventing cross-workspace IDOR and resource leakage.
    """
    stmt = (
        select(Meeting, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
        .where(
            Meeting.id == meeting_id,
            Meeting.deleted_at.is_(None),
            WorkspaceMember.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found.",
        )

    meeting, member = row
    return meeting, member


async def get_trashed_meeting_and_membership(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Meeting, WorkspaceMember]:
    """Verify that a trashed meeting exists and the authenticated user belongs to its workspace."""
    stmt = (
        select(Meeting, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
        .where(
            Meeting.id == meeting_id,
            Meeting.deleted_at.isnot(None),
            WorkspaceMember.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trashed meeting not found.",
        )

    meeting, member = row
    return meeting, member


async def get_any_meeting_and_membership(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Meeting, WorkspaceMember]:
    """Retrieve meeting regardless of soft-delete state for detail endpoints."""
    stmt = (
        select(Meeting, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
        .where(
            Meeting.id == meeting_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found.",
        )

    meeting, member = row
    return meeting, member


async def require_meeting_update_permission(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
) -> Tuple[Meeting, WorkspaceMember]:
    """Enforce that only the meeting creator or workspace OWNER/ADMIN can update the meeting."""
    meeting, member = context
    is_creator = meeting.creator_id == current_user.id
    is_admin_or_owner = member.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not (is_creator or is_admin_or_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this meeting.",
        )
    return meeting, member


async def require_meeting_delete_permission(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
) -> Tuple[Meeting, WorkspaceMember]:
    """Enforce that only the meeting creator or workspace OWNER/ADMIN can move the meeting to Trash."""
    meeting, member = context
    is_creator = meeting.creator_id == current_user.id
    is_admin_or_owner = member.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not (is_creator or is_admin_or_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete this meeting.",
        )
    return meeting, member


async def require_trashed_meeting_permission(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_trashed_meeting_and_membership),
    current_user: User = Depends(get_current_user),
) -> Tuple[Meeting, WorkspaceMember]:
    """Enforce that only the meeting creator or workspace OWNER/ADMIN can restore or permanently delete a trashed meeting."""
    meeting, member = context
    is_creator = meeting.creator_id == current_user.id
    is_admin_or_owner = member.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not (is_creator or is_admin_or_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this action on the trashed meeting.",
        )
    return meeting, member
