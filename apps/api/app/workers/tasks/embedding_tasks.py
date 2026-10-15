"""Celery worker task for asynchronous transcript vector embedding generation."""

import asyncio
import os
import sys
import logging
import time
import uuid
from typing import Any, Dict, Optional
from celery.exceptions import MaxRetriesExceededError
import redis
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.embedding import TranscriptEmbedding
from app.models.enums import TranscriptStatus
from app.models.transcript import Transcript, TranscriptSegment
from app.services.embedding.base import (
    EmbeddingPermanentError,
    EmbeddingTransientError,
)
from app.services.embedding.chunker import TranscriptChunker
from app.services.embedding.factory import get_embedding_provider
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _async_process_transcript_embeddings(transcript_id_str: str) -> Dict[str, Any]:
    """Asynchronously chunk transcript, generate embeddings, and persist in pgvector store."""
    try:
        transcript_id = uuid.UUID(transcript_id_str)
    except (ValueError, TypeError) as exc:
        logger.error(f"Invalid transcript UUID passed to embedding worker: {transcript_id_str} ({exc})")
        return {"status": "invalid_id", "transcript_id": transcript_id_str}

    # Distributed lock via Redis to prevent concurrent worker execution
    redis_client = None
    lock_acquired = False
    lock_key = f"lock:embedding:{transcript_id_str}"

    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        lock_acquired = bool(redis_client.set(lock_key, "locked", nx=True, ex=600))
        if not lock_acquired:
            logger.warning(
                f"Embedding processing for transcript {transcript_id_str} is already active on another worker."
            )
            return {"status": "already_running", "transcript_id": transcript_id_str}
    except Exception as lock_err:
        logger.warning(f"Could not verify Redis lock: {lock_err}. Proceeding with embedding pipeline.")

    start_time = time.time()

    try:
        async with AsyncSessionLocal() as session:
            # 1. Fetch transcript
            t_stmt = select(Transcript).where(Transcript.id == transcript_id)
            transcript = (await session.execute(t_stmt)).scalar_one_or_none()

            if not transcript:
                logger.error(f"Transcript {transcript_id} not found in database.")
                return {"status": "not_found", "transcript_id": transcript_id_str}

            if transcript.status != TranscriptStatus.COMPLETED:
                logger.warning(
                    f"Transcript {transcript_id} status is {transcript.status}; skipping embedding generation."
                )
                return {"status": "skipped_not_completed", "transcript_id": transcript_id_str}

            # 2. Fetch transcript segments with speaker relationship
            seg_stmt = (
                select(TranscriptSegment)
                .options(selectinload(TranscriptSegment.speaker))
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.sequence_order.asc())
            )
            segments = list((await session.execute(seg_stmt)).scalars().all())

            if not segments:
                logger.warning(f"Transcript {transcript_id} has no segments to chunk.")
                return {"status": "no_segments", "transcript_id": transcript_id_str}

            # 3. Perform sentence-aware chunking
            chunker = TranscriptChunker()
            chunks = chunker.chunk_segments(transcript.id, segments)

            if not chunks:
                return {"status": "no_chunks_created", "transcript_id": transcript_id_str}

            # 4. Generate embeddings via provider
            provider = get_embedding_provider()
            contents = [c.content for c in chunks]
            vectors = await provider.generate_embeddings(contents)

            if len(vectors) != len(chunks):
                raise EmbeddingPermanentError(
                    f"Vector count mismatch: generated {len(vectors)} vectors for {len(chunks)} chunks."
                )

            # 5. Atomic Idempotency: Delete existing embeddings for this transcript
            await session.execute(
                delete(TranscriptEmbedding).where(TranscriptEmbedding.transcript_id == transcript.id)
            )

            # 6. Bulk insert new embedding records
            new_embeddings = []
            for chunk_data, vec in zip(chunks, vectors):
                emb_record = TranscriptEmbedding(
                    id=uuid.uuid4(),
                    workspace_id=transcript.workspace_id,
                    meeting_id=transcript.meeting_id,
                    transcript_id=transcript.id,
                    start_segment_id=chunk_data.start_segment_id,
                    end_segment_id=chunk_data.end_segment_id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    content_hash=chunk_data.content_hash,
                    embedding=vec,
                    provider=provider.get_provider_name(),
                    model=provider.get_model_name(),
                    dimension=provider.get_dimension(),
                    start_time=chunk_data.start_time,
                    end_time=chunk_data.end_time,
                    token_count=chunk_data.token_count,
                    chunk_metadata={
                        "segment_ids": [str(sid) for sid in chunk_data.segment_ids],
                        "speaker_labels": chunk_data.speaker_labels,
                    },
                )
                new_embeddings.append(emb_record)

            session.add_all(new_embeddings)
            await session.commit()

            duration_s = round(time.time() - start_time, 2)
            logger.info(
                f"Successfully processed embeddings for transcript {transcript_id}: "
                f"workspace_id={transcript.workspace_id} meeting_id={transcript.meeting_id} "
                f"chunks={len(new_embeddings)} provider={provider.get_provider_name()} "
                f"model={provider.get_model_name()} duration={duration_s}s"
            )

            return {
                "status": "completed",
                "transcript_id": str(transcript.id),
                "meeting_id": str(transcript.meeting_id),
                "workspace_id": str(transcript.workspace_id),
                "chunk_count": len(new_embeddings),
                "duration_seconds": duration_s,
                "provider": provider.get_provider_name(),
                "model": provider.get_model_name(),
            }

    except Exception as exc:
        logger.error(f"Embedding pipeline failed for transcript {transcript_id_str}: {exc}")
        raise exc

    finally:
        # Release distributed lock
        if lock_acquired and redis_client:
            try:
                redis_client.delete(lock_key)
            except Exception:
                pass

        import sys
        if "pytest" not in sys.modules and not os.getenv("TESTING") and os.getenv("CELERY_WORKER"):
            try:
                await engine.dispose()
            except Exception:
                pass


@celery_app.task(
    bind=True,
    name="app.workers.tasks.embedding_tasks.process_transcript_embeddings",
    max_retries=3,
)
def process_transcript_embeddings(
    self,
    transcript_id: str,
) -> Dict[str, Any]:
    """Celery task executing transcript chunking and vector embedding generation."""
    logger.info(
        f"Starting transcript embedding Celery task for transcript {transcript_id} "
        f"(attempt {self.request.retries + 1})"
    )
    try:
        return asyncio.run(_async_process_transcript_embeddings(transcript_id))
    except EmbeddingTransientError as trans_exc:
        countdown = 5 * (2 ** self.request.retries)
        logger.warning(
            f"Transient embedding failure for transcript {transcript_id}: {trans_exc}. "
            f"Retrying in {countdown}s (retry {self.request.retries + 1}/{self.max_retries})..."
        )
        try:
            self.retry(exc=trans_exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for transcript embedding {transcript_id}.")
            raise
    except Exception as exc:
        logger.error(
            f"Permanent or unhandled failure in transcript embedding for {transcript_id}: {exc}"
        )
        raise
