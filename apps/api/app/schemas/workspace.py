"""Workspace and WorkspaceMember request and response schemas."""

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import WorkspaceRole
from app.schemas.user import UserResponse


class WorkspaceCreate(BaseModel):
    """Workspace creation payload."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the workspace",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional workspace description",
    )
    slug: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Optional custom URL-safe workspace slug",
    )
    logo_url: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Optional logo URL",
    )

    @field_validator("name", mode="after")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Workspace name cannot be empty or whitespace only.")
        return trimmed

    @field_validator("slug", mode="after")
    @classmethod
    def normalize_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().lower()
        return None

    @field_validator("description", mode="after")
    @classmethod
    def normalize_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return None


class WorkspaceUpdate(BaseModel):
    """Workspace update payload."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated workspace name",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Updated workspace description",
    )
    slug: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Updated workspace slug",
    )
    logo_url: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Updated logo URL",
    )

    @field_validator("name", mode="after")
    @classmethod
    def normalize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Workspace name cannot be empty or whitespace only.")
            return trimmed
        return None

    @field_validator("slug", mode="after")
    @classmethod
    def normalize_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().lower()
        return None

    @field_validator("description", mode="after")
    @classmethod
    def normalize_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return None


class WorkspaceResponse(BaseModel):
    """Public representation of a workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    created_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class WorkspaceWithRoleResponse(WorkspaceResponse):
    """Workspace details including the current user's membership role and joined date."""

    role: WorkspaceRole
    joined_at: datetime


class WorkspaceMemberCreate(BaseModel):
    """Payload to add/invite an existing user to a workspace."""

    email: EmailStr = Field(
        ...,
        description="Email address of the existing user to add",
    )
    role: WorkspaceRole = Field(
        default=WorkspaceRole.MEMBER,
        description="Role within the workspace (e.g. 'OWNER', 'ADMIN', 'MEMBER', 'GUEST')",
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Any) -> WorkspaceRole:
        if isinstance(v, WorkspaceRole):
            return v
        if isinstance(v, str):
            clean_str = v.strip().upper()
            try:
                return WorkspaceRole(clean_str)
            except ValueError:
                valid_roles = [r.value for r in WorkspaceRole]
                raise ValueError(
                    f"Invalid workspace role '{v}'. Valid roles are: {valid_roles}"
                )
        return v


class WorkspaceMemberUpdate(BaseModel):
    """Payload to update an existing member's role."""

    role: WorkspaceRole = Field(
        ...,
        description="New role to assign to the workspace member",
    )

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Any) -> WorkspaceRole:
        if isinstance(v, WorkspaceRole):
            return v
        if isinstance(v, str):
            clean_str = v.strip().upper()
            try:
                return WorkspaceRole(clean_str)
            except ValueError:
                valid_roles = [r.value for r in WorkspaceRole]
                raise ValueError(
                    f"Invalid workspace role '{v}'. Valid roles are: {valid_roles}"
                )
        return v


class WorkspaceMemberResponse(BaseModel):
    """Representation of a workspace member with associated user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: WorkspaceRole
    joined_at: datetime
    user: Optional[UserResponse] = None
