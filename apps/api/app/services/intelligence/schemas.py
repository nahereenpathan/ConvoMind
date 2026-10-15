"""Pydantic structured output models for LLM meeting intelligence responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractedDecision(BaseModel):
    """A formal agreement or decision reached during the meeting."""

    decision: str = Field(..., description="Clear, concise description of the decision")
    context: Optional[str] = Field(default=None, description="Background or reasoning behind the decision")
    impact: Optional[str] = Field(default=None, description="Expected outcome or organizational impact")
    timestamp_marker: Optional[float] = Field(default=None, description="Audio offset in seconds where decision was reached")
    source_quote: Optional[str] = Field(default=None, description="Direct quote from transcript affirming the decision")


class ExtractedActionItem(BaseModel):
    """An assigned task, commitment, or deliverable identified in the meeting."""

    task: str = Field(..., description="Action item title or task description")
    description: Optional[str] = Field(default=None, description="Additional context or acceptance criteria")
    assignee_name: Optional[str] = Field(default=None, description="Name of person assigned if explicitly mentioned")
    due_date_str: Optional[str] = Field(default=None, description="Mentioned target due date or deadline string")
    priority: str = Field(default="MEDIUM", description="Task priority (LOW, MEDIUM, HIGH, URGENT)")
    timestamp_marker: Optional[float] = Field(default=None, description="Audio offset in seconds where task was assigned")
    source_quote: Optional[str] = Field(default=None, description="Direct transcript quote mentioning the commitment")


class ExtractedQuestion(BaseModel):
    """A question raised during discussion and its resolution status."""

    question: str = Field(..., description="Question asked during the meeting")
    answer: Optional[str] = Field(default=None, description="Answer provided during the meeting if resolved")
    is_resolved: bool = Field(default=False, description="True if an explicit answer was agreed on")
    asked_by: Optional[str] = Field(default=None, description="Name or speaker label who asked the question")
    timestamp_marker: Optional[float] = Field(default=None, description="Audio offset in seconds where question was raised")


class MeetingIntelligenceOutput(BaseModel):
    """Validated structured intelligence extracted from meeting transcripts."""

    model_config = ConfigDict(protected_namespaces=())

    executive_summary: str = Field(
        ..., description="High-level 2-4 sentence executive overview synthesizing the meeting outcomes"
    )
    detailed_summary: str = Field(
        ..., description="Comprehensive section-by-section breakdown of all topics discussed"
    )
    key_points: List[str] = Field(
        default_factory=list, description="List of primary discussion points and discoveries"
    )
    decisions: List[ExtractedDecision] = Field(
        default_factory=list, description="Formal decisions agreed upon by participants"
    )
    action_items: List[ExtractedActionItem] = Field(
        default_factory=list, description="Actionable follow-up tasks and commitments"
    )
    questions: List[ExtractedQuestion] = Field(
        default_factory=list, description="Questions raised, answers, and unresolved queries"
    )
    risks_and_concerns: List[str] = Field(
        default_factory=list, description="Identified technical, schedule, or business risks"
    )
    requirements_and_notes: List[str] = Field(
        default_factory=list, description="Important requirements, architectural notes, and constraints"
    )
    follow_up_suggestions: List[str] = Field(
        default_factory=list, description="Recommended next steps and future agenda topics"
    )
    token_usage: Optional[Dict[str, int]] = Field(
        default=None, description="Token consumption metrics (prompt, completion, total)"
    )
    model_used: Optional[str] = Field(default=None, description="LLM model identifier")
    provider: Optional[str] = Field(default=None, description="LLM provider name")
