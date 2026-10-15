"""Workspace and Workspace Member management API routes."""

import uuid
from typing import List, Tuple
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_workspace_and_membership,
    require_workspace_admin_or_owner,
    require_workspace_member,
    require_workspace_owner,
)
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.auth import MessageResponse
from app.schemas.transcript import TranscriptSearchResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
    WorkspaceWithRoleResponse,
)
from app.services.transcription_service import TranscriptionService
from app.services.workspace_service import workspace_service

router = APIRouter()


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
    description="Create a workspace with automatic unique slug generation. The creator is assigned as OWNER.",
)
async def create_workspace(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Create a new workspace."""
    workspace = await workspace_service.create_workspace(
        db=db,
        current_user=current_user,
        data=data,
    )
    return WorkspaceResponse.model_validate(workspace)


@router.get(
    "",
    response_model=List[WorkspaceWithRoleResponse],
    status_code=status.HTTP_200_OK,
    summary="List workspaces for current user",
    description="Retrieve all workspaces where the authenticated user is a member.",
)
async def list_my_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[WorkspaceWithRoleResponse]:
    """List workspaces the authenticated user belongs to."""
    workspaces = await workspace_service.list_user_workspaces(
        db=db,
        user_id=current_user.id,
    )
    return [WorkspaceWithRoleResponse.model_validate(ws) for ws in workspaces]


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workspace details",
    description="Retrieve workspace details. Only workspace members have access; returns 404 for non-members.",
)
async def get_workspace_details(
    context: Tuple[Workspace, WorkspaceMember] = Depends(require_workspace_member),
) -> WorkspaceResponse:
    """Get details of a specific workspace."""
    workspace, _ = context
    return WorkspaceResponse.model_validate(workspace)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workspace",
    description="Update workspace information. Only authorized OWNER and ADMIN members have access.",
)
async def update_workspace(
    data: WorkspaceUpdate,
    context: Tuple[Workspace, WorkspaceMember] = Depends(
        require_workspace_admin_or_owner
    ),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Update workspace details."""
    workspace, _ = context
    updated = await workspace_service.update_workspace(
        db=db,
        workspace=workspace,
        data=data,
    )
    return WorkspaceResponse.model_validate(updated)


@router.delete(
    "/{workspace_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete workspace",
    description="Permanently delete a workspace. Only the workspace OWNER can perform deletion.",
)
async def delete_workspace(
    context: Tuple[Workspace, WorkspaceMember] = Depends(require_workspace_owner),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a workspace and cascade-delete its resources."""
    workspace, _ = context
    await workspace_service.delete_workspace(db=db, workspace=workspace)
    return MessageResponse(message="Workspace deleted successfully.")


@router.get(
    "/{workspace_id}/members",
    response_model=List[WorkspaceMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List workspace members",
    description="Return all members of a workspace. Only workspace members can view the member list.",
)
async def list_workspace_members(
    context: Tuple[Workspace, WorkspaceMember] = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> List[WorkspaceMemberResponse]:
    """List members of a workspace."""
    workspace, _ = context
    members = await workspace_service.list_members(
        db=db,
        workspace_id=workspace.id,
    )
    return [WorkspaceMemberResponse.model_validate(m) for m in members]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add or invite member to workspace",
    description="Add an existing registered user to the workspace. Accessible by OWNER and ADMIN.",
)
async def add_workspace_member(
    data: WorkspaceMemberCreate,
    context: Tuple[Workspace, WorkspaceMember] = Depends(
        require_workspace_admin_or_owner
    ),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceMemberResponse:
    """Add a registered user to the workspace."""
    workspace, acting_member = context
    new_member = await workspace_service.add_member(
        db=db,
        workspace=workspace,
        acting_member=acting_member,
        data=data,
    )
    return WorkspaceMemberResponse.model_validate(new_member)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Update member role",
    description="Change a member's role in the workspace. Protected against unauthorized privilege escalation or demoting sole owners.",
)
async def update_member_role(
    user_id: uuid.UUID,
    data: WorkspaceMemberUpdate,
    context: Tuple[Workspace, WorkspaceMember] = Depends(
        require_workspace_admin_or_owner
    ),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceMemberResponse:
    """Update role for a workspace member."""
    workspace, acting_member = context
    updated_member = await workspace_service.update_member_role(
        db=db,
        workspace=workspace,
        acting_member=acting_member,
        target_user_id=user_id,
        data=data,
    )
    return WorkspaceMemberResponse.model_validate(updated_member)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove member or leave workspace",
    description="Remove a member from the workspace or leave the workspace (self-removal). Sole owners cannot leave.",
)
async def remove_workspace_member(
    user_id: uuid.UUID,
    context: Tuple[Workspace, WorkspaceMember] = Depends(
        get_workspace_and_membership
    ),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove a member or leave workspace."""
    workspace, acting_member = context
    await workspace_service.remove_member(
        db=db,
        workspace=workspace,
        acting_member=acting_member,
        target_user_id=user_id,
    )
    return MessageResponse(message="Member removed from workspace successfully.")


@router.get(
    "/{workspace_id}/transcripts/search",
    response_model=TranscriptSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search transcripts across workspace",
    description="Full-text search across all meeting transcripts and segments within a workspace.",
)
async def search_workspace_transcripts(
    workspace_id: uuid.UUID,
    q: str = Query(..., min_length=1, description="Search term to match against segment text"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Result offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptSearchResponse:
    """Search transcripts across a workspace."""
    return await TranscriptionService.search_workspace_transcripts(
        db=db,
        workspace_id=workspace_id,
        query=q,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
