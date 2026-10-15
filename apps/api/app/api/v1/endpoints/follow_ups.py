"""AI Follow-Up endpoints handling generation, editing, and explicit human sending."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.follow_up import (
    FollowUpCreateRequest,
    FollowUpResponse,
    FollowUpUpdateRequest,
)
from app.services.follow_up_service import FollowUpService

router = APIRouter()


@router.post(
    "/meetings/{meeting_id}/follow-ups/generate",
    response_model=FollowUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI follow-up draft",
    description="Synthesize grounded AI follow-up draft (subject, body, action items) for a meeting.",
)
async def generate_follow_up(
    meeting_id: uuid.UUID,
    data: FollowUpCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowUpResponse:
    """Generate AI follow-up draft."""
    follow_up = await FollowUpService.generate_follow_up(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        data=data,
    )
    return FollowUpResponse.model_validate(follow_up)


@router.get(
    "/meetings/{meeting_id}/follow-ups",
    response_model=List[FollowUpResponse],
    status_code=status.HTTP_200_OK,
    summary="List meeting follow-ups",
    description="Retrieve all AI follow-up drafts generated for a meeting.",
)
async def list_meeting_follow_ups(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[FollowUpResponse]:
    """List meeting follow-up drafts."""
    follow_ups = await FollowUpService.list_follow_ups(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )
    return [FollowUpResponse.model_validate(f) for f in follow_ups]


@router.get(
    "/follow-ups/{follow_up_id}",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Get follow-up details",
    description="Retrieve details for a specific follow-up item.",
)
async def get_follow_up(
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowUpResponse:
    """Get follow-up details."""
    follow_up = await FollowUpService.get_follow_up(
        db=db,
        follow_up_id=follow_up_id,
        current_user=current_user,
    )
    return FollowUpResponse.model_validate(follow_up)


@router.patch(
    "/follow-ups/{follow_up_id}",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Update follow-up draft",
    description="Edit subject, content, recipients, or status of a follow-up draft before sending.",
)
async def update_follow_up(
    follow_up_id: uuid.UUID,
    data: FollowUpUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowUpResponse:
    """Update follow-up draft."""
    follow_up = await FollowUpService.update_follow_up(
        db=db,
        follow_up_id=follow_up_id,
        current_user=current_user,
        data=data,
    )
    return FollowUpResponse.model_validate(follow_up)


@router.post(
    "/follow-ups/{follow_up_id}/send",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Send follow-up email",
    description="Explicit human approval trigger to dispatch email for a follow-up draft.",
)
async def send_follow_up(
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowUpResponse:
    """Execute send for a follow-up draft upon human approval."""
    follow_up = await FollowUpService.send_follow_up(
        db=db,
        follow_up_id=follow_up_id,
        current_user=current_user,
    )
    return FollowUpResponse.model_validate(follow_up)
