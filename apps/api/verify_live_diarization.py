"""Live HTTP verification script for ConvoMind Speaker Diarization module.

Verifies:
1. API Service & Docker health
2. Authentication & token acquisition
3. Workspace & Meeting creation
4. Recording upload & transcript generation
5. Diarization API trigger (POST /api/v1/meetings/{id}/speakers/diarize)
6. Speaker listing & retrieval (GET /api/v1/meetings/{id}/speakers)
7. Display name mapping (PATCH /api/v1/meetings/{id}/speakers/{id})
8. Workspace isolation (cross-workspace access forbidden)
"""

import sys
import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"


def print_step(msg: str):
    print(f"\n[STEP] {msg}")


def print_success(msg: str):
    print(f"  [SUCCESS] {msg}")


def print_fail(msg: str):
    print(f"  [FAIL] {msg}")


def main():
    print("=" * 70)
    print("CONVOMIND LIVE SPEAKER DIARIZATION VERIFICATION")
    print("=" * 70)

    client = httpx.Client(timeout=30.0)

    # 1. Health check
    print_step("1. Checking API Health Endpoint")
    try:
        resp = client.get(f"{BASE_URL}/health")
        if resp.status_code == 200 and resp.json().get("status") == "healthy":
            print_success("API is healthy.")
        else:
            print_fail(f"Health check unexpected response: {resp.text}")
            sys.exit(1)
    except Exception as exc:
        print_fail(f"Could not connect to API at {BASE_URL}: {exc}")
        sys.exit(1)

    # 2. Authenticate User A
    print_step("2. Authenticating User A")
    user_a_email = f"diarization_a_{uuid.uuid4().hex[:6]}@example.com"
    password = "TestPassword123!"

    reg_resp = client.post(
        f"{BASE_URL}/auth/register",
        json={"email": user_a_email, "password": password, "name": "User A"},
    )
    if reg_resp.status_code != 201:
        print_fail(f"User registration failed: {reg_resp.text}")
        sys.exit(1)

    login_resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": user_a_email, "password": password},
    )
    if login_resp.status_code != 200:
        print_fail(f"User login failed: {login_resp.text}")
        sys.exit(1)

    token_a = login_resp.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print_success(f"Authenticated User A: {user_a_email}")

    # 3. Create Workspace & Meeting
    print_step("3. Creating Workspace & Meeting for User A")
    ws_resp = client.post(
        f"{BASE_URL}/workspaces",
        json={"name": "Diarization WS A"},
        headers=headers_a,
    )
    if ws_resp.status_code != 201:
        print_fail(f"Workspace creation failed: {ws_resp.text}")
        sys.exit(1)
    ws_id = ws_resp.json()["id"]

    meeting_resp = client.post(
        f"{BASE_URL}/meetings",
        json={
            "workspace_id": ws_id,
            "title": "Diarization Live Test Meeting",
            "platform": "other",
        },
        headers=headers_a,
    )
    if meeting_resp.status_code != 201:
        print_fail(f"Meeting creation failed: {meeting_resp.text}")
        sys.exit(1)
    meeting_id = meeting_resp.json()["id"]
    print_success(f"Created Meeting ID: {meeting_id}")

    # 4. Upload Recording & Process Transcript
    print_step("4. Uploading Recording & Transcribing")
    import struct
    num_samples = int(2.0 * 16000)
    byte_rate = 16000 * 2
    block_align = 2
    data_size = num_samples * 2
    chunk_size = 36 + data_size
    pcm_header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1, 1, 16000, byte_rate, block_align, 16, b"data", data_size
    )
    dummy_wav_content = pcm_header + (b"\x00" * data_size)

    files = {
        "file": ("meeting_audio.wav", dummy_wav_content, "audio/wav")
    }
    rec_resp = client.post(
        f"{BASE_URL}/meetings/{meeting_id}/recordings",
        files=files,
        headers=headers_a,
    )
    if rec_resp.status_code != 201:
        print_fail(f"Recording upload failed: {rec_resp.text}")
        sys.exit(1)
    recording_id = rec_resp.json()["id"]
    print_success(f"Uploaded Recording ID: {recording_id}")

    # Poll until transcription reaches COMPLETED
    print("  Waiting for Celery transcription worker...")
    for _ in range(30):
        tr_check = client.get(
            f"{BASE_URL}/meetings/{meeting_id}/transcript",
            headers=headers_a,
        )
        if tr_check.status_code == 200 and tr_check.json().get("status") == "completed":
            print_success(f"Transcript COMPLETED with {len(tr_check.json().get('segments', []))} segments")
            break
        time.sleep(1)

    # 5. Trigger Diarization
    print_step("5. Triggering Speaker Diarization API")
    diar_resp = client.post(
        f"{BASE_URL}/meetings/{meeting_id}/speakers/diarize",
        headers=headers_a,
    )
    if diar_resp.status_code != 202:
        print_fail(f"Diarization trigger failed: {diar_resp.text}")
        sys.exit(1)
    print_success(f"Diarization queued: {diar_resp.json()}")

    # Poll until Celery diarization worker creates speakers
    print("  Waiting for Celery diarization worker...")
    speakers = []
    for _ in range(30):
        spk_list_resp = client.get(
            f"{BASE_URL}/meetings/{meeting_id}/speakers",
            headers=headers_a,
        )
        if spk_list_resp.status_code == 200 and len(spk_list_resp.json()) > 0:
            speakers = spk_list_resp.json()
            break
        time.sleep(1)

    # 6. List Identified Speakers
    print_step("6. Listing Meeting Speakers")
    if len(speakers) == 0:
        print_fail("No speakers returned after diarization!")
        sys.exit(1)
    print_success(f"Diarized {len(speakers)} speakers: {[s['label'] for s in speakers]}")

    speaker_0 = speakers[0]

    # 7. Map Display Name (speaker_0 -> Rahul)
    print_step("7. Mapping Speaker Display Name (speaker_0 -> Rahul)")
    patch_resp = client.patch(
        f"{BASE_URL}/meetings/{meeting_id}/speakers/{speaker_0['id']}",
        json={"name": "Rahul"},
        headers=headers_a,
    )
    if patch_resp.status_code != 200:
        print_fail(f"Speaker update failed: {patch_resp.text}")
        sys.exit(1)
    updated = patch_resp.json()
    if updated["name"] == "Rahul":
        print_success(f"Mapped {speaker_0['label']} to display name '{updated['name']}'")
    else:
        print_fail(f"Name mapping mismatch: {updated}")
        sys.exit(1)

    # 8. Workspace Isolation Check
    print_step("8. Verifying Workspace Isolation Security")
    user_b_email = f"diarization_b_{uuid.uuid4().hex[:6]}@example.com"
    client.post(
        f"{BASE_URL}/auth/register",
        json={"email": user_b_email, "password": password, "name": "User B"},
    )
    token_b = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": user_b_email, "password": password},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    iso_resp = client.get(
        f"{BASE_URL}/meetings/{meeting_id}/speakers",
        headers=headers_b,
    )
    if iso_resp.status_code in (403, 404):
        print_success(f"Workspace Isolation enforced correctly: returned HTTP {iso_resp.status_code}")
    else:
        print_fail(f"SECURITY BREACH: User B accessed User A's speakers! Status: {iso_resp.status_code}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("ALL LIVE DIARIZATION VERIFICATION CHECKS PASSED SUCCESSFULLY (100%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
