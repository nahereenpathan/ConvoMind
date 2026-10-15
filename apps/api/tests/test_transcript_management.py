"""Comprehensive automated test suite for Transcript Management, Speakers, Search, and Exports."""

import json
import uuid
from typing import Dict, Tuple
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import TranscriptStatus, WorkspaceRole
from app.models.meeting import Meeting, Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


async def create_user_and_token(
    client: AsyncClient, name: str = "Test User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user data and JWT access token."""
    email = f"tm_{uuid.uuid4().hex[:8]}@convomind.ai"
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
async def transcript_fixture(client: AsyncClient) -> Dict:
    """Fixture creating workspace, members, meeting, transcript, and initial segments directly in DB."""
    owner, t_owner = await create_user_and_token(client, "WS Owner")
    admin, t_admin = await create_user_and_token(client, "WS Admin")
    member, t_member = await create_user_and_token(client, "WS Member")
    guest, t_guest = await create_user_and_token(client, "WS Guest")
    stranger, t_stranger = await create_user_and_token(client, "WS Stranger")

    # Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Transcript Mgmt WS {uuid.uuid4().hex[:6]}"},
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
        json={"workspace_id": str(ws_id), "title": "Quarterly Product Strategy"},
        headers=auth_header(t_owner),
    )
    assert m_res.status_code == 201
    meeting_id = uuid.UUID(m_res.json()["id"])

    # Seed transcript and initial segments in DB
    async with AsyncSessionLocal() as session:
        transcript = Transcript(
            meeting_id=meeting_id,
            workspace_id=ws_id,
            status=TranscriptStatus.COMPLETED,
            language="en",
            duration=45.0,
            full_text="Welcome everyone to the quarterly product review. Let's discuss our roadmap.",
            word_count=10,
            provider="mock",
        )
        session.add(transcript)
        await session.flush()

        seg0 = TranscriptSegment(
            transcript_id=transcript.id,
            sequence_order=0,
            start_time=0.0,
            end_time=5.0,
            text="Welcome everyone to the quarterly product review.",
            confidence=0.98,
        )
        seg1 = TranscriptSegment(
            transcript_id=transcript.id,
            sequence_order=1,
            start_time=5.5,
            end_time=12.0,
            text="Let's discuss our roadmap.",
            confidence=0.95,
        )
        session.add_all([seg0, seg1])
        await session.commit()
        transcript_id = transcript.id
        seg0_id = seg0.id
        seg1_id = seg1.id

    return {
        "workspace_id": ws_id,
        "meeting_id": meeting_id,
        "transcript_id": transcript_id,
        "seg0_id": seg0_id,
        "seg1_id": seg1_id,
        "owner": (owner, t_owner),
        "admin": (admin, t_admin),
        "member": (member, t_member),
        "guest": (guest, t_guest),
        "stranger": (stranger, t_stranger),
    }


# ============================================================================
# 1. Transcript Retrieval & Metadata Update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_meeting_transcript_success(client: AsyncClient, transcript_fixture: Dict):
    """Verify retrieving transcript with paginated segments and word counts."""
    f = transcript_fixture
    _, t_member = f["member"]

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript?page=1&page_size=10",
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(f["transcript_id"])
    assert data["status"] == "COMPLETED"
    assert data["total_segments"] == 2
    assert len(data["segments"]) == 2
    assert data["segments"][0]["sequence_order"] == 0
    assert "quarterly product review" in data["segments"][0]["text"]


@pytest.mark.asyncio
async def test_update_transcript_metadata_and_rbac(client: AsyncClient, transcript_fixture: Dict):
    """Verify language update works for owner/admin/member and is forbidden for guest."""
    f = transcript_fixture
    _, t_owner = f["owner"]
    _, t_member = f["member"]
    _, t_guest = f["guest"]
    _, t_stranger = f["stranger"]

    # Member updates language
    res = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/transcript",
        json={"language": "es-ES"},
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    assert res.json()["language"] == "es-ES"

    # Guest cannot update
    res_guest = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/transcript",
        json={"language": "fr-FR"},
        headers=auth_header(t_guest),
    )
    assert res_guest.status_code == 403

    # Stranger receives 404
    res_stranger = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/transcript",
        json={"language": "de-DE"},
        headers=auth_header(t_stranger),
    )
    assert res_stranger.status_code == 404


# ============================================================================
# 2. Speaker CRUD & Workspace User Association Tests
# ============================================================================


@pytest.mark.asyncio
async def test_speaker_crud_lifecycle(client: AsyncClient, transcript_fixture: Dict):
    """Test full speaker CRUD, user association, and RBAC."""
    f = transcript_fixture
    _, t_owner = f["owner"]
    member_user, t_member = f["member"]
    _, t_guest = f["guest"]

    # 1. Create speaker
    create_res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/speakers",
        json={
            "label": "SPEAKER_00",
            "name": "Sarah Connor",
            "user_id": member_user["id"],
        },
        headers=auth_header(t_member),
    )
    assert create_res.status_code == 201
    spk_data = create_res.json()
    speaker_id = spk_data["id"]
    assert spk_data["label"] == "SPEAKER_00"
    assert spk_data["name"] == "Sarah Connor"
    assert spk_data["user_id"] == member_user["id"]

    # 2. List speakers
    list_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/speakers",
        headers=auth_header(t_guest),  # Guest can read
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Get speaker details
    get_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/speakers/{speaker_id}",
        headers=auth_header(t_member),
    )
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Sarah Connor"

    # 4. Update speaker
    upd_res = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/speakers/{speaker_id}",
        json={"name": "Sarah J. Connor"},
        headers=auth_header(t_member),
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["name"] == "Sarah J. Connor"

    # 5. Guest cannot update speaker
    guest_upd = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/speakers/{speaker_id}",
        json={"name": "Hacker"},
        headers=auth_header(t_guest),
    )
    assert guest_upd.status_code == 403

    # 6. Delete speaker
    del_res = await client.delete(
        f"/api/v1/meetings/{f['meeting_id']}/speakers/{speaker_id}",
        headers=auth_header(t_owner),
    )
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_speaker_invalid_user_association(client: AsyncClient, transcript_fixture: Dict):
    """Verify associating speaker with non-workspace user returns 400."""
    f = transcript_fixture
    stranger_user, _ = f["stranger"]
    _, t_owner = f["owner"]

    res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/speakers",
        json={
            "label": "SPEAKER_01",
            "name": "Invalid User",
            "user_id": stranger_user["id"],
        },
        headers=auth_header(t_owner),
    )
    assert res.status_code == 400
    assert "workspace" in res.text.lower()


# ============================================================================
# 3. Segment CRUD, Reordering, and Aggregation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_segment_creation_and_insertion_ordering(client: AsyncClient, transcript_fixture: Dict):
    """Verify appending and inserting segments shifts sequence_order properly without collisions."""
    f = transcript_fixture
    _, t_member = f["member"]

    # 1. Append segment to end (no sequence_order provided)
    append_res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments",
        json={
            "start_time": 13.0,
            "end_time": 18.5,
            "text": "Any feedback on this Q3 timeline?",
            "confidence": 0.96,
        },
        headers=auth_header(t_member),
    )
    assert append_res.status_code == 201
    seg2 = append_res.json()
    assert seg2["sequence_order"] == 2

    # 2. Insert segment in the middle at sequence_order = 1
    insert_res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments",
        json={
            "sequence_order": 1,
            "start_time": 5.1,
            "end_time": 5.4,
            "text": "Thank you for the warm introduction.",
            "confidence": 0.99,
        },
        headers=auth_header(t_member),
    )
    assert insert_res.status_code == 201
    seg_inserted = insert_res.json()
    assert seg_inserted["sequence_order"] == 1

    # 3. Verify total segments and continuous sequence ordering 0, 1, 2, 3
    list_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments",
        headers=auth_header(t_member),
    )
    assert list_res.status_code == 200
    segments = list_res.json()["segments"]
    assert len(segments) == 4
    for idx, s in enumerate(segments):
        assert s["sequence_order"] == idx


@pytest.mark.asyncio
async def test_segment_update_recalculates_full_text(client: AsyncClient, transcript_fixture: Dict):
    """Verify editing segment text recalculates transcript full_text and word_count."""
    f = transcript_fixture
    _, t_member = f["member"]

    upd_res = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/{f['seg0_id']}",
        json={"text": "Greetings team and executive stakeholders."},
        headers=auth_header(t_member),
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["text"] == "Greetings team and executive stakeholders."

    # Verify parent transcript updated
    tr_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript",
        headers=auth_header(t_member),
    )
    assert tr_res.status_code == 200
    tr_data = tr_res.json()
    assert "Greetings team and executive stakeholders." in tr_data["full_text"]
    assert tr_data["word_count"] > 0


@pytest.mark.asyncio
async def test_segment_timestamp_validation(client: AsyncClient, transcript_fixture: Dict):
    """Verify invalid timestamps (end_time < start_time) are rejected with 422 or 400."""
    f = transcript_fixture
    _, t_member = f["member"]

    # In creation
    res_create = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments",
        json={
            "start_time": 20.0,
            "end_time": 10.0,
            "text": "Invalid timeline utterance",
        },
        headers=auth_header(t_member),
    )
    assert res_create.status_code == 422

    # In update
    res_update = await client.patch(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/{f['seg0_id']}",
        json={"start_time": 30.0, "end_time": 15.0},
        headers=auth_header(t_member),
    )
    assert res_update.status_code == 422


@pytest.mark.asyncio
async def test_segment_deletion_reindexes_remaining(client: AsyncClient, transcript_fixture: Dict):
    """Verify deleting a segment shifts subsequent segments down with no gaps."""
    f = transcript_fixture
    _, t_member = f["member"]

    # Initially has 2 segments (0, 1). Delete segment 0.
    del_res = await client.delete(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/{f['seg0_id']}",
        headers=auth_header(t_member),
    )
    assert del_res.status_code == 200

    # Remaining segment must now be sequence_order 0
    seg1_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/{f['seg1_id']}",
        headers=auth_header(t_member),
    )
    assert seg1_res.status_code == 200
    assert seg1_res.json()["sequence_order"] == 0


# ============================================================================
# 4. Batch Speaker Assignment Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batch_speaker_assignment(client: AsyncClient, transcript_fixture: Dict):
    """Verify assigning speaker to multiple segments in a single operation."""
    f = transcript_fixture
    _, t_owner = f["owner"]
    _, t_member = f["member"]

    # 1. Create a speaker
    spk_res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/speakers",
        json={"label": "SPEAKER_01", "name": "Keynote Speaker"},
        headers=auth_header(t_member),
    )
    assert spk_res.status_code == 201
    speaker_id = spk_res.json()["id"]

    # 2. Batch assign to seg0 and seg1
    batch_res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/batch-speaker",
        json={
            "segment_ids": [str(f["seg0_id"]), str(f["seg1_id"])],
            "speaker_id": speaker_id,
        },
        headers=auth_header(t_member),
    )
    assert batch_res.status_code == 200
    assert "2" in batch_res.json()["message"]

    # 3. Check segments have speaker populated
    tr_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript",
        headers=auth_header(t_member),
    )
    assert tr_res.status_code == 200
    for seg in tr_res.json()["segments"]:
        assert seg["speaker_id"] == speaker_id
        assert seg["speaker"]["name"] == "Keynote Speaker"

    # 4. Batch unassign
    clear_res = await client.post(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/batch-speaker",
        json={
            "segment_ids": [str(f["seg0_id"])],
            "speaker_id": None,
        },
        headers=auth_header(t_member),
    )
    assert clear_res.status_code == 200

    seg0_res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments/{f['seg0_id']}",
        headers=auth_header(t_member),
    )
    assert seg0_res.status_code == 200
    assert seg0_res.json()["speaker_id"] is None


# ============================================================================
# 5. Search Tests (In-Meeting & Workspace-Wide)
# ============================================================================


@pytest.mark.asyncio
async def test_meeting_segment_search(client: AsyncClient, transcript_fixture: Dict):
    """Verify in-meeting search by query parameter."""
    f = transcript_fixture
    _, t_member = f["member"]

    # Search for "roadmap" -> matches seg1
    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments?query=roadmap",
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_segments"] == 1
    assert "roadmap" in data["segments"][0]["text"].lower()

    # Search for nonexistent word
    res_empty = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/segments?query=nonexistentcrypticterm",
        headers=auth_header(t_member),
    )
    assert res_empty.status_code == 200
    assert res_empty.json()["total_segments"] == 0


@pytest.mark.asyncio
async def test_workspace_transcript_search(client: AsyncClient, transcript_fixture: Dict):
    """Verify workspace-wide search across meeting transcripts."""
    f = transcript_fixture
    _, t_guest = f["guest"]
    _, t_stranger = f["stranger"]

    # Guest can search
    res = await client.get(
        f"/api/v1/workspaces/{f['workspace_id']}/transcripts/search?q=quarterly",
        headers=auth_header(t_guest),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] >= 1
    assert len(data["results"]) >= 1
    assert data["results"][0]["meeting_id"] == str(f["meeting_id"])

    # Stranger receives 404
    stranger_res = await client.get(
        f"/api/v1/workspaces/{f['workspace_id']}/transcripts/search?q=quarterly",
        headers=auth_header(t_stranger),
    )
    assert stranger_res.status_code == 404


# ============================================================================
# 6. Multi-Format Export Tests (TXT, Markdown, SRT, WebVTT, JSON)
# ============================================================================


@pytest.mark.asyncio
async def test_export_transcript_txt(client: AsyncClient, transcript_fixture: Dict):
    """Verify plain text export with timestamps."""
    f = transcript_fixture
    _, t_member = f["member"]

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/export?format=txt",
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    assert "Quarterly Product Strategy" in res.text
    assert "[00:00:00.000]" in res.text


@pytest.mark.asyncio
async def test_export_transcript_markdown(client: AsyncClient, transcript_fixture: Dict):
    """Verify markdown export with headers."""
    f = transcript_fixture
    _, t_guest = f["guest"]  # Guest can export

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/export?format=markdown",
        headers=auth_header(t_guest),
    )
    assert res.status_code == 200
    assert "text/markdown" in res.headers["content-type"]
    assert "# Meeting Transcript:" in res.text
    assert "### [" in res.text


@pytest.mark.asyncio
async def test_export_transcript_srt(client: AsyncClient, transcript_fixture: Dict):
    """Verify SubRip .srt format with comma milliseconds."""
    f = transcript_fixture
    _, t_member = f["member"]

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/export?format=srt",
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    assert "00:00:00,000 --> 00:00:05,000" in res.text


@pytest.mark.asyncio
async def test_export_transcript_vtt(client: AsyncClient, transcript_fixture: Dict):
    """Verify WebVTT format with dot milliseconds."""
    f = transcript_fixture
    _, t_member = f["member"]

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/export?format=vtt",
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    assert "WEBVTT" in res.text
    assert "00:00:00.000 --> 00:00:05.000" in res.text


@pytest.mark.asyncio
async def test_export_transcript_json(client: AsyncClient, transcript_fixture: Dict):
    """Verify structured JSON export."""
    f = transcript_fixture
    _, t_member = f["member"]

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/export?format=json",
        headers=auth_header(t_member),
    )
    assert res.status_code == 200
    data = json.loads(res.text)
    assert data["meeting_id"] == str(f["meeting_id"])
    assert len(data["segments"]) == 2
    assert data["segments"][0]["sequence_order"] == 0


@pytest.mark.asyncio
async def test_export_unsupported_format(client: AsyncClient, transcript_fixture: Dict):
    """Verify unsupported export format produces 422 validation error."""
    f = transcript_fixture
    _, t_member = f["member"]

    res = await client.get(
        f"/api/v1/meetings/{f['meeting_id']}/transcript/export?format=mp4",
        headers=auth_header(t_member),
    )
    assert res.status_code == 422
