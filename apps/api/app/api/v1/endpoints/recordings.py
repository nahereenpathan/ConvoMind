"""Meeting recording upload, listing, retrieval, and deletion API routes."""

import uuid
from typing import Tuple
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.recording import RecordingListResponse, RecordingResponse
from app.schemas.transcript import TranscriptResponse, TranscriptionJobResponse
from app.services.recording_service import RecordingService
from app.services.transcription_service import TranscriptionService

router = APIRouter()


@router.post(
    "",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload meeting recording",
    description="Upload an audio or video recording file for a meeting. Validates file signature, stores safely, and queues Celery processing.",
)
async def upload_meeting_recording(
    meeting_id: uuid.UUID,
    file: UploadFile = File(..., description="Audio or video file (mp3, wav, m4a, ogg, mp4, webm, mov)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:
    """Upload audio/video recording artifact."""
    recording = await RecordingService.upload_recording(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        file=file,
    )
    return RecordingResponse.model_validate(recording)


@router.get(
    "",
    response_model=RecordingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List meeting recordings",
    description="Retrieve all recording artifacts linked to the specified meeting.",
)
async def list_meeting_recordings(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingListResponse:
    """List recordings for a meeting."""
    recordings = await RecordingService.list_recordings(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )
    return RecordingListResponse(
        items=[RecordingResponse.model_validate(r) for r in recordings],
        total=len(recordings),
    )


@router.get(
    "/{recording_id}",
    response_model=RecordingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meeting recording",
    description="Retrieve metadata and processing status for a single meeting recording.",
)
async def get_meeting_recording(
    meeting_id: uuid.UUID,
    recording_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:
    """Get single recording by ID."""
    recording = await RecordingService.get_recording(
        db=db,
        meeting_id=meeting_id,
        recording_id=recording_id,
        current_user=current_user,
    )
    return RecordingResponse.model_validate(recording)


@router.delete(
    "/{recording_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete meeting recording",
    description="Delete a meeting recording from storage and database. Allowed for meeting/workspace owner/admin or the original uploader.",
)
async def delete_meeting_recording(
    meeting_id: uuid.UUID,
    recording_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete recording."""
    await RecordingService.delete_recording(
        db=db,
        meeting_id=meeting_id,
        recording_id=recording_id,
        current_user=current_user,
    )
    return MessageResponse(message="Recording deleted successfully.")


@router.post(
    "/{recording_id}/transcribe",
    response_model=TranscriptionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger recording transcription",
    description="Enqueue an asynchronous transcription task for this recording. Requires Member, Admin, or Owner role.",
)
async def transcribe_recording(
    meeting_id: uuid.UUID,
    recording_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptionJobResponse:
    """Trigger asynchronous transcription for a recording."""
    recording = await TranscriptionService.trigger_transcription(
        db=db,
        meeting_id=meeting_id,
        recording_id=recording_id,
        current_user=current_user,
    )
    return TranscriptionJobResponse(
        recording_id=recording.id,
        meeting_id=recording.meeting_id,
        status=recording.status.value,
        message=f"Transcription task {recording.status.value.lower()}.",
    )


@router.get(
    "/{recording_id}/transcription",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recording transcription",
    description="Retrieve the transcription result and metadata for a specific meeting recording.",
)
async def get_recording_transcription(
    meeting_id: uuid.UUID,
    recording_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptResponse:
    """Retrieve transcription for a specific recording."""
    transcript = await TranscriptionService.get_transcription_for_recording(
        db=db,
        meeting_id=meeting_id,
        recording_id=recording_id,
        current_user=current_user,
    )
    return TranscriptResponse.model_validate(transcript)
