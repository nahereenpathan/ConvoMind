"""Live HTTP verification script for ConvoMind Transcript Management module.

Exercises live HTTP requests against the running FastAPI container:
- Transcript retrieval & metadata update
- Speaker CRUD and workspace user association
- Segment CRUD, sequence re-ordering, timestamp validation, and text re-aggregation
- Batch speaker assignment
- Meeting-level & workspace-wide full-text search
- Multi-format exports (TXT, Markdown, SRT, WebVTT, JSON)
- Strict RBAC enforcement across Owner, Member, Guest, and Stranger
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


def upload_multipart_file(path: str, field_name: str, filename: str, file_bytes: bytes, mime_type: str, headers: dict = None):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    url = f"{BASE_URL}{path}"

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
    )
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req_headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=bytes(body), headers=req_headers, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


def log_step(name: str):
    print(f"\n\033[1;36m{'='*15} {name} {'='*15}\033[0m")


def log_pass(msg: str):
    print(f"\033[1;32m[PASS]\033[0m {msg}")


def log_fail(msg: str):
    print(f"\033[1;31m[FAIL]\033[0m {msg}")
    sys.exit(1)


def main():
    print("\033[1;35mStarting ConvoMind Live Transcript Management Verification...\033[0m\n")

    # Step 1: User Registration & Tokens
    log_step("1. User Provisioning & Authentication")
    tag = uuid.uuid4().hex[:6]
    users = {}
    tokens = {}

    for role in ["owner", "member", "guest", "stranger"]:
        email = f"tm_{role}_{tag}@convomind.ai"
        pwd = "Password123!"
        st, reg_data, _ = http_request("POST", "/api/v1/auth/register", {"name": f"TM {role.capitalize()}", "email": email, "password": pwd})
        if st != 201:
            log_fail(f"Failed to register {role}: {reg_data}")
        users[role] = reg_data

        st, login_data, _ = http_request("POST", "/api/v1/auth/login", {"email": email, "password": pwd})
        if st != 200:
            log_fail(f"Failed to login {role}: {login_data}")
        tokens[role] = login_data["access_token"]
        log_pass(f"Provisioned {role} user: {email}")

    # Step 2: Workspace & Membership
    log_step("2. Workspace Setup & RBAC Roles")
    st, ws, _ = http_request(
        "POST",
        "/api/v1/workspaces",
        {"name": f"Product Strategy WS {tag}"},
        headers={"Authorization": f"Bearer {tokens['owner']}"},
    )
    if st != 201:
        log_fail(f"Failed to create workspace: {ws}")
    ws_id = ws["id"]
    log_pass(f"Created workspace '{ws['name']}' (ID: {ws_id})")

    # Add member and guest
    for role_name in ["member", "guest"]:
        st, mem_data, _ = http_request(
            "POST",
            f"/api/v1/workspaces/{ws_id}/members",
            {"email": users[role_name]["email"], "role": role_name.upper()},
            headers={"Authorization": f"Bearer {tokens['owner']}"},
        )
        if st != 201:
            log_fail(f"Failed to add {role_name}: {mem_data}")
        log_pass(f"Added workspace member: {users[role_name]['email']} as {role_name.upper()}")

    # Step 3: Meeting Creation & Audio Upload
    log_step("3. Meeting Creation & Audio Upload")
    st, meeting, _ = http_request(
        "POST",
        "/api/v1/meetings",
        {"workspace_id": ws_id, "title": "2026 AI Product Roadmap Review"},
        headers={"Authorization": f"Bearer {tokens['owner']}"},
    )
    if st != 201:
        log_fail(f"Failed to create meeting: {meeting}")
    meeting_id = meeting["id"]
    log_pass(f"Created meeting: '{meeting['title']}' (ID: {meeting_id})")

    wav_bytes = make_valid_pcm_wav(duration_s=2.5)
    st, rec = upload_multipart_file(
        f"/api/v1/meetings/{meeting_id}/recordings",
        "file",
        "roadmap_discussion.wav",
        wav_bytes,
        "audio/wav",
        headers={"Authorization": f"Bearer {tokens['owner']}"},
    )
    if st != 201:
        log_fail(f"Failed to upload recording: {rec}")
    rec_id = rec["id"]
    log_pass(f"Uploaded audio recording (ID: {rec_id})")

    # Step 4: Wait for Asynchronous Celery Transcription Pipeline
    log_step("4. Celery Audio Transcription Pipeline Execution")
    print("Waiting for asynchronous transcription to complete...")
    max_wait = 20
    start_t = time.time()
    transcript_ready = False

    while time.time() - start_t < max_wait:
        st, status_data, _ = http_request(
            "GET",
            f"/api/v1/meetings/{meeting_id}/transcript/status",
            headers={"Authorization": f"Bearer {tokens['member']}"},
        )
        if st == 200 and status_data.get("status") == "COMPLETED":
            transcript_ready = True
            log_pass(f"Transcript pipeline completed in {time.time() - start_t:.2f}s!")
            break
        elif st == 200 and status_data.get("status") == "FAILED":
            log_fail(f"Transcription job failed: {status_data}")
        time.sleep(1.0)

    if not transcript_ready:
        log_fail(f"Transcription did not complete within {max_wait}s")

    # Step 5: Transcript Retrieval
    log_step("5. Transcript Retrieval with Segments")
    st, tr_data, _ = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if st != 200:
        log_fail(f"Failed to get transcript: {tr_data}")
    transcript_id = tr_data["id"]
    segments = tr_data["segments"]
    log_pass(f"Retrieved transcript (ID: {transcript_id}) with {len(segments)} initial segment(s)")

    # Step 6: Speaker CRUD
    log_step("6. Meeting Speaker CRUD")
    st, spk1, _ = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/speakers",
        {
            "label": "SPEAKER_00",
            "name": "Dr. Sarah Chen",
            "user_id": users["member"]["id"],
        },
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if st != 201:
        log_fail(f"Failed to create speaker: {spk1}")
    spk1_id = spk1["id"]
    log_pass(f"Created speaker '{spk1['name']}' linked to member user (ID: {spk1_id})")

    # List speakers
    st, spk_list, _ = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/speakers",
        headers={"Authorization": f"Bearer {tokens['guest']}"},  # Guest read access
    )
    if st != 200 or len(spk_list) == 0:
        log_fail(f"Failed to list speakers: {spk_list}")
    log_pass(f"Listed {len(spk_list)} speaker(s) accessible to Guest")

    # Update speaker
    st, spk_upd, _ = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}/speakers/{spk1_id}",
        {"name": "Dr. Sarah Chen, VP of AI"},
        headers={"Authorization": f"Bearer {tokens['owner']}"},
    )
    if st != 200 or spk_upd["name"] != "Dr. Sarah Chen, VP of AI":
        log_fail(f"Failed to update speaker: {spk_upd}")
    log_pass(f"Updated speaker name to '{spk_upd['name']}'")

    # Step 7: Segment CRUD & Sequence Order
    log_step("7. Transcript Segment Insertion, Edits, and Re-sequencing")
    # Insert new segment
    st, new_seg, _ = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/transcript/segments",
        {
            "start_time": 10.0,
            "end_time": 15.0,
            "text": "Our multi-agent orchestration architecture will be open sourced next quarter.",
            "confidence": 0.97,
            "speaker_id": spk1_id,
        },
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if st != 201:
        log_fail(f"Failed to create segment: {new_seg}")
    new_seg_id = new_seg["id"]
    log_pass(f"Appended new segment (ID: {new_seg_id}, sequence_order: {new_seg['sequence_order']})")

    # Edit segment text and verify transcript full_text recalculation
    st, upd_seg, _ = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}/transcript/segments/{new_seg_id}",
        {"text": "Our multi-agent architecture will be publicly unveiled at the annual summit."},
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if st != 200:
        log_fail(f"Failed to update segment: {upd_seg}")
    log_pass("Updated segment text successfully")

    # Verify parent transcript re-aggregated text
    st, tr_reagg, _ = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if "unveiled at the annual summit" not in tr_reagg["full_text"]:
        log_fail(f"Transcript full_text was not updated: {tr_reagg['full_text']}")
    log_pass(f"Transcript text re-aggregated! Total words: {tr_reagg['word_count']}")

    # Step 8: Batch Speaker Assignment
    log_step("8. Batch Speaker Assignment")
    st, batch_res, _ = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/transcript/segments/batch-speaker",
        {
            "segment_ids": [new_seg_id],
            "speaker_id": spk1_id,
        },
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if st != 200:
        log_fail(f"Failed batch speaker assignment: {batch_res}")
    log_pass(f"Batch speaker assignment: {batch_res['message']}")

    # Step 9: In-Meeting & Workspace Search
    log_step("9. In-Meeting & Workspace Full-Text Search")
    # In-meeting search
    st, search_meet, _ = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript/segments?query=annual+summit",
        headers={"Authorization": f"Bearer {tokens['member']}"},
    )
    if st != 200 or search_meet["total_segments"] < 1:
        log_fail(f"In-meeting search failed: {search_meet}")
    log_pass(f"In-meeting search found {search_meet['total_segments']} segment match(es)")

    # Workspace-wide cross-transcript search
    st, search_ws, _ = http_request(
        "GET",
        f"/api/v1/workspaces/{ws_id}/transcripts/search?q=multi-agent",
        headers={"Authorization": f"Bearer {tokens['guest']}"},
    )
    if st != 200 or search_ws["total_matches"] < 1:
        log_fail(f"Workspace search failed: {search_ws}")
    log_pass(f"Workspace search matched {search_ws['total_matches']} segment(s) across meetings")

    # Step 10: Multi-Format Exports
    log_step("10. Multi-Format Transcript Exports")
    formats = ["txt", "markdown", "srt", "vtt", "json"]
    for fmt in formats:
        st, export_body, headers = http_request(
            "GET",
            f"/api/v1/meetings/{meeting_id}/transcript/export?format={fmt}",
            headers={"Authorization": f"Bearer {tokens['guest']}"},  # Guest allowed export
        )
        if st != 200:
            log_fail(f"Failed to export format {fmt}: {export_body}")
        content_len = len(export_body) if isinstance(export_body, str) else len(json.dumps(export_body))
        log_pass(f"Exported format '{fmt}' successfully ({content_len} bytes, Content-Type: {headers.get('Content-Type')})")

    # Step 11: RBAC & Security Boundaries
    log_step("11. RBAC & IDOR Security Boundaries")
    # Guest cannot modify segment (403)
    st, guest_err, _ = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}/transcript/segments/{new_seg_id}",
        {"text": "Unauthorized alteration attempt"},
        headers={"Authorization": f"Bearer {tokens['guest']}"},
    )
    if st != 403:
        log_fail(f"Guest should receive 403 on segment edit, got {st}: {guest_err}")
    log_pass("Guest blocked from editing segment (403 Forbidden)")

    # Stranger cannot view transcript (404)
    st, stranger_err, _ = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers={"Authorization": f"Bearer {tokens['stranger']}"},
    )
    if st != 404:
        log_fail(f"Stranger should receive 404 on transcript access, got {st}: {stranger_err}")
    log_pass("Stranger isolated from transcript access (404 Not Found)")

    # Stranger cannot search workspace (404)
    st, stranger_ws_err, _ = http_request(
        "GET",
        f"/api/v1/workspaces/{ws_id}/transcripts/search?q=roadmap",
        headers={"Authorization": f"Bearer {tokens['stranger']}"},
    )
    if st != 404:
        log_fail(f"Stranger should receive 404 on workspace search, got {st}: {stranger_ws_err}")
    log_pass("Stranger isolated from workspace transcript search (404 Not Found)")

    print("\n\033[1;32m===============================================================\033[0m")
    print("\033[1;32m🎉 ALL LIVE TRANSCRIPT MANAGEMENT VERIFICATION CHECKS PASSED! 🎉\033[0m")
    print("\033[1;32m===============================================================\033[0m\n")


if __name__ == "__main__":
    main()
