"""System telemetry and AI Engine health API endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.system import AiEngineHealthResponse
from app.services.ai_health_service import AiHealthService

router = APIRouter()


@router.get(
    "/ai-health",
    response_model=AiEngineHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI Engine Infrastructure Health Status",
    description=(
        "Retrieve real-time component operational readiness (Whisper, Diarization, "
        "AI Intelligence, RAG, Celery, Redis, PostgreSQL) and overall AI processing status. "
        "Requires authenticated user."
    ),
)
async def get_ai_engine_health(
    refresh: bool = Query(default=False, description="Force refresh health checks bypassing TTL cache"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiEngineHealthResponse:
    """Fetch backend-driven AI Engine infrastructure status."""
    return await AiHealthService.get_ai_engine_health(
        db=db,
        force_refresh=refresh,
    )
