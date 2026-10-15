"""Pydantic schemas for vector embedding operations and semantic search."""

from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class EmbeddingProcessResponse(BaseModel):
    """Response returned when triggering an embedding process job."""

    status: str = Field(..., description="Job status indicator ('queued', 'completed', etc.)")
    meeting_id: uuid.UUID = Field(..., description="Target meeting UUID")
    transcript_id: Optional[uuid.UUID] = Field(None, description="Target transcript UUID")
    task_id: Optional[str] = Field(None, description="Celery task ID")
    message: str = Field(..., description="Human-readable status summary")


class EmbeddingStatusResponse(BaseModel):
    """Response describing vector embedding status for a meeting transcript."""

    meeting_id: uuid.UUID
    transcript_id: Optional[uuid.UUID]
    is_embedded: bool
    chunk_count: int
    provider: Optional[str]
    model: Optional[str]
    dimension: Optional[int]
    last_updated_at: Optional[datetime]


class VectorSearchRequest(BaseModel):
    """Request payload for semantic vector search."""

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language search query")
    meeting_id: Optional[uuid.UUID] = Field(None, description="Optional meeting UUID filter")
    top_k: int = Field(10, ge=1, le=50, description="Maximum number of search results to return")
    score_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Minimum similarity score threshold (0.0 to 1.0)"
    )


class VectorSearchResultItem(BaseModel):
    """Single semantic search result item."""

    embedding_id: uuid.UUID
    workspace_id: uuid.UUID
    meeting_id: uuid.UUID
    transcript_id: uuid.UUID
    start_segment_id: Optional[uuid.UUID]
    end_segment_id: Optional[uuid.UUID]
    chunk_index: int
    content: str
    similarity_score: float
    distance: float
    start_time: Optional[float]
    end_time: Optional[float]
    speaker_labels: List[str] = Field(default_factory=list)
    provider: str
    model: str


class VectorSearchResponse(BaseModel):
    """Response wrapper for vector semantic search results."""

    workspace_id: uuid.UUID
    query: str
    total_results: int
    results: List[VectorSearchResultItem]
