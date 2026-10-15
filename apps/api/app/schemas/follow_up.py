"""Pydantic schemas for AI follow-up drafts and management."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FollowUpStatus, FollowUpType


class FollowUpResponse(BaseModel):
    """Public representation of an AI-generated follow-up item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    meeting_id: uuid.UUID
    created_by_id: Optional[uuid.UUID] = None
    type: FollowUpType
    status: FollowUpStatus
    subject: str
    content: str
    recipients: Optional[List[str]] = None
    follow_up_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class FollowUpCreateRequest(BaseModel):
    """Request schema for triggering AI follow-up generation."""

    type: FollowUpType = Field(default=FollowUpType.EMAIL_DRAFT, description="Type of follow-up to generate")
    additional_instructions: Optional[str] = Field(
        default=None, max_length=1000, description="Optional custom prompt instructions for the AI"
    )


class FollowUpUpdateRequest(BaseModel):
    """Request schema for updating/editing a follow-up draft before explicit sending."""

    subject: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = Field(default=None, min_length=1)
    recipients: Optional[List[str]] = Field(default=None)
    status: Optional[FollowUpStatus] = Field(default=None)


class FollowUpEmailDraftOutput(BaseModel):
    """Structured LLM response for grounded follow-up generation."""

    subject: str = Field(..., description="Professional email subject line")
    body: str = Field(..., description="Formatted email body content summarizing meeting decisions and action items")
    recipients: List[str] = Field(default_factory=list, description="Extracted or recommended recipient names/emails")
    key_highlights: List[str] = Field(default_factory=list, description="Bullet list of main key meeting points")
