"""End-to-End Test for Marketing Campaign Planning Meeting AI Intelligence Pipeline & RAG Isolation."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.meeting import Meeting, Speaker, MeetingParticipant
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript, TranscriptSegment
from app.models.intelligence import MeetingIntelligenceJob, MeetingSummary, ActionItem, Decision, MeetingQuestion
from app.models.enums import WorkspaceRole, MeetingStatus, RecordingStatus, TranscriptStatus, IntelligenceStatus
from app.services.intelligence_service import IntelligenceService
from app.services.rag.rag_service import RAGService
from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
from app.workers.tasks.embedding_tasks import _async_process_transcript_embeddings
from app.models.chat import ChatConversation
from app.core.security import hash_password


@pytest.mark.asyncio
async def test_marketing_campaign_planning_pipeline_and_rag(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    test_workspace: Workspace,
):
    """End-to-end pipeline test for Marketing Campaign Planning Meeting."""
    ws_id = test_workspace.id
    user_id = test_workspace.created_by_id

    # 1. Create Meeting A: ConvoMind Real Test Meeting (Billing / Razorpay)
    m_a = Meeting(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        creator_id=user_id,
        title="ConvoMind Real Test Meeting",
        description="Discussion regarding billing integration, Razorpay testing, frontend verification, and security.",
        status=MeetingStatus.COMPLETED,
        platform="UPLOAD",
    )
    db_session.add(m_a)

    t_a = Transcript(
        id=uuid.uuid4(),
        meeting_id=m_a.id,
        workspace_id=ws_id,
        language="en",
        status=TranscriptStatus.COMPLETED,
        full_text="Rahul will test the Razorpay payment flow by Friday. Frontend team is verifying dashboard action items. Workspace security rules are strictly enforced.",
        word_count=22,
    )
    db_session.add(t_a)

    seg_a = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t_a.id,
        sequence_order=0,
        start_time=0.0,
        end_time=10.0,
        text="Rahul will test the Razorpay payment flow by Friday.",
    )
    db_session.add(seg_a)

    # 2. Create Meeting B: Marketing Campaign Planning Meeting
    m_b = Meeting(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        creator_id=user_id,
        title="Marketing Campaign Planning Meeting",
        description="Comprehensive planning session for new product launch campaign, social media marketing, demo video, budget, and channel strategy.",
        status=MeetingStatus.COMPLETED,
        platform="UPLOAD",
    )
    db_session.add(m_b)

    marketing_seg_texts = [
        "Welcome everyone to the Marketing Campaign Planning Meeting for our new product launch.",
        "We need to outline our primary social media marketing strategy across LinkedIn, Twitter, and YouTube.",
        "Priya will manage the production of the product demo video by next Tuesday.",
        "The total advertising budget of fifty thousand dollars has been approved by management.",
        "Our primary target audience consists of small business owners and software development leads.",
        "We are establishing the campaign launch timeline to begin on October first.",
        "Thank you team for finalizing the marketing channel strategy for Q4.",
    ]

    full_marketing_text = " ".join(marketing_seg_texts)

    t_b = Transcript(
        id=uuid.uuid4(),
        meeting_id=m_b.id,
        workspace_id=ws_id,
        language="en",
        status=TranscriptStatus.COMPLETED,
        full_text=full_marketing_text,
        word_count=len(full_marketing_text.split()),
    )
    db_session.add(t_b)

    for i, txt in enumerate(marketing_seg_texts):
        seg = TranscriptSegment(
            id=uuid.uuid4(),
            transcript_id=t_b.id,
            sequence_order=i,
            start_time=float(i * 10),
            end_time=float(i * 10 + 9),
            text=txt,
        )
        db_session.add(seg)

    await db_session.commit()

    # 3. Process AI Intelligence pipeline for Meeting B
    res_b = await _async_process_meeting_intelligence(str(m_b.id))
    assert res_b["status"] == "completed"

    # Process AI Intelligence pipeline for Meeting A
    res_a = await _async_process_meeting_intelligence(str(m_a.id))
    assert res_a["status"] == "completed"

    db_session.expunge_all()

    # 4. Verify API response for Meeting B (Marketing Campaign Planning Meeting)
    resp_b = await client.get(f"/api/v1/meetings/{m_b.id}/ai", headers=auth_headers)
    assert resp_b.status_code == 200
    intel_b = resp_b.json()

    assert intel_b["meeting_id"] == str(m_b.id)
    assert intel_b["workspace_id"] == str(ws_id)
    assert intel_b["summary"] is not None
    overview_text = intel_b["summary"]["overview"].lower()

    # Must contain marketing topics
    assert "marketing" in overview_text or "campaign" in overview_text or "social media" in overview_text or "budget" in overview_text

    # MUST NOT contain generic un-grounded engineering terms
    assert "microservice architecture" not in overview_text
    assert "production readiness" not in overview_text
    assert "api schema specifications" not in overview_text

    # 5. Verify database records for Meeting B
    sum_b_db = (await db_session.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == m_b.id))).scalar_one()
    assert sum_b_db.workspace_id == ws_id
    assert sum_b_db.meeting_id == m_b.id

    act_b_db = (await db_session.execute(select(ActionItem).where(ActionItem.meeting_id == m_b.id))).scalars().all()
    for act in act_b_db:
        assert act.workspace_id == ws_id
        assert act.meeting_id == m_b.id

    # 6. Process Vector Embeddings for RAG search
    await _async_process_transcript_embeddings(str(t_b.id))
    await _async_process_transcript_embeddings(str(t_a.id))

    # 7. Create Chat Conversation for Meeting B
    conv_b = ChatConversation(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        meeting_id=m_b.id,
        title="Marketing Meeting Q&A",
    )
    db_session.add(conv_b)

    # Create Chat Conversation for Meeting A
    conv_a = ChatConversation(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        meeting_id=m_a.id,
        title="Billing Meeting Q&A",
    )
    db_session.add(conv_a)
    await db_session.commit()

    # 8. Test RAG Questions against Meeting B
    q1_ans = await RAGService.answer_question(
        session=db_session,
        workspace_id=ws_id,
        user_id=user_id,
        conversation_id=conv_b.id,
        question_text="What is this meeting about?",
        meeting_id_filter=m_b.id,
    )
    assert "marketing" in q1_ans.answer.lower() or "campaign" in q1_ans.answer.lower() or "launch" in q1_ans.answer.lower()

    q2_ans = await RAGService.answer_question(
        session=db_session,
        workspace_id=ws_id,
        user_id=user_id,
        conversation_id=conv_b.id,
        question_text="What are the main topics discussed?",
        meeting_id_filter=m_b.id,
    )
    assert any(k in q2_ans.answer.lower() for k in ["social media", "budget", "video", "target", "audience", "marketing", "channel", "strategy", "launch"])

    q3_ans = await RAGService.answer_question(
        session=db_session,
        workspace_id=ws_id,
        user_id=user_id,
        conversation_id=conv_b.id,
        question_text="What was discussed about the launch campaign?",
        meeting_id_filter=m_b.id,
    )
    assert any(k in q3_ans.answer.lower() for k in ["timeline", "october", "campaign", "budget", "target", "audience", "launch", "marketing"])

    # 9. Verify Isolation: Ask Meeting A about "advertising budget"
    q_isolation = await RAGService.answer_question(
        session=db_session,
        workspace_id=ws_id,
        user_id=user_id,
        conversation_id=conv_a.id,
        question_text="What is the advertising budget?",
        meeting_id_filter=m_a.id,
    )
    assert "couldn't find" in q_isolation.answer.lower() or "not mentioned" in q_isolation.answer.lower()
