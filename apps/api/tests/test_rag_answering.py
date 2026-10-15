import pytest
import uuid
from app.services.intelligence.mock_provider import MockLLMProvider
from app.services.rag.rag_service import RAGService
from app.models.chat import ChatConversation, ChatMessage
from app.models.meeting import Meeting
from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User

TEST_TRANSCRIPT_CONTEXT = """
RETRIEVED MEETING CONTEXT:
Meeting:
ConvoMind Real Test Meeting

Source #1:
Speaker: Speaker 1
Timestamp: 0.0s - 39.5s
Transcript:
Hello, this is a ConvoMind test meeting. Today we discussed the development of our AI meeting intelligence platform. We need to complete the billing integration by Friday. Rahul will test the Razorpay payment flow. The frontend team will verify the dashboard and action items. We decided that the first release should support meeting transcription, summaries, decisions, and action items. We also need to verify workspace security and make sure users cannot access another workspace's data. One important question is whether we should enable email notifications for every completed meeting. We will review this again tomorrow.
"""

@pytest.mark.asyncio
async def test_rag_deadline_question():
    provider = MockLLMProvider()
    res = await provider.generate_chat_response(
        messages=[{"role": "user", "content": "What needs to be completed by Friday?"}],
        system_prompt=TEST_TRANSCRIPT_CONTEXT,
    )
    assert res["answer"] == "The billing integration needs to be completed by Friday."

@pytest.mark.asyncio
async def test_rag_person_action_question():
    provider = MockLLMProvider()
    res = await provider.generate_chat_response(
        messages=[{"role": "user", "content": "What is Rahul responsible for?"}],
        system_prompt=TEST_TRANSCRIPT_CONTEXT,
    )
    assert res["answer"] == "Rahul will test the Razorpay payment flow."

@pytest.mark.asyncio
async def test_rag_decision_question():
    provider = MockLLMProvider()
    res = await provider.generate_chat_response(
        messages=[{"role": "user", "content": "What decision was made about the first release?"}],
        system_prompt=TEST_TRANSCRIPT_CONTEXT,
    )
    assert res["answer"] == "The first release should support meeting transcription, summaries, decisions, and action items."

@pytest.mark.asyncio
async def test_rag_unsupported_question():
    provider = MockLLMProvider()
    res = await provider.generate_chat_response(
        messages=[{"role": "user", "content": "Did they discuss microservice architecture?"}],
        system_prompt=TEST_TRANSCRIPT_CONTEXT,
    )
    assert res["answer"] == "I couldn't find that information in this meeting transcript."

@pytest.mark.asyncio
async def test_rag_empty_context_refusal():
    provider = MockLLMProvider()
    res = await provider.generate_chat_response(
        messages=[{"role": "user", "content": "What is the plan?"}],
        system_prompt="[NO RETRIEVED CONTEXT AVAILABLE]",
    )
    assert res["answer"] == "I couldn't find that information in this meeting transcript."

@pytest.mark.asyncio
async def test_rag_workspace_isolation(db_session):
    """Verify that RAG queries for Workspace A cannot access transcript chunks from Workspace B."""
    ws_a_id = uuid.uuid4()
    ws_b_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    # Querying workspace A with a conversation belonging to workspace B should raise ValueError / 404
    with pytest.raises(ValueError, match="Chat conversation"):
        await RAGService.answer_question(
            session=db_session,
            workspace_id=ws_a_id,
            user_id=user_id,
            conversation_id=conv_id,
            question_text="What needs to be completed by Friday?",
        )
