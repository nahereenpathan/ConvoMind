"""Pydantic schemas for Chat Conversations, Messages, RAG Question Answering, and Source Citations."""

from datetime import datetime
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ChatSourceCitation(BaseModel):
    """Structured source citation pointing to transcript chunk."""

    source_index: int
    meeting_id: uuid.UUID
    transcript_id: uuid.UUID
    start_segment_id: Optional[uuid.UUID] = None
    end_segment_id: Optional[uuid.UUID] = None
    meeting_title: str
    text_excerpt: str
    text: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speaker: Optional[str] = None
    speaker_labels: List[str] = Field(default_factory=list)
    similarity_score: float
    score: Optional[float] = None


class ChatConversationCreate(BaseModel):
    """Payload for creating a new chat conversation."""

    title: Optional[str] = Field(None, max_length=255, description="Optional custom conversation title")
    meeting_id: Optional[uuid.UUID] = Field(None, description="Optional meeting UUID for meeting-specific chat")


class ChatConversationResponse(BaseModel):
    """Response representing a chat conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    meeting_id: Optional[uuid.UUID] = None
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    """Payload for submitting a question to a chat conversation."""

    question: str = Field(..., min_length=1, max_length=4000, description="Natural language question text")
    top_k: int = Field(5, ge=1, le=20, description="Number of vector context chunks to retrieve")
    score_threshold: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")


class ChatMessageResponse(BaseModel):
    """Response representing an individual chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: Optional[List[ChatSourceCitation]] = None
    tokens_used: int
    created_at: datetime


class RAGQuestionResponse(BaseModel):
    """Response for RAG question execution."""

    model_config = ConfigDict(protected_namespaces=())

    conversation_id: uuid.UUID
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    sources: List[ChatSourceCitation]
    token_usage: Dict[str, int]
    model_used: str
    provider: str

