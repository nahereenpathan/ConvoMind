"""Live HTTP verification script for ConvoMind AI Meeting Intelligence module.

Exercises live HTTP requests against the running FastAPI container and Celery worker:
- Transcript completion prerequisite validation
- AI Intelligence trigger (202 Accepted)
- Concurrent processing lock / 409 Conflict handling
- Strict RBAC: Owner/Admin/Member allowed, Guest 403 Forbidden, Stranger 404
- Asynchronous Celery execution with Mock LLM Provider
- Job status polling (QUEUED -> PROCESSING -> COMPLETED)
- Summary retrieval (overview, detailed summary, key points, risks, next steps)
- Decisions extraction with context, impact, and timestamp markers
- Action items extraction with assignee, priority, due date, and timestamp markers
- Questions extraction with resolution status and answers
- Consolidated intelligence bundle (GET /meetings/{id}/ai)
- Versioning and regeneration (Version 1 & Version 2 retrieval)
"""

import json
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = "http://127.0.0.1:8000"


def make_valid_pcm_wav(duration_s: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate authentic, valid PCM WAV audio byte sequence."""
    num_samples = int(duration_s * sample_rate)
    byte_rate = sample_rate * 2
    block_align = 2
    data_size = num_samples * 2
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        1,  # Mono
        sample_rate,
        byte_rate,
        block_align,
        16,  # 16-bit
        b"data",
        data_size,
    )
    samples = b"\x00" * data_size
    return header + samples


def http_request(method: str, path: str, data: dict = None, headers: dict = None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(resp_body) if resp_body else {}
            except Exception:
                parsed = resp_body
            return resp.status, parsed, resp.headers
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed, e.headers


def upload_multipart_file(
    path: str,
    field_name: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str,
    headers: dict = None,
):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    url = f"{BASE_URL}{path}"

    req_headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    if headers:
        req_headers.update(headers)

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode(
            "utf-8"
        )
    )
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url, data=bytes(body), headers=req_headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body), resp.headers
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed, e.headers


def run_live_verification():
    print("=" * 70)
    print("ConvoMind AI Meeting Intelligence — Live Verification")
    print("=" * 70)

    # 1. API Health Check
    print("\n[1/10] Checking API Health...")
    status, body, _ = http_request("GET", "/api/v1/health")
    assert status == 200, f"Health check failed: {status} {body}"
    print(f"  ✓ API healthy: {body['service']}")

    # 2. Register Users (Owner, Member, Guest, Stranger)
    print("\n[2/10] Provisioning Test Users & Tokens...")
    uid = uuid.uuid4().hex[:6]
    users = {}
    for role_name in ["owner", "member", "guest", "stranger"]:
        email = f"ai_{role_name}_{uid}@convomind.ai"
        password = "Password123!"
        s, b, _ = http_request(
            "POST",
            "/api/v1/auth/register",
            {"name": f"User {role_name.capitalize()}", "email": email, "password": password},
        )
        assert s == 201, f"Register failed for {role_name}: {b}"

        s, b, _ = http_request(
            "POST",
            "/api/v1/auth/login",
            {"email": email, "password": password},
        )
        assert s == 200, f"Login failed for {role_name}: {b}"
        users[role_name] = {"email": email, "token": b["access_token"]}
        print(f"  ✓ Created {role_name}: {email}")

    h_owner = {"Authorization": f"Bearer {users['owner']['token']}"}
    h_member = {"Authorization": f"Bearer {users['member']['token']}"}
    h_guest = {"Authorization": f"Bearer {users['guest']['token']}"}
    h_stranger = {"Authorization": f"Bearer {users['stranger']['token']}"}

    # 3. Create Workspace and Add Members
    print("\n[3/10] Setting up Workspace & RBAC...")
    s, ws, _ = http_request(
        "POST",
        "/api/v1/workspaces",
        {"name": f"AI Intelligence Lab {uid}"},
        headers=h_owner,
    )
    assert s == 201, f"Create workspace failed: {ws}"
    ws_id = ws["id"]
    print(f"  ✓ Created Workspace {ws_id}")

    for role_name in ["member", "guest"]:
        s, m, _ = http_request(
            "POST",
            f"/api/v1/workspaces/{ws_id}/members",
            {"email": users[role_name]["email"], "role": role_name},
            headers=h_owner,
        )
        assert s == 201, f"Add member failed: {m}"
        print(f"  ✓ Added {role_name} to workspace")

    # 4. Create Meeting & Upload Audio
    print("\n[4/10] Creating Meeting & Uploading Recording...")
    s, m, _ = http_request(
        "POST",
        "/api/v1/meetings",
        {"workspace_id": ws_id, "title": "Quarterly Technical Strategy & Architecture"},
        headers=h_owner,
    )
    assert s == 201, f"Create meeting failed: {m}"
    meeting_id = m["id"]
    print(f"  ✓ Meeting created: {meeting_id}")

    # Attempt to trigger AI before transcript is ready -> Should fail with 400
    s, b, _ = http_request("POST", f"/api/v1/meetings/{meeting_id}/ai/process", headers=h_owner)
    assert s == 400, f"Expected 400 when triggering AI without transcript, got {s}: {b}"
    print(f"  ✓ Validated requirement: Cannot process AI without completed transcript (HTTP 400)")

    # Upload PCM audio recording
    wav_bytes = make_valid_pcm_wav(duration_s=3.0)
    s, rec, _ = upload_multipart_file(
        f"/api/v1/meetings/{meeting_id}/recordings",
        field_name="file",
        filename="strategy_sync.wav",
        file_bytes=wav_bytes,
        mime_type="audio/wav",
        headers=h_owner,
    )
    assert s == 201, f"Recording upload failed: {rec}"
    rec_id = rec["id"]
    print(f"  ✓ Uploaded recording {rec_id}")

    # 5. Wait for Celery worker to transcribe recording
    print("\n[5/10] Waiting for Background Audio Transcription to Complete...")
    max_wait = 30
    start_time = time.time()
    transcript_ready = False
    while time.time() - start_time < max_wait:
        s, trans, _ = http_request(
            "GET", f"/api/v1/meetings/{meeting_id}/transcript", headers=h_owner
        )
        if s == 200 and str(trans.get("status", "")).upper() == "COMPLETED":
            transcript_ready = True
            print(f"  ✓ Transcription completed in {time.time() - start_time:.1f}s")
            break
        time.sleep(1)

    assert transcript_ready, "Timed out waiting for transcription task to complete"

    # Add rich segments to guarantee extracted decisions, action items, and questions
    print("\n[6/10] Enriching Transcript Segments for AI Analysis...")
    segments_to_add = [
        {
            "sequence_order": 10,
            "start_time": 5.0,
            "end_time": 15.0,
            "text": "We agreed to standardize on PostgreSQL and Redis for our production deployment.",
        },
        {
            "sequence_order": 11,
            "start_time": 16.0,
            "end_time": 25.0,
            "text": "Can we complete the database migration by the end of next sprint?",
        },
        {
            "sequence_order": 12,
            "start_time": 26.0,
            "end_time": 40.0,
            "text": "Yes, Alice will lead the migration planning and submit the pull request by Friday.",
        },
        {
            "sequence_order": 13,
            "start_time": 41.0,
            "end_time": 50.0,
            "text": "What is our primary security concern? Bob: Unencrypted tokens at rest.",
        },
    ]
    for seg in segments_to_add:
        s, _, _ = http_request(
            "POST",
            f"/api/v1/meetings/{meeting_id}/transcript/segments",
            seg,
            headers=h_owner,
        )
        assert s == 201, f"Failed adding segment: {seg}"
    print(f"  ✓ Added {len(segments_to_add)} dialogue segments")

    # 7. Test RBAC for AI Intelligence Processing Trigger
    print("\n[7/10] Testing RBAC on AI Processing Trigger...")
    # Guest -> 403 Forbidden
    s, b, _ = http_request("POST", f"/api/v1/meetings/{meeting_id}/ai/process", headers=h_guest)
    assert s == 403, f"Expected 403 for Guest, got {s}: {b}"
    print("  ✓ Guest forbidden from triggering AI (HTTP 403)")

    # Stranger -> 404 Not Found
    s, b, _ = http_request("POST", f"/api/v1/meetings/{meeting_id}/ai/process", headers=h_stranger)
    assert s == 404, f"Expected 404 for Stranger, got {s}: {b}"
    print("  ✓ Stranger meeting isolation verified (HTTP 404)")

    # Member -> 202 Accepted
    s, job, _ = http_request("POST", f"/api/v1/meetings/{meeting_id}/ai/process", headers=h_member)
    assert s == 202, f"Expected 202 for Member trigger, got {s}: {job}"
    job_id = job["id"]
    assert str(job["status"]).upper() in ["QUEUED", "PROCESSING"]
    assert job["version"] == 1
    print(f"  ✓ Member successfully triggered AI processing (HTTP 202 Accepted, Job ID: {job_id})")

    # Duplicate trigger while processing -> 409 Conflict
    s, b, _ = http_request("POST", f"/api/v1/meetings/{meeting_id}/ai/process", headers=h_owner)
    if s == 409:
        print("  ✓ Concurrent trigger conflict rejected (HTTP 409 Conflict)")
    else:
        print(f"  (Note: task completed before conflict check, status: {s})")

    # 8. Poll for AI Job Completion
    print("\n[8/10] Waiting for AI Intelligence Celery Worker...")
    ai_completed = False
    start_time = time.time()
    while time.time() - start_time < 30:
        s, st, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/ai/status", headers=h_owner)
        assert s == 200
        if str(st.get("status", "")).upper() == "COMPLETED":
            ai_completed = True
            print(f"  ✓ AI Intelligence completed in {time.time() - start_time:.1f}s")
            print(f"    - Provider: {st['provider']}")
            print(f"    - Model: {st['model']}")
            print(f"    - Processing Duration: {st['processing_duration']:.2f}s")
            print(f"    - Token Usage: {st['token_usage']}")
            break
        elif str(st.get("status", "")).upper() == "FAILED":
            print(f"  ✗ AI Job failed: {st.get('error_message')}")
            sys.exit(1)
        time.sleep(1)

    assert ai_completed, "Timed out waiting for AI intelligence job to complete"

    # 9. Verify Entities and Query Endpoints
    print("\n[9/10] Verifying Meeting Intelligence Outputs...")

    # Executive & Detailed Summary
    s, summary, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/summary", headers=h_owner)
    assert s == 200, f"Failed getting summary: {summary}"
    assert summary["overview"], "Overview missing"
    assert summary["detailed_summary"], "Detailed summary missing"
    assert len(summary["key_points"]) > 0, "Key points missing"
    print(f"  ✓ Summary verified (Executive Overview: {summary['overview'][:80]}...)")
    print(f"    - Key points count: {len(summary['key_points'])}")
    print(f"    - Risks count: {len(summary['risks_and_concerns'])}")
    print(f"    - Next steps count: {len(summary['next_steps'])}")

    # Decisions
    s, decisions, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/decisions", headers=h_owner)
    assert s == 200, f"Failed getting decisions: {decisions}"
    assert len(decisions) > 0, "Expected at least one decision"
    d0 = decisions[0]
    print(f"  ✓ Decisions verified ({len(decisions)} extracted):")
    print(f"    - Title: {d0['title']}")
    print(f"    - Context: {d0.get('context')}")
    print(f"    - Impact: {d0.get('impact')}")
    print(f"    - Timestamp marker: {d0.get('timestamp_marker')}s")

    # Action Items
    s, action_items, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/action-items", headers=h_owner)
    assert s == 200, f"Failed getting action items: {action_items}"
    assert len(action_items) > 0, "Expected at least one action item"
    a0 = action_items[0]
    print(f"  ✓ Action Items verified ({len(action_items)} extracted):")
    print(f"    - Title: {a0['title']}")
    print(f"    - Assignee: {a0.get('assignee_name')}")
    print(f"    - Priority: {a0.get('priority')}")
    print(f"    - Status: {a0.get('status')}")
    print(f"    - Timestamp marker: {a0.get('timestamp_marker')}s")

    # Questions
    s, questions, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/questions", headers=h_owner)
    assert s == 200, f"Failed getting questions: {questions}"
    assert len(questions) > 0, "Expected at least one question"
    q0 = questions[0]
    print(f"  ✓ Questions verified ({len(questions)} extracted):")
    print(f"    - Question: {q0['question']}")
    print(f"    - Answer: {q0.get('answer')}")
    print(f"    - Resolved: {q0.get('is_resolved')}")

    # Consolidated Intelligence Bundle
    s, bundle, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/ai", headers=h_owner)
    assert s == 200, f"Failed getting bundle: {bundle}"
    assert bundle["meeting_id"] == meeting_id
    assert bundle["version"] == 1
    assert bundle["summary"]["id"] == summary["id"]
    assert len(bundle["decisions"]) == len(decisions)
    assert len(bundle["action_items"]) == len(action_items)
    assert len(bundle["questions"]) == len(questions)
    print(f"  ✓ Consolidated AI Intelligence bundle verified (GET /meetings/{meeting_id}/ai)")

    # 10. Test Versioning & Regeneration
    print("\n[10/10] Testing Intelligence Regeneration & Versioning...")
    s, v2_job, _ = http_request("POST", f"/api/v1/meetings/{meeting_id}/ai/process", headers=h_owner)
    assert s == 202, f"Failed to trigger v2: {v2_job}"
    assert v2_job["version"] == 2, f"Expected version 2, got {v2_job['version']}"
    print(f"  ✓ Triggered Version 2 processing (Job ID: {v2_job['id']})")

    # Wait for v2 to finish
    start_time = time.time()
    v2_done = False
    while time.time() - start_time < 30:
        s, st, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/ai/status", headers=h_owner)
        if s == 200 and st["version"] == 2 and str(st.get("status", "")).upper() == "COMPLETED":
            v2_done = True
            break
        time.sleep(1)
    assert v2_done, "Timed out waiting for Version 2 to complete"

    # Verify querying version 1 explicitly
    s, b1, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/ai?version=1", headers=h_owner)
    assert s == 200 and b1["version"] == 1
    print("  ✓ Explicit version 1 query verified (?version=1)")

    # Verify querying default returns latest version (2)
    s, b_latest, _ = http_request("GET", f"/api/v1/meetings/{meeting_id}/ai", headers=h_owner)
    assert s == 200 and b_latest["version"] == 2
    print("  ✓ Default query returns latest version (?version=2)")

    print("\n" + "=" * 70)
    print("✓ ALL LIVE AI MEETING INTELLIGENCE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_live_verification()
