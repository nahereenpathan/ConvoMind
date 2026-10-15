"""Meeting transcript and segment management API routes."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.transcript import TranscriptSegment
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.transcript import (
    SegmentListResponse,
    SpeakerResponse,
    TranscriptResponse,
    TranscriptSegmentBatchSpeaker,
    TranscriptSegmentCreate,
    TranscriptSegmentResponse,
    TranscriptSegmentUpdate,
    TranscriptStatusResponse,
    TranscriptUpdate,
    TranscriptWithSegmentsResponse,
)
from app.services.transcript_export_service import TranscriptExportService
from app.services.transcription_service import TranscriptionService

router = APIRouter()


def _to_segment_response(seg: TranscriptSegment) -> TranscriptSegmentResponse:
    """Helper to convert a TranscriptSegment ORM entity to TranscriptSegmentResponse."""
    speaker_dto = SpeakerResponse.model_validate(seg.speaker) if seg.speaker else None
    return TranscriptSegmentResponse(
        id=seg.id,
        transcript_id=seg.transcript_id,
        sequence_order=seg.sequence_order,
        start_time=seg.start_time,
        end_time=seg.end_time,
        text=seg.text,
        confidence=seg.confidence,
        speaker_id=seg.speaker_id,
        speaker=speaker_dto,
        created_at=seg.created_at,
        updated_at=seg.updated_at,
    )


@router.get(
    "",
    response_model=TranscriptWithSegmentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meeting transcript",
    description="Retrieve the latest transcript and paginated timestamped speech segments for a meeting.",
)
async def get_meeting_transcript(
    meeting_id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="Page number of segments"),
    page_size: int = Query(default=100, ge=1, le=500, description="Number of segments per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptWithSegmentsResponse:
    """Retrieve meeting transcript and paginated segments."""
    _, transcript, segments, total_segments = await TranscriptionService.get_transcript_for_meeting(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )

    segment_responses = [_to_segment_response(s) for s in segments]

    return TranscriptWithSegmentsResponse(
        id=transcript.id,
        meeting_id=transcript.meeting_id,
        recording_id=transcript.recording_id,
        workspace_id=transcript.workspace_id,
        status=transcript.status,
        language=transcript.language,
        full_text=transcript.full_text,
        word_count=transcript.word_count,
        confidence_score=transcript.confidence_score,
        duration=transcript.duration,
        provider=transcript.provider,
        processing_metadata=transcript.processing_metadata,
        error_message=transcript.error_message,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
        segments=segment_responses,
        total_segments=total_segments,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transcript metadata",
    description="Update metadata for a meeting transcript (e.g. language tag).",
)
async def update_transcript_metadata(
    meeting_id: uuid.UUID,
    data: TranscriptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptResponse:
    """Update transcript metadata."""
    transcript = await TranscriptionService.update_transcript(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        data=data,
    )
    return TranscriptResponse.model_validate(transcript)


@router.get(
    "/status",
    response_model=TranscriptStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transcript processing status",
    description="Lightweight status check for a meeting's audio transcription pipeline.",
)
async def get_meeting_transcript_status(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptStatusResponse:
    """Retrieve lightweight transcription status."""
    transcript = await TranscriptionService.get_transcript_status(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )

    return TranscriptStatusResponse(
        meeting_id=transcript.meeting_id,
        recording_id=transcript.recording_id,
        status=transcript.status,
        word_count=transcript.word_count,
        duration=transcript.duration,
        error_message=transcript.error_message,
        updated_at=transcript.updated_at,
    )


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export transcript",
    description="Export meeting transcript in TXT, Markdown, SRT, WebVTT, or JSON format.",
)
async def export_transcript(
    meeting_id: uuid.UUID,
    format: str = Query(
        default="txt",
        pattern="^(txt|markdown|md|srt|vtt|webvtt|json)$",
        description="Target export format (txt, markdown/md, srt, vtt/webvtt, json)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export transcript and all segments into the specified file format."""
    meeting, transcript, segments = await TranscriptionService.get_all_segments_for_export(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )

    fmt = format.lower()
    if fmt == "txt":
        content, media_type, filename = TranscriptExportService.export_txt(meeting, transcript, segments)
    elif fmt in ("markdown", "md"):
        content, media_type, filename = TranscriptExportService.export_markdown(meeting, transcript, segments)
    elif fmt == "srt":
        content, media_type, filename = TranscriptExportService.export_srt(meeting, transcript, segments)
    elif fmt in ("vtt", "webvtt"):
        content, media_type, filename = TranscriptExportService.export_vtt(meeting, transcript, segments)
    elif fmt == "json":
        content, media_type, filename = TranscriptExportService.export_json(meeting, transcript, segments)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}",
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/segments",
    response_model=SegmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List or search transcript segments",
    description="List segments with optional text search filter and pagination.",
)
async def list_transcript_segments(
    meeting_id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Page size"),
    query: Optional[str] = Query(default=None, description="Optional text search query within segments"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SegmentListResponse:
    """List transcript segments with optional in-meeting search."""
    transcript, segments, total = await TranscriptionService.list_segments(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        page=page,
        page_size=page_size,
        query=query,
    )

    return SegmentListResponse(
        transcript_id=transcript.id,
        meeting_id=meeting_id,
        total_segments=total,
        page=page,
        page_size=page_size,
        segments=[_to_segment_response(s) for s in segments],
    )


@router.post(
    "/segments",
    response_model=TranscriptSegmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Insert new transcript segment",
    description="Add a new utterance segment. If sequence_order is omitted, it is appended to the end.",
)
async def create_transcript_segment(
    meeting_id: uuid.UUID,
    data: TranscriptSegmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptSegmentResponse:
    """Insert a new segment into the transcript."""
    segment = await TranscriptionService.create_segment(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        data=data,
    )
    return _to_segment_response(segment)


@router.post(
    "/segments/batch-speaker",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch assign speaker to segments",
    description="Assign or clear speaker tag across multiple segments simultaneously.",
)
async def batch_assign_speaker(
    meeting_id: uuid.UUID,
    data: TranscriptSegmentBatchSpeaker,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Batch assign speaker to multiple segments."""
    updated_count = await TranscriptionService.batch_assign_speaker(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
        data=data,
    )
    return MessageResponse(message=f"Successfully updated {updated_count} segment(s).")


@router.get(
    "/segments/{segment_id}",
    response_model=TranscriptSegmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transcript segment",
    description="Retrieve a single transcript segment by ID.",
)
async def get_transcript_segment(
    meeting_id: uuid.UUID,
    segment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptSegmentResponse:
    """Get a single transcript segment."""
    segment = await TranscriptionService.get_segment(
        db=db,
        meeting_id=meeting_id,
        segment_id=segment_id,
        current_user=current_user,
    )
    return _to_segment_response(segment)


@router.patch(
    "/segments/{segment_id}",
    response_model=TranscriptSegmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit transcript segment",
    description="Update segment text, timestamps, confidence, or speaker.",
)
async def update_transcript_segment(
    meeting_id: uuid.UUID,
    segment_id: uuid.UUID,
    data: TranscriptSegmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptSegmentResponse:
    """Update a transcript segment."""
    segment = await TranscriptionService.update_segment(
        db=db,
        meeting_id=meeting_id,
        segment_id=segment_id,
        current_user=current_user,
        data=data,
    )
    return _to_segment_response(segment)


@router.delete(
    "/segments/{segment_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete transcript segment",
    description="Delete a transcript segment and automatically re-sequence remaining segments.",
)
async def delete_transcript_segment(
    meeting_id: uuid.UUID,
    segment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a segment from the transcript."""
    await TranscriptionService.delete_segment(
        db=db,
        meeting_id=meeting_id,
        segment_id=segment_id,
        current_user=current_user,
    )
    return MessageResponse(message="Transcript segment deleted successfully.")
