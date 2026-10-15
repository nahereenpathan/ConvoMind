"""Workspace management business logic and lifecycle service."""

import re
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceUpdate,
)


class WorkspaceService:
    """Service handling workspace CRUD, member management, and role-based policies."""

    @staticmethod
    async def generate_unique_slug(
        db: AsyncSession,
        name: str,
        custom_slug: Optional[str] = None,
    ) -> str:
        """Generate or validate a URL-safe, unique slug for a workspace."""
        if custom_slug:
            slug = custom_slug.strip().lower()
            stmt = select(Workspace.id).where(Workspace.slug == slug)
            result = await db.execute(stmt)
            if result.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Workspace slug '{slug}' is already in use.",
                )
            return slug

        # Generate slug from workspace name
        base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not base_slug:
            base_slug = "workspace"
        base_slug = base_slug[:80]

        candidate = base_slug
        counter = 1

        while True:
            stmt = select(Workspace.id).where(Workspace.slug == candidate)
            result = await db.execute(stmt)
            if result.scalar_one_or_none() is None:
                return candidate
            counter += 1
            if counter > 50:
                # Fallback to random hex suffix if sequential collisions exceed 50
                candidate = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            else:
                candidate = f"{base_slug}-{counter}"

    @staticmethod
    async def create_workspace(
        db: AsyncSession,
        current_user: User,
        data: WorkspaceCreate,
    ) -> Workspace:
        """Create a new workspace and automatically assign the creator as OWNER."""
        slug = await WorkspaceService.generate_unique_slug(
            db=db,
            name=data.name,
            custom_slug=data.slug,
        )

        workspace = Workspace(
            name=data.name,
            slug=slug,
            description=data.description,
            logo_url=data.logo_url,
            created_by_id=current_user.id,
        )
        db.add(workspace)
        await db.flush()  # Obtain workspace.id for foreign key

        owner_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.OWNER,
        )
        db.add(owner_member)
        await db.commit()
        await db.refresh(workspace)
        return workspace

    @staticmethod
    async def list_user_workspaces(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Retrieve all workspaces where the given user is an active member."""
        stmt = (
            select(Workspace, WorkspaceMember.role, WorkspaceMember.joined_at)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        workspaces = []
        for ws, role, joined_at in rows:
            workspaces.append(
                {
                    "id": ws.id,
                    "name": ws.name,
                    "slug": ws.slug,
                    "description": ws.description,
                    "logo_url": ws.logo_url,
                    "created_by_id": ws.created_by_id,
                    "created_at": ws.created_at,
                    "updated_at": ws.updated_at,
                    "role": role,
                    "joined_at": joined_at,
                }
            )
        return workspaces

    @staticmethod
    async def get_workspace_by_id(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Workspace:
        """Retrieve workspace by ID. If user_id is provided, enforces membership access."""
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await db.execute(stmt)
        workspace = result.scalar_one_or_none()

        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

        if user_id is not None:
            member_stmt = select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            member_result = await db.execute(member_stmt)
            if member_result.scalar_one_or_none() is None:
                # Obfuscate workspace existence for non-members to prevent IDOR & enumeration
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found.",
                )

        return workspace

    @staticmethod
    async def update_workspace(
        db: AsyncSession,
        workspace: Workspace,
        data: WorkspaceUpdate,
    ) -> Workspace:
        """Update workspace attributes."""
        if data.name is not None:
            workspace.name = data.name

        if data.description is not None:
            workspace.description = data.description

        if data.logo_url is not None:
            workspace.logo_url = data.logo_url

        if data.slug is not None and data.slug != workspace.slug:
            new_slug = await WorkspaceService.generate_unique_slug(
                db=db,
                name=data.slug,
                custom_slug=data.slug,
            )
            workspace.slug = new_slug

        await db.commit()
        await db.refresh(workspace)
        return workspace

    @staticmethod
    async def delete_workspace(
        db: AsyncSession,
        workspace: Workspace,
    ) -> None:
        """Permanently delete a workspace and cascade-delete its members and entities."""
        await db.delete(workspace)
        await db.commit()

    @staticmethod
    async def list_members(
        db: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> List[WorkspaceMember]:
        """List all members belonging to the specified workspace with user profile details."""
        stmt = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def add_member(
        db: AsyncSession,
        workspace: Workspace,
        acting_member: WorkspaceMember,
        data: WorkspaceMemberCreate,
    ) -> WorkspaceMember:
        """Add an existing registered user to the workspace with role checks."""
        # 1. Authorization checks
        if acting_member.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions. Only workspace owners and admins can add members.",
            )

        if acting_member.role == WorkspaceRole.ADMIN:
            if data.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot assign OWNER or ADMIN roles. Only workspace owners can do so.",
                )

        # 2. Look up target user by normalized email
        stmt = select(User).where(User.email == data.email)
        res = await db.execute(stmt)
        target_user = res.scalar_one_or_none()

        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email '{data.email}' not found. The user must register an account first.",
            )

        # 3. Check for duplicate membership
        member_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user.id,
        )
        existing_res = await db.execute(member_stmt)
        if existing_res.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this workspace.",
            )

        # 4. Create membership
        new_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=target_user.id,
            role=data.role,
        )
        db.add(new_member)
        await db.commit()

        # Eager load user relationship for response
        reloaded_stmt = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.id == new_member.id)
        )
        reloaded_res = await db.execute(reloaded_stmt)
        return reloaded_res.scalar_one()

    @staticmethod
    async def update_member_role(
        db: AsyncSession,
        workspace: Workspace,
        acting_member: WorkspaceMember,
        target_user_id: uuid.UUID,
        data: WorkspaceMemberUpdate,
    ) -> WorkspaceMember:
        """Update a member's role with strict protections for OWNER and ADMIN roles."""
        # 1. Base authorization check
        if acting_member.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions. Only workspace owners and admins can update member roles.",
            )

        # 2. Retrieve target member
        stmt = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == target_user_id,
            )
        )
        res = await db.execute(stmt)
        target_member = res.scalar_one_or_none()

        if target_member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found.",
            )

        # 3. Hierarchy and role protection rules
        if target_member.role == WorkspaceRole.OWNER:
            if acting_member.role != WorkspaceRole.OWNER:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot modify or demote the workspace owner.",
                )

            # Check if this owner is the sole owner and trying to demote
            if data.role != WorkspaceRole.OWNER:
                owner_count_stmt = select(func.count(WorkspaceMember.id)).where(
                    WorkspaceMember.workspace_id == workspace.id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                )
                count_res = await db.execute(owner_count_stmt)
                owner_count = count_res.scalar_one()
                if owner_count <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot demote the sole workspace owner. Please transfer ownership or assign another owner first.",
                    )

        if target_member.role == WorkspaceRole.ADMIN and acting_member.role == WorkspaceRole.ADMIN:
            if acting_member.user_id != target_member.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot modify fellow admin roles. Only workspace owners can do so.",
                )

        if data.role == WorkspaceRole.OWNER and acting_member.role != WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot promote members to owner.",
            )

        if data.role == WorkspaceRole.ADMIN and acting_member.role == WorkspaceRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot promote members to admin.",
            )

        # 4. Apply role change
        target_member.role = data.role
        await db.commit()
        await db.refresh(target_member)
        return target_member

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        workspace: Workspace,
        acting_member: WorkspaceMember,
        target_user_id: uuid.UUID,
    ) -> None:
        """Remove a member from the workspace with self-removal rules and owner protection."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user_id,
        )
        res = await db.execute(stmt)
        target_member = res.scalar_one_or_none()

        if target_member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found.",
            )

        # Case A: Self-removal (user leaving the workspace)
        if target_user_id == acting_member.user_id:
            if acting_member.role == WorkspaceRole.OWNER:
                owner_count_stmt = select(func.count(WorkspaceMember.id)).where(
                    WorkspaceMember.workspace_id == workspace.id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                )
                count_res = await db.execute(owner_count_stmt)
                owner_count = count_res.scalar_one()
                if owner_count <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The sole workspace owner cannot leave the workspace. You must transfer ownership or delete the workspace.",
                    )
            await db.delete(target_member)
            await db.commit()
            return

        # Case B: Removing another member
        if acting_member.role in (WorkspaceRole.MEMBER, WorkspaceRole.GUEST):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Regular members cannot remove other members.",
            )

        if target_member.role == WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The workspace owner cannot be removed.",
            )

        if acting_member.role == WorkspaceRole.ADMIN:
            if target_member.role == WorkspaceRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot remove other admins. Only the workspace owner can remove admins.",
                )

        await db.delete(target_member)
        await db.commit()


workspace_service = WorkspaceService()
