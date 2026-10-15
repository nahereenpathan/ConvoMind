"""Meeting AI intelligence, summaries, decisions, action items, and question extraction endpoints."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.intelligence import (
    ActionItemCreate,
    ActionItemUpdate,
    ActionItemResponse,
    DecisionResponse,
    IntelligenceJobResponse,
    MeetingIntelligenceResponse,
    MeetingQuestionResponse,
    MeetingSummaryResponse,
)
from app.services.intelligence_service import IntelligenceService

router = APIRouter()


@router.post(
    "/ai/process",
    response_model=IntelligenceJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI meeting intelligence analysis",
    description="Trigger asynchronous LLM intelligence processing for a meeting with a completed transcript. Returns 202 Accepted.",
)
async def process_meeting_intelligence(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntelligenceJobResponse:
    """Queue meeting intelligence processing job."""
    job = await IntelligenceService.trigger_intelligence_processing(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )
    return IntelligenceJobResponse.model_validate(job)


@router.get(
    "/ai/status",
    response_model=IntelligenceJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI intelligence processing status",
    description="Retrieve the execution status, provider, token usage, and errors for the latest or specific intelligence job.",
)
async def get_intelligence_job_status(
    meeting_id: uuid.UUID,
    job_id: Optional[uuid.UUID] = Query(None, description="Optional job ID to inspect"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntelligenceJobResponse:
    """Get status of an intelligence processing job."""
    job = await IntelligenceService.get_intelligence_job_status(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        job_id=job_id,
    )
    return IntelligenceJobResponse.model_validate(job)


@router.get(
    "/ai",
    response_model=MeetingIntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get consolidated meeting intelligence",
    description="Retrieve all intelligence entities (job info, summary, decisions, action items, questions) for a meeting.",
)
async def get_meeting_intelligence(
    meeting_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Specific intelligence version (default: latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingIntelligenceResponse:
    """Fetch complete AI intelligence bundle for a meeting."""
    return await IntelligenceService.get_meeting_intelligence(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        version=version,
    )


@router.get(
    "/summary",
    response_model=MeetingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI meeting summary",
    description="Retrieve the executive overview, detailed summary, key points, risks, and next steps for a meeting.",
)
@router.get(
    "/ai/summary",
    response_model=MeetingSummaryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_meeting_summary(
    meeting_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Specific summary version (default: latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingSummaryResponse:
    """Fetch meeting executive summary and key points."""
    summary = await IntelligenceService.get_summary(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        version=version,
    )
    return MeetingSummaryResponse.model_validate(summary)


@router.get(
    "/decisions",
    response_model=List[DecisionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get meeting decisions",
    description="Retrieve decisions reached during the meeting along with context, impact, and transcript timestamp markers.",
)
@router.get(
    "/ai/decisions",
    response_model=List[DecisionResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_meeting_decisions(
    meeting_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Specific intelligence version (default: latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DecisionResponse]:
    """Fetch decisions extracted from the meeting transcript."""
    decisions = await IntelligenceService.get_decisions(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        version=version,
    )
    return [DecisionResponse.model_validate(d) for d in decisions]


@router.get(
    "/action-items",
    response_model=List[ActionItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get meeting action items",
    description="Retrieve assigned action items and commitments with assignee, priority, due date, and transcript timestamp markers.",
)
@router.get(
    "/ai/action-items",
    response_model=List[ActionItemResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_meeting_action_items(
    meeting_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Specific intelligence version (default: latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ActionItemResponse]:
    """Fetch action items extracted from the meeting transcript."""
    action_items = await IntelligenceService.get_action_items(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        version=version,
    )
    return [ActionItemResponse.model_validate(a) for a in action_items]


@router.get(
    "/questions",
    response_model=List[MeetingQuestionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get meeting questions",
    description="Retrieve questions asked during the meeting, their resolution status, answers, and transcript timestamp markers.",
)
@router.get(
    "/ai/questions",
    response_model=List[MeetingQuestionResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_meeting_questions(
    meeting_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Specific intelligence version (default: latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MeetingQuestionResponse]:
    """Fetch questions asked during the meeting."""
    questions = await IntelligenceService.get_questions(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        version=version,
    )
    return [MeetingQuestionResponse.model_validate(q) for q in questions]

