"""Comprehensive automated test suite for AI Meeting Intelligence."""

import uuid
from typing import Dict, Tuple
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import IntelligenceStatus, TranscriptStatus, WorkspaceRole
from app.models.intelligence import (
    ActionItem,
    Decision,
    MeetingIntelligenceJob,
    MeetingQuestion,
    MeetingSummary,
)
from app.models.meeting import Meeting, Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.workers.tasks.intelligence_tasks import (
    _async_process_meeting_intelligence,
    process_meeting_intelligence,
)


async def create_user_and_token(
    client: AsyncClient, name: str = "Test User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user data and JWT access token."""
    email = f"ai_{uuid.uuid4().hex[:8]}@convomind.ai"
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


@pytest.fixture
async def intelligence_fixture(client: AsyncClient) -> Dict:
    """Fixture creating workspace, members, meeting, speakers, and completed transcript with segments."""
    owner, t_owner = await create_user_and_token(client, "AI Owner")
    admin, t_admin = await create_user_and_token(client, "AI Admin")
    member, t_member = await create_user_and_token(client, "AI Member")
    guest, t_guest = await create_user_and_token(client, "AI Guest")
    stranger, t_stranger = await create_user_and_token(client, "AI Stranger")

    # Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Intelligence WS {uuid.uuid4().hex[:6]}"},
        headers=auth_header(t_owner),
    )
    assert ws_res.status_code == 201
    ws_id = uuid.UUID(ws_res.json()["id"])

    # Add members
    for u_obj, role in [
        (admin, WorkspaceRole.ADMIN.value),
        (member, WorkspaceRole.MEMBER.value),
        (guest, WorkspaceRole.GUEST.value),
    ]:
        res = await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"email": u_obj["email"], "role": role},
            headers=auth_header(t_owner),
        )
        assert res.status_code == 201

    # Create meeting
    m_res = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": str(ws_id), "title": "AI Architecture Sync"},
        headers=auth_header(t_owner),
    )
    assert m_res.status_code == 201
    meeting_id = uuid.UUID(m_res.json()["id"])

    # Seed speakers, transcript, and segments
    async with AsyncSessionLocal() as session:
        speaker_alice = Speaker(
            meeting_id=meeting_id,
            name="Alice",
            label="Speaker 1",
        )
        speaker_bob = Speaker(
            meeting_id=meeting_id,
            name="Bob",
            label="Speaker 2",
        )
        session.add_all([speaker_alice, speaker_bob])
        await session.flush()

        transcript = Transcript(
            meeting_id=meeting_id,
            workspace_id=ws_id,
            status=TranscriptStatus.COMPLETED,
            language="en",
            duration=90.0,
            full_text=(
                "Alice: We decided to deploy the new auth service on Friday. "
                "Bob: Should we implement rate limiting before the release? "
                "Alice: Yes, Bob will finalize the rate limiting configuration by tomorrow. "
                "Bob: What is our latency requirement? Alice: Under 200 milliseconds."
            ),
            word_count=40,
            provider="mock",
        )
        session.add(transcript)
        await session.flush()

        seg0 = TranscriptSegment(
            transcript_id=transcript.id,
            speaker_id=speaker_alice.id,
            sequence_order=0,
            start_time=0.0,
            end_time=15.0,
            text="We decided to deploy the new auth service on Friday.",
            confidence=0.98,
        )
        seg1 = TranscriptSegment(
            transcript_id=transcript.id,
            speaker_id=speaker_bob.id,
            sequence_order=1,
            start_time=16.0,
            end_time=30.0,
            text="Should we implement rate limiting before the release?",
            confidence=0.95,
        )
        seg2 = TranscriptSegment(
            transcript_id=transcript.id,
            speaker_id=speaker_alice.id,
            sequence_order=2,
            start_time=31.0,
            end_time=50.0,
            text="Yes, Bob will finalize the rate limiting configuration by tomorrow.",
            confidence=0.99,
        )
        seg3 = TranscriptSegment(
            transcript_id=transcript.id,
            speaker_id=speaker_bob.id,
            sequence_order=3,
            start_time=51.0,
            end_time=70.0,
            text="What is our latency requirement?",
            confidence=0.97,
        )
        seg4 = TranscriptSegment(
            transcript_id=transcript.id,
            speaker_id=speaker_alice.id,
            sequence_order=4,
            start_time=71.0,
            end_time=85.0,
            text="Under 200 milliseconds.",
            confidence=0.98,
        )
        session.add_all([seg0, seg1, seg2, seg3, seg4])
        await session.commit()

    return {
        "workspace_id": ws_id,
        "meeting_id": meeting_id,
        "owner": (owner, t_owner),
        "admin": (admin, t_admin),
        "member": (member, t_member),
        "guest": (guest, t_guest),
        "stranger": (stranger, t_stranger),
    }


class TestIntelligenceTrigger:
    """Test suite for triggering AI meeting intelligence processing."""

    async def test_trigger_intelligence_success(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Owner can successfully trigger AI intelligence processing."""
        meeting_id = intelligence_fixture["meeting_id"]
        _, t_owner = intelligence_fixture["owner"]

        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ) as mock_delay:
            res = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            assert res.status_code == 202
            data = res.json()
            assert data["meeting_id"] == str(meeting_id)
            assert data["status"] in ["QUEUED", "queued"]
            assert data["version"] == 1
            assert data["provider"] == "mock"
            mock_delay.assert_called_once()

    async def test_trigger_intelligence_no_completed_transcript(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Cannot trigger intelligence if meeting has no completed transcript."""
        ws_id = intelligence_fixture["workspace_id"]
        _, t_owner = intelligence_fixture["owner"]

        # Create meeting with no transcript
        m_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": str(ws_id), "title": "Empty Meeting"},
            headers=auth_header(t_owner),
        )
        m_id = m_res.json()["id"]

        res = await client.post(
            f"/api/v1/meetings/{m_id}/ai/process",
            headers=auth_header(t_owner),
        )
        assert res.status_code == 400
        assert "completed transcript" in res.json()["detail"].lower()

    async def test_trigger_intelligence_conflict_when_already_active(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Cannot trigger a new intelligence job while one is already queued or processing."""
        meeting_id = intelligence_fixture["meeting_id"]
        _, t_owner = intelligence_fixture["owner"]

        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ):
            first = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            assert first.status_code == 202

            second = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            assert second.status_code == 409
            assert "already in progress" in second.json()["detail"].lower()

    async def test_trigger_intelligence_rbac(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Validate RBAC: Owner, Admin, Member can trigger; Guest and Stranger are rejected."""
        meeting_id = intelligence_fixture["meeting_id"]
        _, t_guest = intelligence_fixture["guest"]
        _, t_stranger = intelligence_fixture["stranger"]

        # Guest -> 403 Forbidden
        guest_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/ai/process",
            headers=auth_header(t_guest),
        )
        assert guest_res.status_code == 403
        assert "guests are not permitted" in guest_res.json()["detail"].lower()

        # Stranger -> 404 Not Found
        stranger_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/ai/process",
            headers=auth_header(t_stranger),
        )
        assert stranger_res.status_code == 404


class TestIntelligenceJobStatus:
    """Test suite for retrieving intelligence job status."""

    async def test_get_job_status(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Retrieve job status for an existing intelligence job."""
        meeting_id = intelligence_fixture["meeting_id"]
        _, t_owner = intelligence_fixture["owner"]

        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ):
            res_trigger = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            assert res_trigger.status_code == 202
            job_id = res_trigger.json()["id"]

        # Query latest status
        status_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/ai/status",
            headers=auth_header(t_owner),
        )
        assert status_res.status_code == 200
        assert status_res.json()["id"] == job_id
        assert status_res.json()["status"] in ["QUEUED", "queued"]

        # Query specific job_id
        status_spec = await client.get(
            f"/api/v1/meetings/{meeting_id}/ai/status?job_id={job_id}",
            headers=auth_header(t_owner),
        )
        assert status_spec.status_code == 200
        assert status_spec.json()["id"] == job_id

    async def test_get_job_status_not_found(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """404 when no intelligence jobs have been run for the meeting."""
        ws_id = intelligence_fixture["workspace_id"]
        _, t_owner = intelligence_fixture["owner"]

        m_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": str(ws_id), "title": "Fresh Meeting"},
            headers=auth_header(t_owner),
        )
        m_id = m_res.json()["id"]

        res = await client.get(
            f"/api/v1/meetings/{m_id}/ai/status",
            headers=auth_header(t_owner),
        )
        assert res.status_code == 404


class TestIntelligenceTaskExecutionAndQueries:
    """Test end-to-end execution of the Celery intelligence pipeline and query endpoints."""

    async def test_full_intelligence_pipeline_and_endpoints(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Execute Celery task with mock provider and verify all generated intelligence entities."""
        meeting_id = intelligence_fixture["meeting_id"]
        _, t_owner = intelligence_fixture["owner"]
        _, t_member = intelligence_fixture["member"]

        # 1. Trigger intelligence job
        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ):
            trig_res = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            assert trig_res.status_code == 202
            job_id = trig_res.json()["id"]

        # 2. Execute the async intelligence pipeline directly
        result = await _async_process_meeting_intelligence(str(meeting_id), str(job_id))
        assert result["status"] == "completed"
        assert result["version"] == 1
        assert result["action_items_count"] > 0
        assert result["decisions_count"] > 0
        assert result["questions_count"] > 0

        # 3. Verify job status endpoint shows COMPLETED
        st_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/ai/status",
            headers=auth_header(t_member),
        )
        assert st_res.status_code == 200
        st_data = st_res.json()
        assert st_data["status"] in ["COMPLETED", "completed"]
        assert st_data["processing_duration"] is not None
        assert st_data["token_usage"] is not None

        # 4. Verify Summary endpoint
        sum_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/summary",
            headers=auth_header(t_member),
        )
        assert sum_res.status_code == 200
        sum_data = sum_res.json()
        assert sum_data["overview"]
        assert sum_data["detailed_summary"]
        assert len(sum_data["key_points"]) > 0
        assert len(sum_data["risks_and_concerns"]) > 0
        assert len(sum_data["requirements_and_notes"]) > 0
        assert len(sum_data["follow_up_suggestions"]) > 0
        assert sum_data["version"] == 1

        # 5. Verify Decisions endpoint
        dec_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/decisions",
            headers=auth_header(t_member),
        )
        assert dec_res.status_code == 200
        dec_data = dec_res.json()
        assert len(dec_data) > 0
        for d in dec_data:
            assert d["title"]
            assert d["context"]
            assert d["impact"]
            assert d["version"] == 1
            if d.get("timestamp_marker") is not None:
                assert d["source_segment_id"] is not None

        # 6. Verify Action Items endpoint
        act_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/action-items",
            headers=auth_header(t_member),
        )
        assert act_res.status_code == 200
        act_data = act_res.json()
        assert len(act_data) > 0
        for a in act_data:
            assert a["title"]
            assert a["status"] in ["OPEN", "open", "PENDING", "pending"]
            assert a["priority"] in ["LOW", "MEDIUM", "HIGH", "low", "medium", "high"]
            assert a["version"] == 1

        # 7. Verify Questions endpoint
        que_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/questions",
            headers=auth_header(t_member),
        )
        assert que_res.status_code == 200
        que_data = que_res.json()
        assert len(que_data) > 0
        for q in que_data:
            assert q["question"]
            assert q["is_resolved"] in [True, False]
            assert q["version"] == 1

        # 8. Verify Consolidated GET /meetings/{id}/ai bundle
        all_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/ai",
            headers=auth_header(t_member),
        )
        assert all_res.status_code == 200
        bundle = all_res.json()
        assert bundle["meeting_id"] == str(meeting_id)
        assert bundle["version"] == 1
        assert bundle["job"]["status"] in ["COMPLETED", "completed"]
        assert bundle["summary"]["overview"]
        assert len(bundle["decisions"]) == len(dec_data)
        assert len(bundle["action_items"]) == len(act_data)
        assert len(bundle["questions"]) == len(que_data)

    async def test_intelligence_regeneration_and_versioning(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Regenerating intelligence creates a new version while preserving the previous version."""
        meeting_id = intelligence_fixture["meeting_id"]
        _, t_owner = intelligence_fixture["owner"]

        # Run Version 1
        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ):
            v1_trig = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            v1_job_id = v1_trig.json()["id"]

        await _async_process_meeting_intelligence(str(meeting_id), str(v1_job_id))

        # Run Version 2
        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ):
            v2_trig = await client.post(
                f"/api/v1/meetings/{meeting_id}/ai/process",
                headers=auth_header(t_owner),
            )
            assert v2_trig.status_code == 202
            v2_job_id = v2_trig.json()["id"]
            assert v2_trig.json()["version"] == 2

        await _async_process_meeting_intelligence(str(meeting_id), str(v2_job_id))

        # Default query returns version 2
        res_latest = await client.get(
            f"/api/v1/meetings/{meeting_id}/ai",
            headers=auth_header(t_owner),
        )
        assert res_latest.status_code == 200
        assert res_latest.json()["version"] == 2

        # Explicit version 1 query returns version 1
        res_v1 = await client.get(
            f"/api/v1/meetings/{meeting_id}/ai?version=1",
            headers=auth_header(t_owner),
        )
        assert res_v1.status_code == 200
        assert res_v1.json()["version"] == 1

    async def test_intelligence_permanent_error_handling(
        self, client: AsyncClient, intelligence_fixture: Dict
    ):
        """Permanent LLM error marks job as FAILED with error message."""
        ws_id = intelligence_fixture["workspace_id"]
        _, t_owner = intelligence_fixture["owner"]

        # Create meeting with transcript containing simulation trigger
        m_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": str(ws_id), "title": "Error Meeting"},
            headers=auth_header(t_owner),
        )
        m_id = uuid.UUID(m_res.json()["id"])

        async with AsyncSessionLocal() as session:
            transcript = Transcript(
                meeting_id=m_id,
                workspace_id=ws_id,
                status=TranscriptStatus.COMPLETED,
                language="en",
                duration=10.0,
                full_text="[SIMULATE_PERMANENT_ERROR] Invalid content",
                word_count=4,
                provider="mock",
            )
            session.add(transcript)
            await session.commit()

        # Trigger job
        with patch(
            "app.workers.tasks.intelligence_tasks.process_meeting_intelligence.delay"
        ):
            trig = await client.post(
                f"/api/v1/meetings/{m_id}/ai/process",
                headers=auth_header(t_owner),
            )
            job_id = trig.json()["id"]

        # Run task
        with pytest.raises(Exception):
            await _async_process_meeting_intelligence(str(m_id), str(job_id))

        # Verify job marked as FAILED
        st_res = await client.get(
            f"/api/v1/meetings/{m_id}/ai/status",
            headers=auth_header(t_owner),
        )
        assert st_res.status_code == 200
        assert st_res.json()["status"] in ["FAILED", "failed"]
        err_msg = st_res.json()["error_message"].lower()
        assert "unrecoverable model fault" in err_msg or "simulated" in err_msg or "permanent" in err_msg
