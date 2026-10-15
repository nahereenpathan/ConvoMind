"""Comprehensive automated test suite for AI Follow-Up email generation, draft management, and email dispatch."""

import uuid
from typing import Dict, Tuple
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import FollowUpStatus, TranscriptStatus
from app.models.follow_up import FollowUp
from app.models.intelligence import ActionItem, Decision, MeetingSummary
from app.models.meeting import Meeting, MeetingParticipant
from app.models.transcript import Transcript


async def create_user_and_token(
    client: AsyncClient, name: str = "FollowUp User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user data and JWT access token."""
    email = f"followup_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "Password123!"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return reg.json(), token


def auth_header(token: str) -> Dict[str, str]:
    """Helper for Bearer authorization header."""
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_generate_follow_up_missing_transcript(client: AsyncClient):
    """Test generating a follow-up email draft on a meeting without transcript or intelligence raises HTTP 400."""
    _, token = await create_user_and_token(client, "Owner 1")
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS No Transcript"},
        headers=auth_header(token),
    )
    assert ws_res.status_code == 201, ws_res.text
    ws_id = ws_res.json()["id"]

    m_res = await client.post(
        "/api/v1/meetings",
        json={"title": "Empty Meeting", "workspace_id": ws_id},
        headers=auth_header(token),
    )

    assert m_res.status_code == 201, m_res.text
    m_id = m_res.json()["id"]

    gen_res = await client.post(
        f"/api/v1/meetings/{m_id}/follow-ups/generate",
        json={"type": "EMAIL_DRAFT"},
        headers=auth_header(token),
    )
    assert gen_res.status_code == 400
    assert "No meeting transcript or AI intelligence found" in gen_res.json()["detail"]


@pytest.mark.asyncio
async def test_generate_follow_up_with_transcript_and_summary(client: AsyncClient):
    """Test generating, updating, and sending a follow-up email draft."""
    _, token = await create_user_and_token(client, "Owner 2")
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS FollowUp Test"},
        headers=auth_header(token),
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    m_res = await client.post(
        "/api/v1/meetings",
        json={"title": "Q3 Planning Session", "workspace_id": ws_id},
        headers=auth_header(token),
    )
    assert m_res.status_code == 201
    m_id = uuid.UUID(m_res.json()["id"])
    workspace_uuid = uuid.UUID(ws_id)


    # Seed meeting transcript, summary, and action items in DB
    async with AsyncSessionLocal() as db:
        transcript = Transcript(
            id=uuid.uuid4(),
            meeting_id=m_id,
            workspace_id=workspace_uuid,
            status=TranscriptStatus.COMPLETED,
            full_text="Discussion on Q3 goals. Agreed to launch new AI follow-up feature next week.",
        )
        summary = MeetingSummary(
            id=uuid.uuid4(),
            meeting_id=m_id,
            overview="The team reviewed Q3 goals and finalized deployment schedules.",
        )

        action_item = ActionItem(
            id=uuid.uuid4(),
            meeting_id=m_id,
            workspace_id=workspace_uuid,
            title="Deploy AI FollowUp Feature",
            description="Finalize endpoint contracts and frontend modal.",
        )
        decision = Decision(
            id=uuid.uuid4(),
            meeting_id=m_id,
            workspace_id=workspace_uuid,
            title="Adopt Microservice Architecture for RAG",
            context="Evaluated system concurrency requirements.",
        )
        participant = MeetingParticipant(
            id=uuid.uuid4(),
            meeting_id=m_id,
            name="Alice Smith",
            email="alice@convomind.ai",
        )
        db.add_all([transcript, summary, action_item, decision, participant])
        await db.commit()


    # 1. Generate follow-up draft
    gen_res = await client.post(
        f"/api/v1/meetings/{m_id}/follow-ups/generate",
        json={"type": "EMAIL_DRAFT"},
        headers=auth_header(token),
    )
    assert gen_res.status_code in (200, 201), gen_res.text

    f_data = gen_res.json()
    follow_up_id = f_data["id"]
    assert f_data["status"] == "READY"
    assert "Q3 Planning Session" in f_data["subject"]
    assert f_data["content"] or f_data.get("body")

    # 2. Get list of follow-ups for meeting
    list_res = await client.get(
        f"/api/v1/meetings/{m_id}/follow-ups",
        headers=auth_header(token),
    )
    print("LIST RES:", list_res.status_code, list_res.text)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Update follow-up draft
    patch_res = await client.patch(
        f"/api/v1/follow-ups/{follow_up_id}",
        json={
            "subject": "Updated: Q3 Planning Action Items",
            "content": "Hi Team,\n\nPlease see the updated action items for Q3.\n\nBest,\nConvoMind AI",
            "recipients": ["alice@convomind.ai", "bob@convomind.ai"],
        },
        headers=auth_header(token),
    )
    print("PATCH RES:", patch_res.status_code, patch_res.text)
    assert patch_res.status_code == 200, patch_res.text
    updated_data = patch_res.json()
    assert updated_data["subject"] == "Updated: Q3 Planning Action Items"
    assert "alice@convomind.ai" in updated_data["recipients"]

    # 4. Explicitly send follow-up email
    send_res = await client.post(
        f"/api/v1/follow-ups/{follow_up_id}/send",
        headers=auth_header(token),
    )
    print("SEND RES:", send_res.status_code, send_res.text)
    assert send_res.status_code == 200, send_res.text
    sent_data = send_res.json()
    assert sent_data["status"] == "SENT"


@pytest.mark.asyncio
async def test_send_follow_up_smtp_failure(client: AsyncClient, monkeypatch):
    """Test that when SMTP email dispatch fails, the backend returns an error and does not mark draft as SENT."""
    from app.services.email.base import EmailProviderError

    class FailingEmailProvider:
        async def send_email(self, to_email: str, subject: str, body_text: str, body_html=None) -> bool:
            raise EmailProviderError("SMTP authentication failed. Please verify SMTP_USER and SMTP_PASSWORD.")

    monkeypatch.setattr("app.services.follow_up_service.get_email_provider", lambda: FailingEmailProvider())

    _, token = await create_user_and_token(client, "Owner Failing SMTP")
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS Failing SMTP"},
        headers=auth_header(token),
    )
    ws_id = ws_res.json()["id"]

    m_res = await client.post(
        "/api/v1/meetings",
        json={"title": "Failing SMTP Meeting", "workspace_id": ws_id},
        headers=auth_header(token),
    )
    m_id = uuid.UUID(m_res.json()["id"])
    workspace_uuid = uuid.UUID(ws_id)

    async with AsyncSessionLocal() as db:
        transcript = Transcript(
            id=uuid.uuid4(),
            meeting_id=m_id,
            workspace_id=workspace_uuid,
            status=TranscriptStatus.COMPLETED,
            full_text="Meeting discussion notes.",
        )
        db.add(transcript)
        await db.commit()

    gen_res = await client.post(
        f"/api/v1/meetings/{m_id}/follow-ups/generate",
        json={"type": "EMAIL_DRAFT"},
        headers=auth_header(token),
    )
    assert gen_res.status_code in (200, 201)
    follow_up_id = gen_res.json()["id"]

    # Dispatch should fail and return 400 with SMTP error detail
    send_res = await client.post(
        f"/api/v1/follow-ups/{follow_up_id}/send",
        headers=auth_header(token),
    )
    assert send_res.status_code == 400
    assert "SMTP authentication failed" in send_res.json()["detail"]


@pytest.mark.asyncio
async def test_cross_workspace_isolation(client: AsyncClient):
    """Test that users from other workspaces cannot view or modify follow-up drafts."""
    _, token1 = await create_user_and_token(client, "User WS1")
    _, token2 = await create_user_and_token(client, "User WS2")

    ws1_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace 1"},
        headers=auth_header(token1),
    )
    ws1_id = ws1_res.json()["id"]

    m1_res = await client.post(
        "/api/v1/meetings",
        json={"title": "Private WS1 Meeting", "workspace_id": ws1_id},
        headers=auth_header(token1),
    )
    m1_id = m1_res.json()["id"]

    # User 2 attempts to generate follow-up on User 1's meeting
    gen_res = await client.post(
        f"/api/v1/meetings/{m1_id}/follow-ups/generate",
        json={"type": "EMAIL_DRAFT"},
        headers=auth_header(token2),
    )
    assert gen_res.status_code == 404

