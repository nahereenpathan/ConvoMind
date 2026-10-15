"""Meeting and Participant request and response schemas."""

import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import MeetingStatus


class ParticipantCreate(BaseModel):
    """Payload to add a participant to a meeting."""

    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Full name of participant",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address of participant",
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Registered user UUID if participant is an internal user",
    )
    role: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Role in the meeting (e.g. 'host', 'attendee', 'guest')",
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: Optional[EmailStr]) -> Optional[str]:
        if v is not None:
            return str(v).strip().lower()
        return None

    @field_validator("name", mode="after")
    @classmethod
    def normalize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return None

    @model_validator(mode="after")
    def validate_has_identifier(self) -> "ParticipantCreate":
        if not self.name and not self.email and not self.user_id:
            raise ValueError(
                "At least one of 'name', 'email', or 'user_id' must be provided."
            )
        return self


class ParticipantResponse(BaseModel):
    """Public representation of a meeting participant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    joined_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
    created_at: datetime


class MeetingCreate(BaseModel):
    """Meeting creation payload."""

    workspace_id: uuid.UUID = Field(
        ...,
        description="UUID of the workspace the meeting belongs to",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title of the meeting",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Meeting agenda or description",
    )
    meeting_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Type of meeting (e.g. '1on1', 'standup', 'planning', 'interview')",
    )
    status: MeetingStatus = Field(
        default=MeetingStatus.SCHEDULED,
        description="Initial lifecycle status",
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="Scheduled meeting start time",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Actual meeting start time",
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="Actual meeting end time",
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Duration of meeting in seconds",
    )
    source_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Platform or capture source (e.g. 'zoom', 'google_meet', 'upload')",
    )
    recording_url: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Public/accessible URL of recording",
    )
    recording_key: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Internal object store key for recording",
    )

    @field_validator("title", mode="after")
    @classmethod
    def normalize_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Meeting title cannot be empty or whitespace only.")
        return trimmed

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v: Any) -> MeetingStatus:
        if isinstance(v, MeetingStatus):
            return v
        if isinstance(v, str):
            clean = v.strip().upper()
            try:
                return MeetingStatus(clean)
            except ValueError:
                valid_states = [s.value for s in MeetingStatus]
                raise ValueError(
                    f"Invalid meeting status '{v}'. Valid statuses are: {valid_states}"
                )
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "MeetingCreate":
        if self.started_at and self.ended_at:
            if self.ended_at < self.started_at:
                raise ValueError("ended_at cannot be earlier than started_at.")
        return self


class MeetingUpdate(BaseModel):
    """Meeting update payload."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated meeting title",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Updated meeting description",
    )
    meeting_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated meeting type",
    )
    status: Optional[MeetingStatus] = Field(
        default=None,
        description="Updated lifecycle status",
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="Updated scheduled start time",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Updated actual start time",
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="Updated actual end time",
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Updated duration in seconds",
    )
    source_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Updated capture source",
    )
    recording_url: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Updated recording URL",
    )
    recording_key: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Updated storage key",
    )

    @field_validator("title", mode="after")
    @classmethod
    def normalize_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Meeting title cannot be empty or whitespace only.")
            return trimmed
        return None

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v: Any) -> Optional[MeetingStatus]:
        if v is None or isinstance(v, MeetingStatus):
            return v
        if isinstance(v, str):
            clean = v.strip().upper()
            try:
                return MeetingStatus(clean)
            except ValueError:
                valid_states = [s.value for s in MeetingStatus]
                raise ValueError(
                    f"Invalid meeting status '{v}'. Valid statuses are: {valid_states}"
                )
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "MeetingUpdate":
        if self.started_at and self.ended_at:
            if self.ended_at < self.started_at:
                raise ValueError("ended_at cannot be earlier than started_at.")
        return self


class MeetingResponse(BaseModel):
    """Complete public representation of a meeting."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    creator_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = Field(
        default=None,
        validation_alias=AliasChoices("created_by", "creator_id"),
        description="User UUID of meeting creator",
    )
    title: str
    description: Optional[str] = None
    meeting_type: Optional[str] = None
    status: MeetingStatus
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    source_type: Optional[str] = None
    recording_url: Optional[str] = None
    recording_key: Optional[str] = None
    is_native: bool = False
    room_id: Optional[str] = None
    room_provider: Optional[str] = None
    room_status: Optional[str] = None
    deleted_at: Optional[datetime] = None
    deleted_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    """Paginated meetings list response with metadata."""

    items: List[MeetingResponse]
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Page size limit")
    total: int = Field(..., ge=0, description="Total matching meetings count")
    total_pages: int = Field(..., ge=0, description="Total available pages")


class NativeRoomInitResponse(BaseModel):
    """Response returned upon native meeting room initialization."""

    meeting_id: uuid.UUID
    room_id: str
    room_provider: str
    room_status: str
    is_native: bool


class JoinRoomResponse(BaseModel):
    """Response payload returned when a participant joins a native room."""

    meeting_id: uuid.UUID
    room_id: str
    ws_url: str
    token: str
    is_host: bool
    participant_identity: str
    participant_name: str
    room_status: str


class RoomStatusResponse(BaseModel):
    """Live status and participant presence summary for a native meeting room."""

    meeting_id: uuid.UUID
    room_id: str
    room_status: str
    is_native: bool
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    active_participants_count: int
    participants: List[ParticipantResponse]


class MeetingMessageCreate(BaseModel):
    """Payload for sending a new in-meeting chat message."""

    message: str = Field(..., min_length=1, max_length=1000, description="Chat message body")


class MeetingMessageResponse(BaseModel):
    """Response returned for an in-meeting chat message."""

    id: uuid.UUID
    meeting_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    sender_name: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class NativeRecordingStartResponse(BaseModel):
    """Response payload when host starts native meeting recording."""

    meeting_id: uuid.UUID
    recording_id: uuid.UUID
    status: str
    started_at: datetime
    message: str


class NativeRecordingStopResponse(BaseModel):
    """Response payload when host stops native meeting recording."""

    meeting_id: uuid.UUID
    recording_id: uuid.UUID
    status: str
    duration_seconds: Optional[int] = None
    file_size: int
    message: str


class ParticipantModerationResponse(BaseModel):
    """Response payload returned upon host moderation action (mute/kick)."""

    meeting_id: uuid.UUID
    participant_id: uuid.UUID
    action: str
    message: str



