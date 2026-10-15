"""Workspace authentication, membership verification, and RBAC dependencies."""

import uuid
from typing import Callable, List, Optional, Tuple
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


async def resolve_workspace_context(
    db: AsyncSession,
    current_user: User,
    workspace_id: Optional[uuid.UUID] = None,
) -> uuid.UUID:
    """Resolve and validate active workspace UUID for the authenticated user.

    If workspace_id is provided, verifies active user membership.
    If workspace_id is None, automatically resolves user's primary workspace membership.
    Raises 404 Not Found if workspace does not exist or user is not a member.
    """
    if workspace_id is not None:
        stmt = select(WorkspaceMember.workspace_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        res = await db.execute(stmt)
        matched_id = res.scalar_one_or_none()
        if matched_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or access denied.",
            )
        return matched_id

    # Fallback to user's first joined workspace membership
    stmt = (
        select(WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.joined_at.asc())
        .limit(1)
    )
    res = await db.execute(stmt)
    default_ws_id = res.scalar_one_or_none()

    if default_ws_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workspace context found for user. Please create or join a workspace.",
        )

    return default_ws_id


async def get_workspace_and_membership(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Workspace, WorkspaceMember]:
    """Verify that the workspace exists and the authenticated user is an active member.

    Returns 404 Not Found if the workspace does not exist OR if the user is not
    a member, completely mitigating IDOR and workspace enumeration risks.
    """
    stmt = (
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    workspace, member = row
    return workspace, member


def require_workspace_role(
    allowed_roles: List[WorkspaceRole],
) -> Callable:
    """Dependency factory enforcing that the authenticated member holds one of the specified roles."""

    async def role_checker(
        context: Tuple[Workspace, WorkspaceMember] = Depends(
            get_workspace_and_membership
        ),
    ) -> Tuple[Workspace, WorkspaceMember]:
        workspace, member = context
        if member.role not in allowed_roles:
            allowed_names = ", ".join([r.value for r in allowed_roles])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {allowed_names}.",
            )
        return workspace, member

    return role_checker


# Convenient role-checking dependencies
require_workspace_member = require_workspace_role(
    [
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.MEMBER,
        WorkspaceRole.GUEST,
    ]
)

require_workspace_admin_or_owner = require_workspace_role(
    [
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
    ]
)

require_workspace_owner = require_workspace_role(
    [
        WorkspaceRole.OWNER,
    ]
)
