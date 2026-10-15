"""Deterministic regression test suite for RAG QA pipeline.

Fixtures and test cases as defined in Section 6:
Transcript:
"Arjun will complete backend development and testing by October 19.
Sara will improve the user interface and complete the design changes by October 20.
Daniel will prepare the marketing plan and customer feedback form by October 21."

Test cases:
1. Question: "What task is assigned to Sara?"
   Expected: Improve the user interface and complete design changes.
   Expected deadline: October 20.

2. Question: "Who handles backend development?"
   Expected: Arjun.
   Expected deadline: October 19.

3. Question: "What must Daniel prepare?"
   Expected: Marketing plan and customer feedback form.
   Expected deadline: October 21.

4. Question: "What is Sara's deadline?"
   Expected: October 20.

5. Question: "What is the clinic's opening time?"
   Expected: State that this information is not present in the supplied meeting transcript.

6. Verify that questions cannot retrieve transcripts from another user's meeting or workspace.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation
from app.models.enums import MeetingPlatform, MeetingStatus, TranscriptStatus, WorkspaceRole
from app.models.meeting import Meeting, Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.rag.rag_service import RAGService
from app.workers.tasks.embedding_tasks import _async_process_transcript_embeddings


async def _setup_regression_environment(session: AsyncSession, suffix: str = "reg"):
    """Helper to set up meeting with deterministic 3-sentence transcript."""
    user = User(
        id=uuid.uuid4(),
        email=f"user_{suffix}_{uuid.uuid4().hex[:6]}@convomind.ai",
        full_name=f"User {suffix}",
        hashed_password="hashed_password_sample",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        name=f"Workspace {suffix}",
        slug=f"ws-{suffix}-{uuid.uuid4().hex[:6]}",
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
        title=f"Sprint Planning {suffix}",
        status=MeetingStatus.COMPLETED,
        platform=MeetingPlatform.UPLOAD,
    )
    session.add(meeting)
    await session.flush()

    speaker = Speaker(
        id=uuid.uuid4(),
        meeting_id=meeting.id,
        name="Team Lead",
        label="SPEAKER_00",
    )
    session.add(speaker)
    await session.flush()

    full_transcript_text = (
        "Arjun will complete backend development and testing by October 19.\n"
        "Sara will improve the user interface and complete the design changes by October 20.\n"
        "Daniel will prepare the marketing plan and customer feedback form by October 21."
    )

    transcript = Transcript(
        id=uuid.uuid4(),
        meeting_id=meeting.id,
        workspace_id=workspace.id,
        status=TranscriptStatus.COMPLETED,
        full_text=full_transcript_text,
        word_count=len(full_transcript_text.split()),
        language="en",
    )
    session.add(transcript)
    await session.flush()

    segments_data = [
        ("Arjun will complete backend development and testing by October 19.", 0.0, 10.0),
        ("Sara will improve the user interface and complete the design changes by October 20.", 11.0, 20.0),
        ("Daniel will prepare the marketing plan and customer feedback form by October 21.", 21.0, 30.0),
    ]

    for i, (text, start_t, end_t) in enumerate(segments_data):
        seg = TranscriptSegment(
            id=uuid.uuid4(),
            transcript_id=transcript.id,
            speaker_id=speaker.id,
            sequence_order=i,
            start_time=start_t,
            end_time=end_t,
            text=text,
            confidence=0.99,
        )
        session.add(seg)

    await session.commit()

    # Generate embeddings and chunk index
    await _async_process_transcript_embeddings(str(transcript.id))

    conv = ChatConversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        meeting_id=meeting.id,
        title=f"Chat {suffix}",
    )
    session.add(conv)
    await session.commit()

    return user, workspace, meeting, transcript, conv


@pytest.mark.asyncio
async def test_case_1_sara_assigned_task(db_session):
    """Test 1: What task is assigned to Sara?
    Expected: Improve user interface and complete design changes, deadline October 20.
    """
    user, workspace, meeting, transcript, conv = await _setup_regression_environment(db_session, "tc1")

    res = await RAGService.answer_question(
        session=db_session,
        workspace_id=workspace.id,
        user_id=user.id,
        conversation_id=conv.id,
        question_text="What task is assigned to Sara?",
        meeting_id_filter=meeting.id,
    )

    ans = res.answer.lower()
    assert "user interface" in ans or "design changes" in ans
    assert "october 20" in ans
    assert len(res.sources) > 0
    assert any("Sara will improve" in (s.get("text") or s.get("text_excerpt") or "") for s in res.sources)

    # Test grammatical & spelling variations
    for query_var in [
        "what task is assign to sara?",
        "What is Sara responsible for?",
        "What does Sara need to complete?",
    ]:
        v_res = await RAGService.answer_question(
            session=db_session,
            workspace_id=workspace.id,
            user_id=user.id,
            conversation_id=conv.id,
            question_text=query_var,
            meeting_id_filter=meeting.id,
        )
        v_ans = v_res.answer.lower()
        assert "user interface" in v_ans or "design changes" in v_ans
        assert "october 20" in v_ans


@pytest.mark.asyncio
async def test_case_2_who_handles_backend(db_session):
    """Test 2: Who handles backend development?
    Expected: Arjun, deadline October 19.
    """
    user, workspace, meeting, transcript, conv = await _setup_regression_environment(db_session, "tc2")

    res = await RAGService.answer_question(
        session=db_session,
        workspace_id=workspace.id,
        user_id=user.id,
        conversation_id=conv.id,
        question_text="Who handles backend development?",
        meeting_id_filter=meeting.id,
    )

    ans = res.answer.lower()
    assert "arjun" in ans
    assert "october 19" in ans
    assert len(res.sources) > 0
    assert any("Arjun" in (s.get("text") or s.get("text_excerpt") or "") for s in res.sources)


@pytest.mark.asyncio
async def test_case_3_daniel_prepare(db_session):
    """Test 3: What must Daniel prepare?
    Expected: Marketing plan and customer feedback form, deadline October 21.
    """
    user, workspace, meeting, transcript, conv = await _setup_regression_environment(db_session, "tc3")

    res = await RAGService.answer_question(
        session=db_session,
        workspace_id=workspace.id,
        user_id=user.id,
        conversation_id=conv.id,
        question_text="What must Daniel prepare?",
        meeting_id_filter=meeting.id,
    )

    ans = res.answer.lower()
    assert "daniel" in ans
    assert "marketing plan" in ans
    assert "customer feedback form" in ans
    assert "october 21" in ans
    assert len(res.sources) > 0
    assert any("Daniel" in (s.get("text") or s.get("text_excerpt") or "") for s in res.sources)


@pytest.mark.asyncio
async def test_case_4_sara_deadline(db_session):
    """Test 4: What is Sara's deadline?
    Expected: October 20.
    """
    user, workspace, meeting, transcript, conv = await _setup_regression_environment(db_session, "tc4")

    res = await RAGService.answer_question(
        session=db_session,
        workspace_id=workspace.id,
        user_id=user.id,
        conversation_id=conv.id,
        question_text="What is Sara's deadline?",
        meeting_id_filter=meeting.id,
    )

    ans = res.answer.lower()
    assert "october 20" in ans
    assert len(res.sources) > 0


@pytest.mark.asyncio
async def test_case_5_unsupported_clinic_opening_time(db_session):
    """Test 5: What is the clinic's opening time?
    Expected: State that this information is not present in the supplied meeting transcript.
    Ensure citations are not fabricated for missing information.
    """
    user, workspace, meeting, transcript, conv = await _setup_regression_environment(db_session, "tc5")

    res = await RAGService.answer_question(
        session=db_session,
        workspace_id=workspace.id,
        user_id=user.id,
        conversation_id=conv.id,
        question_text="What is the clinic's opening time?",
        meeting_id_filter=meeting.id,
    )

    ans = res.answer.lower()
    assert "couldn't find" in ans or "could not find" in ans or "not present in" in ans or "could not be found" in ans
    # Crucial: Unrelated citations must not be presented as proof
    assert len(res.sources) == 0


@pytest.mark.asyncio
async def test_case_6_strict_multi_tenant_isolation(db_session):
    """Test 6: Verify that questions cannot retrieve transcripts from another user's meeting or workspace."""
    user_a, ws_a, meeting_a, _, conv_a = await _setup_regression_environment(db_session, "iso_a")
    user_b, ws_b, meeting_b, _, conv_b = await _setup_regression_environment(db_session, "iso_b")

    # User A asks question in Workspace A with Meeting A filter
    res_a = await RAGService.answer_question(
        session=db_session,
        workspace_id=ws_a.id,
        user_id=user_a.id,
        conversation_id=conv_a.id,
        question_text="What task is assigned to Sara?",
        meeting_id_filter=meeting_a.id,
    )

    for src in res_a.sources:
        assert src["meeting_id"] == str(meeting_a.id)
        assert src["meeting_id"] != str(meeting_b.id)

    # Cross-workspace conversation access should be rejected
    with pytest.raises(ValueError):
        await RAGService.answer_question(
            session=db_session,
            workspace_id=ws_a.id,
            user_id=user_a.id,
            conversation_id=conv_b.id,  # Belonging to Workspace B
            question_text="What task is assigned to Sara?",
        )
