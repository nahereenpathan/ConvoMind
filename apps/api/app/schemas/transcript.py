"""Pydantic schemas for transcripts, transcript segments, speakers, search, and export."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TranscriptStatus


# --- Speaker Schemas ---


class SpeakerCreate(BaseModel):
    """Schema for creating a speaker identity in a meeting."""

    label: str = Field(..., min_length=1, max_length=100, description="Speaker identifier, e.g. 'Speaker 1' or 'SPEAKER_00'")
    name: Optional[str] = Field(default=None, max_length=255, description="Display name, e.g. 'Alice Smith'")
    user_id: Optional[uuid.UUID] = Field(default=None, description="Optional associated workspace user ID")


class SpeakerUpdate(BaseModel):
    """Schema for updating a speaker's identity or label."""

    label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    name: Optional[str] = Field(default=None, max_length=255)
    user_id: Optional[uuid.UUID] = Field(default=None)


class SpeakerResponse(BaseModel):
    """Public representation of a meeting speaker."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    label: str
    name: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


# --- Transcript Segment Schemas ---


class TranscriptSegmentResponse(BaseModel):
    """Public representation of an individual transcribed speech segment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transcript_id: uuid.UUID
    sequence_order: int = Field(..., description="0-indexed sequential order of the utterance")
    start_time: float = Field(..., description="Start offset in seconds")
    end_time: float = Field(..., description="End offset in seconds")
    text: str = Field(..., description="Spoken text in the segment")
    confidence: Optional[float] = Field(default=None, description="Confidence score between 0.0 and 1.0")
    speaker_id: Optional[uuid.UUID] = Field(default=None, description="Speaker entity UUID if tagged")
    speaker: Optional[SpeakerResponse] = Field(default=None, description="Speaker details if loaded")
    created_at: datetime
    updated_at: datetime


class TranscriptSegmentCreate(BaseModel):
    """Schema for inserting a new segment into a transcript."""

    sequence_order: Optional[int] = Field(
        default=None,
        ge=0,
        description="Position to insert. If omitted, appends to the end of the transcript.",
    )
    start_time: float = Field(..., ge=0.0, description="Start offset in seconds")
    end_time: float = Field(..., ge=0.0, description="End offset in seconds")
    text: str = Field(..., min_length=1, description="Utterance text")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    speaker_id: Optional[uuid.UUID] = Field(default=None)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "TranscriptSegmentCreate":
        if self.end_time < self.start_time:
            raise ValueError("end_time cannot be less than start_time")
        return self


class TranscriptSegmentUpdate(BaseModel):
    """Schema for updating an existing transcript segment."""

    text: Optional[str] = Field(default=None, min_length=1)
    start_time: Optional[float] = Field(default=None, ge=0.0)
    end_time: Optional[float] = Field(default=None, ge=0.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    speaker_id: Optional[uuid.UUID] = Field(default=None)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "TranscriptSegmentUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time cannot be less than start_time")
        return self


class TranscriptSegmentBatchSpeaker(BaseModel):
    """Schema for assigning a speaker to multiple segments in bulk."""

    segment_ids: List[uuid.UUID] = Field(
        ..., min_length=1, description="List of segment UUIDs to update"
    )
    speaker_id: Optional[uuid.UUID] = Field(
        default=None, description="Speaker UUID to assign (or null to unassign)"
    )


class SegmentListResponse(BaseModel):
    """Paginated list of transcript segments."""

    transcript_id: uuid.UUID
    meeting_id: uuid.UUID
    total_segments: int
    page: int
    page_size: int
    segments: List[TranscriptSegmentResponse]


# --- Transcript Schemas ---


class TranscriptUpdate(BaseModel):
    """Schema for updating transcript metadata."""

    language: Optional[str] = Field(default=None, min_length=2, max_length=50)


class TranscriptResponse(BaseModel):
    """Public representation of a meeting transcript."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    recording_id: Optional[uuid.UUID] = Field(default=None, description="Associated recording UUID")
    workspace_id: Optional[uuid.UUID] = Field(default=None, description="Associated workspace UUID")
    status: TranscriptStatus = Field(..., description="Transcription lifecycle status")
    language: str = Field(..., description="Detected or configured BCP-47 language tag")
    full_text: Optional[str] = Field(default=None, description="Complete concatenated transcript text")
    word_count: int = Field(default=0, description="Total word count")
    confidence_score: Optional[float] = Field(default=None, description="Overall transcript confidence")
    duration: Optional[float] = Field(default=None, description="Transcribed audio duration in seconds")
    provider: Optional[str] = Field(default=None, description="STT provider used (e.g. 'whisper', 'mock')")
    processing_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Provider metadata and diagnostics")
    error_message: Optional[str] = Field(default=None, description="Failure reason if transcription failed")
    created_at: datetime
    updated_at: datetime


class TranscriptWithSegmentsResponse(TranscriptResponse):
    """Meeting transcript including paginated speech segments."""

    segments: List[TranscriptSegmentResponse] = Field(
        default_factory=list,
        description="Paginated list of timestamped segments",
    )
    total_segments: int = Field(default=0, description="Total number of segments in this transcript")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=100, ge=1, description="Number of segments per page")


class TranscriptStatusResponse(BaseModel):
    """Lightweight transcription status response for polling."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: uuid.UUID
    recording_id: Optional[uuid.UUID] = None
    status: TranscriptStatus
    word_count: int = 0
    duration: Optional[float] = None
    error_message: Optional[str] = None
    updated_at: datetime


class TranscriptionJobResponse(BaseModel):
    """Response returned when a transcription task is queued."""

    recording_id: uuid.UUID
    meeting_id: uuid.UUID
    status: str
    message: str


# --- Search Schemas ---


class TranscriptSearchSegmentResult(BaseModel):
    """Individual segment matching a search query."""

    segment_id: uuid.UUID
    sequence_order: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    speaker_id: Optional[uuid.UUID] = None
    speaker_name: Optional[str] = None
    speaker_label: Optional[str] = None


class TranscriptSearchResultItem(BaseModel):
    """Transcript match containing meeting context and matching segments."""

    transcript_id: uuid.UUID
    meeting_id: uuid.UUID
    meeting_title: str
    workspace_id: uuid.UUID
    language: str
    matched_segment_count: int
    matched_segments: List[TranscriptSearchSegmentResult] = Field(default_factory=list)


class TranscriptSearchResponse(BaseModel):
    """Result of searching transcripts across a workspace."""

    query: str
    total_matches: int
    results: List[TranscriptSearchResultItem] = Field(default_factory=list)
