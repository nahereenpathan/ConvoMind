import pytest
import uuid
from app.services.intelligence.mock_provider import MockLLMProvider

TEST_TRANSCRIPT_TEXT = (
    "Hello, this is a ConvoMind test meeting. "
    "Today we discussed the development of our AI meeting intelligence platform. "
    "We need to complete the billing integration by Friday. "
    "Rahul will test the Razorpay payment flow. "
    "The frontend team will verify the dashboard and action items. "
    "We decided that the first release should support meeting transcription, summaries, decisions, and action items. "
    "We also need to verify workspace security and make sure users cannot access another workspace's data. "
    "One important question is whether we should enable email notifications for every completed meeting. "
    "We will review this again tomorrow."
)

@pytest.mark.asyncio
async def test_mock_llm_provider_grounded_extraction():
    """Verify that MockLLMProvider extracts 100% real content from transcript without mock text."""
    provider = MockLLMProvider()
    segments = [
        {"start_time": 0.0, "end_time": 5.0, "text": "Hello, this is a ConvoMind test meeting."},
        {"start_time": 5.0, "end_time": 10.0, "text": "We need to complete the billing integration by Friday."},
        {"start_time": 10.0, "end_time": 15.0, "text": "Rahul will test the Razorpay payment flow."},
    ]

    output = await provider.generate_meeting_intelligence(
        transcript_text=TEST_TRANSCRIPT_TEXT,
        segments=segments,
    )

    # 1. Executive Summary ground check
    assert "ConvoMind" in output.executive_summary or "billing" in output.executive_summary

    # 2. Action Items ground check
    tasks = [a.task.lower() for a in output.action_items]
    assert any("billing integration" in t for t in tasks)
    assert any("razorpay" in t for t in tasks)
    assert any("frontend" in t for t in tasks)

    # 3. Decisions ground check
    decisions = [d.decision.lower() for d in output.decisions]
    assert any("first release should support" in d for d in decisions)

    # 4. Questions ground check
    questions = [q.question.lower() for q in output.questions]
    assert any("email notifications" in q for q in questions)

    # 5. ZERO hardcoded mock data assertion
    full_output_str = str(output).lower()
    assert "finalize api schema" not in full_output_str
    assert "microservice architecture" not in full_output_str
    assert "deploy monitoring metrics" not in full_output_str
    assert "project deliverables" not in full_output_str
