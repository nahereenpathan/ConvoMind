"""Meeting speaker management API routes."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.transcript import (
    SpeakerCreate,
    SpeakerResponse,
    SpeakerUpdate,
)
from app.services.speaker_service import SpeakerService

router = APIRouter()


@router.get(
    "",
    response_model=List[SpeakerResponse],
    status_code=status.HTTP_200_OK,
    summary="List meeting speakers",
    description="Retrieve all identified speakers tagged in this meeting.",
)
async def list_speakers(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SpeakerResponse]:
    """List meeting speakers."""
    speakers = await SpeakerService.list_speakers(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )
    return [SpeakerResponse.model_validate(s) for s in speakers]


@router.post(
    "/diarize",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger speaker diarization",
    description="Queue an asynchronous Celery task to identify speakers and align transcript segments.",
)
async def trigger_diarization(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger speaker diarization task for meeting recording."""
    return await SpeakerService.trigger_diarization(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )


@router.post(
    "",
    response_model=SpeakerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create meeting speaker",
    description="Register a new speaker identity for a meeting (optionally linked to a workspace member).",
)
async def create_speaker(
    meeting_id: uuid.UUID,
    data: SpeakerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpeakerResponse:
    """Create a speaker for a meeting."""
    speaker = await SpeakerService.create_speaker(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        data=data,
    )
    return SpeakerResponse.model_validate(speaker)


@router.get(
    "/{speaker_id}",
    response_model=SpeakerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get speaker details",
    description="Retrieve a specific speaker identity by ID.",
)
async def get_speaker(
    meeting_id: uuid.UUID,
    speaker_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpeakerResponse:
    """Get speaker details."""
    speaker = await SpeakerService.get_speaker(
        db=db,
        meeting_id=meeting_id,
        speaker_id=speaker_id,
        current_user=current_user,
    )
    return SpeakerResponse.model_validate(speaker)


@router.patch(
    "/{speaker_id}",
    response_model=SpeakerResponse,
    status_code=status.HTTP_200_OK,
    summary="Update speaker",
    description="Update speaker label, display name, or user link.",
)
async def update_speaker(
    meeting_id: uuid.UUID,
    speaker_id: uuid.UUID,
    data: SpeakerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpeakerResponse:
    """Update speaker details."""
    speaker = await SpeakerService.update_speaker(
        db=db,
        meeting_id=meeting_id,
        speaker_id=speaker_id,
        current_user=current_user,
        data=data,
    )
    return SpeakerResponse.model_validate(speaker)


@router.delete(
    "/{speaker_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete speaker",
    description="Delete a speaker identity from a meeting. Associated segments will have speaker_id unlinked.",
)
async def delete_speaker(
    meeting_id: uuid.UUID,
    speaker_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a speaker identity."""
    await SpeakerService.delete_speaker(
        db=db,
        meeting_id=meeting_id,
        speaker_id=speaker_id,
        current_user=current_user,
    )
    return MessageResponse(message="Speaker deleted successfully.")
