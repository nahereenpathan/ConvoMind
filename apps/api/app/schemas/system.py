"""Pydantic schemas for AI Engine health status and system telemetry."""

from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ComponentHealthStatus(BaseModel):
    """Health status and metadata for an individual infrastructure or AI component."""

    status: str = Field(
        ...,
        description="Component status: 'operational', 'degraded', 'down', or 'not_configured'",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Active provider name (e.g. 'whisper', 'pyannote', 'openai', 'pgvector', 'mock')",
    )
    details: str = Field(
        ...,
        description="Safe, non-sensitive summary of component status",
    )


class AiEngineHealthResponse(BaseModel):
    """Consolidated AI Engine health status response payload."""

    overall_status: str = Field(
        ...,
        description="Overall system status: 'operational', 'degraded', 'down', or 'not_configured'",
    )
    checked_at: datetime = Field(
        ...,
        description="UTC timestamp when health check was performed",
    )
    components: Dict[str, ComponentHealthStatus] = Field(
        ...,
        description="Map of component health details (whisper, diarization, ai_intelligence, rag, celery, redis, postgresql)",
    )
