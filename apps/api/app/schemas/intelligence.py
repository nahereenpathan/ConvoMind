"""Pydantic DTO schemas for meeting intelligence, summaries, decisions, action items, and questions."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ActionItemStatus, IntelligenceStatus, PriorityLevel, QuestionStatus


# ---------------------------------------------------------------------------
# Decision Schemas
# ---------------------------------------------------------------------------

class DecisionResponse(BaseModel):
    """Public representation of an extracted or user-managed meeting decision."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    meeting_id: uuid.UUID
    title: str
    context: Optional[str] = None
    impact: Optional[str] = None
    timestamp_marker: Optional[float] = None
    source_segment_id: Optional[uuid.UUID] = None
    version: int = 1
    created_by_id: Optional[uuid.UUID] = None
    updated_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    @property
    def description(self) -> str:
        """Alias for title for backward compatibility."""
        return self.title


class DecisionCreate(BaseModel):
    """Payload to create a new decision manually."""

    title: str = Field(..., min_length=1, max_length=500, description="Summary of the decision reached")
    context: Optional[str] = Field(None, description="Background or context leading to the decision")
    impact: Optional[str] = Field(None, description="Expected outcome or organizational impact")
    timestamp_marker: Optional[float] = Field(None, description="Optional offset in seconds within the audio/video")
    source_segment_id: Optional[uuid.UUID] = Field(None, description="Optional transcript segment UUID")


class DecisionUpdate(BaseModel):
    """Payload to update an existing decision."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    context: Optional[str] = None
    impact: Optional[str] = None
    timestamp_marker: Optional[float] = None
    source_segment_id: Optional[uuid.UUID] = None


class DecisionListResponse(BaseModel):
    """Paginated list envelope for decisions."""

    items: List[DecisionResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Action Item Schemas
# ---------------------------------------------------------------------------

class ActionItemResponse(BaseModel):
    """Public representation of an extracted or user-managed action item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    meeting_id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = None
    assignee_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: ActionItemStatus
    priority: PriorityLevel
    timestamp_marker: Optional[float] = None
    source_segment_id: Optional[uuid.UUID] = None
    version: int = 1
    completed_at: Optional[datetime] = None
    created_by_id: Optional[uuid.UUID] = None
    meeting_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ActionItemCreate(BaseModel):
    """Payload to create a new action item."""

    title: str = Field(..., min_length=1, max_length=500, description="Task title or commitment description")
    description: Optional[str] = Field(None, description="Detailed instructions or context")
    assignee_id: Optional[uuid.UUID] = Field(None, description="Workspace member user UUID to assign this task")
    assignee_name: Optional[str] = Field(None, description="Display name or label for the assignee")
    due_date: Optional[datetime] = Field(None, description="Target completion datetime")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="LOW, MEDIUM, HIGH, or URGENT")
    status: Optional[ActionItemStatus] = Field(default=ActionItemStatus.OPEN, description="OPEN, IN_PROGRESS, COMPLETED, or CANCELLED")
    timestamp_marker: Optional[float] = Field(None, description="Optional offset in seconds")
    source_segment_id: Optional[uuid.UUID] = Field(None, description="Optional transcript segment UUID")

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.upper().strip()
            if v_upper == "TODO":
                return ActionItemStatus.OPEN
            if v_upper in ActionItemStatus.__members__:
                return ActionItemStatus[v_upper]
        return v


class ActionItemUpdate(BaseModel):
    """Payload to update an existing action item."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    assignee_name: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[PriorityLevel] = None
    status: Optional[ActionItemStatus] = None
    timestamp_marker: Optional[float] = None
    source_segment_id: Optional[uuid.UUID] = None

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.upper().strip()
            if v_upper == "TODO":
                return ActionItemStatus.OPEN
            if v_upper in ActionItemStatus.__members__:
                return ActionItemStatus[v_upper]
        return v


class ActionItemListResponse(BaseModel):
    """Paginated list envelope for action items."""

    items: List[ActionItemResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Meeting Question Schemas
# ---------------------------------------------------------------------------

class MeetingQuestionResponse(BaseModel):
    """Public representation of a question raised during a meeting."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    meeting_id: uuid.UUID
    asked_by_speaker_id: Optional[uuid.UUID] = None
    asked_by_speaker_name: Optional[str] = None
    question: str
    answer: Optional[str] = None
    context: Optional[str] = None
    status: QuestionStatus
    is_resolved: bool
    timestamp_marker: Optional[float] = None
    source_segment_id: Optional[uuid.UUID] = None
    version: int = 1
    created_by_id: Optional[uuid.UUID] = None
    updated_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    @property
    def question_text(self) -> str:
        """Alias for question for backward compatibility."""
        return self.question


class MeetingQuestionCreate(BaseModel):
    """Payload to create a meeting question manually."""

    question: str = Field(..., min_length=1, description="Question text")
    answer: Optional[str] = Field(None, description="Answer provided during the meeting or afterwards")
    context: Optional[str] = Field(None, description="Discussion context surrounding the question")
    asked_by_speaker_id: Optional[uuid.UUID] = Field(None, description="Speaker UUID who asked")
    asked_by_speaker_name: Optional[str] = Field(None, description="Name or label of speaker who asked")
    status: Optional[QuestionStatus] = Field(default=QuestionStatus.OPEN, description="OPEN, ANSWERED, or DISMISSED")
    is_resolved: Optional[bool] = Field(None, description="Whether the question was resolved")
    timestamp_marker: Optional[float] = Field(None, description="Optional offset in seconds")
    source_segment_id: Optional[uuid.UUID] = Field(None, description="Optional transcript segment UUID")

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.upper().strip()
            if v_upper in QuestionStatus.__members__:
                return QuestionStatus[v_upper]
        return v


class MeetingQuestionUpdate(BaseModel):
    """Payload to update an existing meeting question."""

    question: Optional[str] = Field(None, min_length=1)
    answer: Optional[str] = None
    context: Optional[str] = None
    asked_by_speaker_id: Optional[uuid.UUID] = None
    asked_by_speaker_name: Optional[str] = None
    status: Optional[QuestionStatus] = None
    is_resolved: Optional[bool] = None
    timestamp_marker: Optional[float] = None
    source_segment_id: Optional[uuid.UUID] = None

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.upper().strip()
            if v_upper in QuestionStatus.__members__:
                return QuestionStatus[v_upper]
        return v


class MeetingQuestionListResponse(BaseModel):
    """Paginated list envelope for meeting questions."""

    items: List[MeetingQuestionResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Summary & Intelligence Job Schemas
# ---------------------------------------------------------------------------

class MeetingSummaryResponse(BaseModel):
    """Public representation of AI-generated executive and detailed summaries."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    meeting_id: uuid.UUID
    overview: str = Field(..., description="Executive summary")
    detailed_summary: Optional[str] = None
    key_points: Optional[List[Dict[str, Any]]] = None
    next_steps: Optional[List[Dict[str, Any]]] = None
    risks_and_concerns: Optional[List[Dict[str, Any]]] = None
    requirements_and_notes: Optional[List[Dict[str, Any]]] = None
    follow_up_suggestions: Optional[List[Dict[str, Any]]] = None
    model_used: Optional[str] = None
    provider: Optional[str] = None
    prompt_version: Optional[str] = None
    processing_duration: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None
    version: int = 1
    created_at: datetime

    @property
    def summary_text(self) -> str:
        """Alias for overview for backward compatibility."""
        return self.overview


class IntelligenceJobResponse(BaseModel):
    """Public representation of an AI intelligence processing task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    workspace_id: uuid.UUID
    status: IntelligenceStatus
    provider: str
    model: str
    version: int
    processing_duration: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MeetingIntelligenceResponse(BaseModel):
    """Consolidated bundle of all meeting intelligence entities for a meeting version."""

    meeting_id: uuid.UUID
    workspace_id: uuid.UUID
    version: int
    job: IntelligenceJobResponse
    summary: Optional[MeetingSummaryResponse] = None
    decisions: List[DecisionResponse] = Field(default_factory=list)
    action_items: List[ActionItemResponse] = Field(default_factory=list)
    questions: List[MeetingQuestionResponse] = Field(default_factory=list)
