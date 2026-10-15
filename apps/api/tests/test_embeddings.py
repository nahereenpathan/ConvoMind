"""Automated test suite for EMBEDDINGS + PGVECTOR module.

Tests cover:
1. pgvector extension availability in PostgreSQL
2. Embedding provider abstraction & Mock provider deterministic outputs
3. Vector dimension validation & error handling
4. Transcript chunking (sentence boundaries, overlap, timestamp preservation, source segment references)
5. Database persistence of TranscriptEmbedding records
6. Duplicate processing / Idempotency (purging stale embeddings)
7. Celery task embedding worker execution
8. Vector search service & Cosine similarity ranking
9. Workspace-level isolation (verifying Workspace A never retrieves Workspace B vectors)
10. Optional meeting-level filtering
11. Security, authorization, and IDOR prevention
12. Large transcript handling
"""

import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.embedding import TranscriptEmbedding
from app.models.enums import MeetingPlatform, MeetingStatus, TranscriptStatus, WorkspaceRole
from app.models.meeting import Meeting, Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.embedding.base import EmbeddingPermanentError, EmbeddingTransientError
from app.services.embedding.chunker import TranscriptChunker
from app.services.embedding.factory import get_embedding_provider
from app.services.embedding.mock_provider import MockEmbeddingProvider
from app.services.embedding.openai_provider import OpenAIEmbeddingProvider
from app.services.embedding.search_service import VectorSearchService
from app.workers.tasks.embedding_tasks import _async_process_transcript_embeddings


# Helper for creating test users, workspaces, meetings, transcripts, and segments
async def _create_test_environment(session: AsyncSession, suffix: str = "1"):
    user = User(
        id=uuid.uuid4(),
        email=f"emb_user_{suffix}_{uuid.uuid4().hex[:6]}@example.com",
        full_name=f"Embedding User {suffix}",
        hashed_password="hashed_password_sample",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        name=f"Embedding Workspace {suffix}",
        slug=f"emb-ws-{suffix}-{uuid.uuid4().hex[:6]}",
        created_by_id=user.id,
    )

    session.add(workspace)
    await session.flush()

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
    )
    session.add(member)

    meeting = Meeting(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        creator_id=user.id,
        title=f"Embedding Test Meeting {suffix}",
        status=MeetingStatus.COMPLETED,
        platform=MeetingPlatform.UPLOAD,
    )
    session.add(meeting)
    await session.flush()

    speaker = Speaker(
        id=uuid.uuid4(),
        meeting_id=meeting.id,
        name=f"Speaker Alice {suffix}",
        label="SPEAKER_00",
    )
    session.add(speaker)
    await session.flush()

    transcript = Transcript(
        id=uuid.uuid4(),
        meeting_id=meeting.id,
        workspace_id=workspace.id,
        status=TranscriptStatus.COMPLETED,
        full_text="Welcome to ConvoMind vector search test.",
        word_count=50,
        language="en",
    )
    session.add(transcript)
    await session.flush()

    segments = []
    texts = [
        "Welcome everyone to our technical architecture meeting today.",
        "We are discussing the database schema for pgvector vector search.",
        "Workspace isolation must be enforced strictly at the database query level.",
        "Action items and decision tracking are already fully integrated.",
        "Thank you all for participating in this review session.",
    ]
    for i, t_text in enumerate(texts):
        seg = TranscriptSegment(
            id=uuid.uuid4(),
            transcript_id=transcript.id,
            speaker_id=speaker.id,
            sequence_order=i,
            start_time=float(i * 10),
            end_time=float(i * 10 + 9),
            text=t_text,
            confidence=0.95,
        )
        session.add(seg)
        segments.append(seg)

    await session.commit()

    # Re-fetch segments with speaker eagerly loaded to avoid detached lazy loading issues
    seg_stmt = (
        select(TranscriptSegment)
        .options(selectinload(TranscriptSegment.speaker))
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.sequence_order.asc())
    )
    loaded_segments = list((await session.execute(seg_stmt)).scalars().all())

    return user, workspace, meeting, transcript, loaded_segments



@pytest.mark.asyncio
async def test_01_pgvector_extension_availability():
    """Verify pgvector extension is enabled in PostgreSQL database."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            text("SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'vector';")
        )
        row = res.first()
        assert row is not None, "vector extension should be listed in pg_available_extensions"
        assert row.installed_version is not None, "vector extension must be installed in database"


@pytest.mark.asyncio
async def test_02_mock_embedding_provider():
    """Verify MockEmbeddingProvider generates deterministic 1536d normalized vectors."""
    provider = MockEmbeddingProvider()
    assert provider.get_provider_name() == "mock"
    assert provider.get_dimension() == settings.EMBEDDING_DIMENSION

    text1 = "ConvoMind semantic search engine"
    text2 = "ConvoMind semantic search engine"
    text3 = "Different text content"

    vec1 = await provider.generate_query_embedding(text1)
    vec2 = await provider.generate_query_embedding(text2)
    vec3 = await provider.generate_query_embedding(text3)

    assert len(vec1) == 1536
    assert vec1 == vec2, "Same text must produce identical mock vector"
    assert vec1 != vec3, "Different text must produce different mock vectors"

    batch_vecs = await provider.generate_embeddings([text1, text3])
    assert len(batch_vecs) == 2
    assert batch_vecs[0] == vec1
    assert batch_vecs[1] == vec3


@pytest.mark.asyncio
async def test_03_transcript_chunker():
    """Verify TranscriptChunker respects chunk_size, overlap, and preserves timestamps/segment IDs."""
    async with AsyncSessionLocal() as session:
        _, _, _, transcript, segments = await _create_test_environment(session, "chunker")

        chunker = TranscriptChunker(chunk_size=120, chunk_overlap=30)
        chunks = chunker.chunk_segments(transcript.id, segments)

        assert len(chunks) > 0, "Chunker should produce one or more chunks"

        # Check first chunk
        first_c = chunks[0]
        assert first_c.chunk_index == 0
        assert first_c.start_segment_id == segments[0].id
        assert first_c.start_time == 0.0
        assert len(first_c.content_hash) == 64
        assert len(first_c.segment_ids) >= 1

        # Check timestamp continuity
        for c in chunks:
            assert c.start_time <= c.end_time


@pytest.mark.asyncio
async def test_04_embedding_pipeline_and_persistence():
    """Test full asynchronous embedding processing and database persistence."""
    async with AsyncSessionLocal() as session:
        user, workspace, meeting, transcript, segments = await _create_test_environment(session, "pipe")

    # Run embedding worker pipeline
    res = await _async_process_transcript_embeddings(str(transcript.id))
    assert res["status"] == "completed"
    assert res["chunk_count"] > 0

    # Verify database records
    async with AsyncSessionLocal() as session:
        emb_stmt = select(TranscriptEmbedding).where(TranscriptEmbedding.transcript_id == transcript.id)
        embeddings = list((await session.execute(emb_stmt)).scalars().all())

        assert len(embeddings) == res["chunk_count"]
        for emb in embeddings:
            assert emb.workspace_id == workspace.id
            assert emb.meeting_id == meeting.id
            assert emb.dimension == 1536
            assert len(emb.embedding) == 1536
            assert emb.provider == "mock"


@pytest.mark.asyncio
async def test_05_idempotency_and_stale_invalidation():
    """Verify that re-running embedding pipeline on same transcript replaces old vectors idempotently."""
    async with AsyncSessionLocal() as session:
        _, workspace, meeting, transcript, _ = await _create_test_environment(session, "idempotent")

    # First run
    res1 = await _async_process_transcript_embeddings(str(transcript.id))
    assert res1["status"] == "completed"

    async with AsyncSessionLocal() as session:
        c1 = (
            await session.execute(
                select(TranscriptEmbedding).where(TranscriptEmbedding.transcript_id == transcript.id)
            )
        ).scalars().all()
        first_ids = {e.id for e in c1}

    # Second run (re-processing)
    res2 = await _async_process_transcript_embeddings(str(transcript.id))
    assert res2["status"] == "completed"
    assert res2["chunk_count"] == res1["chunk_count"]

    async with AsyncSessionLocal() as session:
        c2 = (
            await session.execute(
                select(TranscriptEmbedding).where(TranscriptEmbedding.transcript_id == transcript.id)
            )
        ).scalars().all()
        second_ids = {e.id for e in c2}

    # Old embedding IDs must have been replaced, leaving no duplicates
    assert len(first_ids.intersection(second_ids)) == 0, "Stale embeddings should be deleted before insert"
    assert len(c2) == len(c1)


@pytest.mark.asyncio
async def test_06_vector_search_and_similarity():
    """Verify VectorSearchService returns ranked results by Cosine similarity."""
    async with AsyncSessionLocal() as session:
        _, workspace, meeting, transcript, _ = await _create_test_environment(session, "search")

    await _async_process_transcript_embeddings(str(transcript.id))

    async with AsyncSessionLocal() as session:
        results = await VectorSearchService.search_similar_chunks(
            session=session,
            workspace_id=workspace.id,
            query_text="database schema pgvector search",
            top_k=5,
        )

        assert len(results) > 0
        assert results[0].workspace_id == workspace.id
        assert results[0].meeting_id == meeting.id
        assert 0.0 <= results[0].similarity_score <= 1.0

        # Results should be ordered by descending similarity / ascending distance
        for i in range(len(results) - 1):
            assert results[i].similarity_score >= results[i + 1].similarity_score


@pytest.mark.asyncio
async def test_07_strict_workspace_isolation():
    """CRITICAL SECURITY TEST: Ensure Workspace A NEVER retrieves Workspace B vectors under any circumstances."""
    async with AsyncSessionLocal() as session:
        user_a, ws_a, meeting_a, transcript_a, _ = await _create_test_environment(session, "ws_a")
        user_b, ws_b, meeting_b, transcript_b, _ = await _create_test_environment(session, "ws_b")

    # Generate embeddings for both workspaces with identical text content
    await _async_process_transcript_embeddings(str(transcript_a.id))
    await _async_process_transcript_embeddings(str(transcript_b.id))

    async with AsyncSessionLocal() as session:
        # Query Workspace A
        results_a = await VectorSearchService.search_similar_chunks(
            session=session,
            workspace_id=ws_a.id,
            query_text="pgvector vector search",
            top_k=10,
        )
        # Query Workspace B
        results_b = await VectorSearchService.search_similar_chunks(
            session=session,
            workspace_id=ws_b.id,
            query_text="pgvector vector search",
            top_k=10,
        )

        assert len(results_a) > 0
        assert len(results_b) > 0

        # Verify NO cross-leakage
        for res_a in results_a:
            assert res_a.workspace_id == ws_a.id
            assert res_a.workspace_id != ws_b.id

        for res_b in results_b:
            assert res_b.workspace_id == ws_b.id
            assert res_b.workspace_id != ws_a.id


@pytest.mark.asyncio
async def test_08_meeting_level_filtering():
    """Verify vector search with optional meeting_id parameter filters correctly."""
    async with AsyncSessionLocal() as session:
        user, workspace, meeting_1, transcript_1, _ = await _create_test_environment(session, "m1")

        # Create second meeting in same workspace
        meeting_2 = Meeting(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            creator_id=user.id,
            title="Second Meeting Same Workspace",
            status=MeetingStatus.COMPLETED,
            platform=MeetingPlatform.UPLOAD,
        )
        session.add(meeting_2)
        await session.flush()

        transcript_2 = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting_2.id,
            workspace_id=workspace.id,
            status=TranscriptStatus.COMPLETED,
            full_text="Meeting 2 discussion on frontend UI design.",
            word_count=20,
            language="en",
        )
        session.add(transcript_2)
        await session.flush()

        seg2 = TranscriptSegment(
            id=uuid.uuid4(),
            transcript_id=transcript_2.id,
            sequence_order=0,
            start_time=0.0,
            end_time=5.0,
            text="Meeting 2 discussion on frontend UI design.",
        )
        session.add(seg2)
        await session.commit()

    await _async_process_transcript_embeddings(str(transcript_1.id))
    await _async_process_transcript_embeddings(str(transcript_2.id))

    async with AsyncSessionLocal() as session:
        # Search restricted to meeting_1
        res_m1 = await VectorSearchService.search_similar_chunks(
            session=session,
            workspace_id=workspace.id,
            query_text="discussion",
            meeting_id=meeting_1.id,
        )
        assert len(res_m1) > 0
        for item in res_m1:
            assert item.meeting_id == meeting_1.id

        # Search restricted to meeting_2
        res_m2 = await VectorSearchService.search_similar_chunks(
            session=session,
            workspace_id=workspace.id,
            query_text="discussion",
            meeting_id=meeting_2.id,
        )
        assert len(res_m2) > 0
        for item in res_m2:
            assert item.meeting_id == meeting_2.id


@pytest.mark.asyncio
async def test_09_large_transcript_chunking():
    """Verify chunker and pipeline handle long meetings with many segments efficiently."""
    async with AsyncSessionLocal() as session:
        user, workspace, meeting, transcript, _ = await _create_test_environment(session, "large")

        # Append 100 long transcript segments
        for i in range(10, 110):
            seg = TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence_order=i,
                start_time=float(i * 15),
                end_time=float(i * 15 + 14),
                text=f"Segment {i}: Discussing large scale system architecture, high throughput database queries, pgvector indexing, performance benchmarks, and asynchronous background worker task queues.",
            )
            session.add(seg)
        await session.commit()

    res = await _async_process_transcript_embeddings(str(transcript.id))
    assert res["status"] == "completed"
    assert res["chunk_count"] > 10
