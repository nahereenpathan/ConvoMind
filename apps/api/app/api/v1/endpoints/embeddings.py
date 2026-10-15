"""API endpoints for vector embedding processing, status inspection, and semantic search."""

import uuid
from typing import Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.meeting import get_meeting_and_membership
from app.api.dependencies.workspace import get_workspace_and_membership
from app.core.database import get_db
from app.models.embedding import TranscriptEmbedding
from app.models.enums import TranscriptStatus
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.embedding import (
    EmbeddingProcessResponse,
    EmbeddingStatusResponse,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResultItem,
)
from app.services.embedding.search_service import VectorSearchService
from app.workers.tasks.embedding_tasks import process_transcript_embeddings

router = APIRouter()


@router.post(
    "/meetings/{meeting_id}/embeddings/process",
    response_model=EmbeddingProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger vector embedding generation for a meeting transcript",
    description="Asynchronously chunks the completed transcript and generates vector embeddings for semantic search.",
)
async def process_meeting_embeddings(
    meeting_context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    db: AsyncSession = Depends(get_db),
) -> EmbeddingProcessResponse:
    """Queue vector embedding processing job for a meeting's completed transcript."""
    meeting, member = meeting_context

    # Retrieve completed transcript
    stmt = (
        select(Transcript)
        .where(Transcript.meeting_id == meeting.id)
        .order_by(Transcript.updated_at.desc())
    )
    result = await db.execute(stmt)
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found for this meeting.",
        )

    if transcript.status != TranscriptStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript status is '{transcript.status}'. Embeddings can only be generated for COMPLETED transcripts.",
        )

    # Dispatch Celery background task
    task = process_transcript_embeddings.delay(str(transcript.id))

    return EmbeddingProcessResponse(
        status="queued",
        meeting_id=meeting.id,
        transcript_id=transcript.id,
        task_id=task.id,
        message="Transcript embedding task queued successfully.",
    )


@router.get(
    "/meetings/{meeting_id}/embeddings/status",
    response_model=EmbeddingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get vector embedding status for a meeting transcript",
)
async def get_meeting_embedding_status(
    meeting_context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    db: AsyncSession = Depends(get_db),
) -> EmbeddingStatusResponse:
    """Retrieve embedding chunk count, provider, model, and processing stats."""
    meeting, member = meeting_context

    # Retrieve transcript
    t_stmt = (
        select(Transcript)
        .where(Transcript.meeting_id == meeting.id)
        .order_by(Transcript.updated_at.desc())
    )
    t_result = await db.execute(t_stmt)
    transcript = t_result.scalar_one_or_none()

    if not transcript:
        return EmbeddingStatusResponse(
            meeting_id=meeting.id,
            transcript_id=None,
            is_embedded=False,
            chunk_count=0,
            provider=None,
            model=None,
            dimension=None,
            last_updated_at=None,
        )

    # Query embedding metrics
    e_stmt = select(
        func.count(TranscriptEmbedding.id).label("count"),
        func.max(TranscriptEmbedding.provider).label("provider"),
        func.max(TranscriptEmbedding.model).label("model"),
        func.max(TranscriptEmbedding.dimension).label("dimension"),
        func.max(TranscriptEmbedding.updated_at).label("last_updated"),
    ).where(TranscriptEmbedding.transcript_id == transcript.id)

    row = (await db.execute(e_stmt)).first()

    count = row.count if row and row.count else 0
    provider = row.provider if row and count > 0 else None
    model_name = row.model if row and count > 0 else None
    dimension = row.dimension if row and count > 0 else None
    last_updated = row.last_updated if row and count > 0 else None

    return EmbeddingStatusResponse(
        meeting_id=meeting.id,
        transcript_id=transcript.id,
        is_embedded=count > 0,
        chunk_count=count,
        provider=provider,
        model=model_name,
        dimension=dimension,
        last_updated_at=last_updated,
    )


@router.post(
    "/workspaces/{workspace_id}/embeddings/search",
    response_model=VectorSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Perform workspace-isolated semantic vector search",
    description="Execute vector similarity search across transcript chunks within a workspace.",
)
async def search_workspace_embeddings(
    request: VectorSearchRequest,
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    db: AsyncSession = Depends(get_db),
) -> VectorSearchResponse:
    """Execute workspace semantic vector search."""
    workspace, member = workspace_context

    # Optional meeting validation to ensure it belongs to workspace
    if request.meeting_id is not None:
        m_stmt = select(Meeting).where(
            Meeting.id == request.meeting_id,
            Meeting.workspace_id == workspace.id,
        )
        meeting = (await db.execute(m_stmt)).scalar_one_or_none()
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified meeting not found in this workspace.",
            )

    results = await VectorSearchService.search_similar_chunks(
        session=db,
        workspace_id=workspace.id,
        query_text=request.query,
        meeting_id=request.meeting_id,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
    )

    items = [
        VectorSearchResultItem(
            embedding_id=r.embedding_id,
            workspace_id=r.workspace_id,
            meeting_id=r.meeting_id,
            transcript_id=r.transcript_id,
            start_segment_id=r.start_segment_id,
            end_segment_id=r.end_segment_id,
            chunk_index=r.chunk_index,
            content=r.content,
            similarity_score=r.similarity_score,
            distance=r.distance,
            start_time=r.start_time,
            end_time=r.end_time,
            speaker_labels=r.speaker_labels,
            provider=r.provider,
            model=r.model,
        )
        for r in results
    ]

    return VectorSearchResponse(
        workspace_id=workspace.id,
        query=request.query,
        total_results=len(items),
        results=items,
    )
