"""Meeting recording request and response schemas."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import RecordingStatus


class RecordingResponse(BaseModel):
    """Public representation of an uploaded meeting recording."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    workspace_id: uuid.UUID
    uploaded_by: Optional[uuid.UUID] = Field(
        default=None,
        validation_alias=AliasChoices("uploaded_by", "uploaded_by_id"),
        description="User UUID who uploaded the recording",
    )
    filename: str = Field(
        ...,
        validation_alias=AliasChoices("filename", "original_filename"),
        description="Original name of the uploaded file",
    )
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME content type")
    duration_seconds: Optional[int] = Field(
        default=None,
        description="Audio/video duration in seconds",
    )
    status: RecordingStatus = Field(..., description="Current processing lifecycle status")
    checksum: Optional[str] = Field(
        default=None,
        description="SHA-256 integrity hash",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Failure details if status is FAILED",
    )
    created_at: datetime
    updated_at: datetime


class RecordingListResponse(BaseModel):
    """List of meeting recordings."""

    items: List[RecordingResponse]
    total: int = Field(..., ge=0, description="Total recordings for the meeting")
