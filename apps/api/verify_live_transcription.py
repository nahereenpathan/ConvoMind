"""Live HTTP & Asynchronous Celery Verification Script for ConvoMind Transcription Pipeline.

Executes real HTTP requests against the running FastAPI application and validates
end-to-end processing by the live Celery worker container.
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
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


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


def create_user_and_token(name: str):
    email = f"live_trans_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "StrongPassword123!"
    status, body = http_request(
        "POST",
        "/api/v1/auth/register",
        {"name": name, "email": email, "password": password},
    )
    if status != 201:
        raise RuntimeError(f"Failed to register {email}: {body}")

    status, body = http_request(
        "POST",
        "/api/v1/auth/login",
        {"email": email, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"Failed to login {email}: {body}")

    return body["access_token"], email


def main():
    print("================================================================")
    print("  ConvoMind Live Transcription & Audio Processing Verification  ")
    print("================================================================")

    # 1. Health check
    print("\n[1] Checking service health...")
    status, body = http_request("GET", "/health")
    assert status == 200, f"Service unhealthy: {body}"
    print(f"    -> API Service Healthy: {body}")

    # 2. User & Workspace Setup
    print("\n[2] Setting up authenticated workspace & meeting...")
    token, email = create_user_and_token("Lead Architect")
    auth = {"Authorization": f"Bearer {token}"}

    status, ws = http_request(
        "POST",
        "/api/v1/workspaces",
        {"name": f"Live Transcribe WS {uuid.uuid4().hex[:6]}"},
        headers=auth,
    )
    assert status == 201, f"Failed workspace creation: {ws}"
    ws_id = ws["id"]
    print(f"    -> Workspace created: {ws_id}")

    status, meeting = http_request(
        "POST",
        "/api/v1/meetings",
        {"workspace_id": ws_id, "title": "Live Audio Transcription Sync"},
        headers=auth,
    )
    assert status == 201, f"Failed meeting creation: {meeting}"
    meeting_id = meeting["id"]
    print(f"    -> Meeting created: {meeting_id}")

    # 3. Upload Audio Recording
    print("\n[3] Uploading audio recording (WAV format)...")
    wav_bytes = make_valid_pcm_wav(duration_s=3.0)
    status, recording = upload_multipart_file(
        f"/api/v1/meetings/{meeting_id}/recordings",
        field_name="file",
        filename="live_session.wav",
        file_bytes=wav_bytes,
        mime_type="audio/wav",
        headers=auth,
    )
    assert status == 201, f"Failed audio upload: {recording}"
    recording_id = recording["id"]
    print(f"    -> Recording uploaded: id={recording_id}, status={recording['status']}")

    # 4. Wait for Celery Worker to Process
    print("\n[4] Polling recording status until Celery worker completes processing...")
    max_wait = 30
    start = time.time()
    final_rec = None

    while time.time() - start < max_wait:
        status, poll = http_request(
            "GET",
            f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
            headers=auth,
        )
        if status == 200 and poll.get("status") == "COMPLETED":
            final_rec = poll
            break
        elif poll.get("status") == "FAILED":
            raise RuntimeError(f"Processing failed unexpectedly: {poll.get('error_message')}")
        time.sleep(1)

    assert final_rec is not None, f"Celery worker timed out after {max_wait}s"
    print(f"    -> Recording completed: status={final_rec['status']}, duration={final_rec.get('duration_seconds')}s")

    # 5. Verify Meeting Transcript
    print("\n[5] Fetching meeting transcript...")
    status, transcript = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers=auth,
    )
    assert status == 200, f"Failed fetching transcript: {transcript}"
    print(f"    -> Transcript ID: {transcript['id']}")
    print(f"    -> Status: {transcript['status']}")
    print(f"    -> Provider: {transcript['provider']}")
    print(f"    -> Word Count: {transcript['word_count']}")
    print(f"    -> Segments Count: {len(transcript['segments'])}")
    print(f"    -> Full Text: {transcript['full_text'][:120]}...")

    # 6. Verify Segment Pagination
    print("\n[6] Verifying transcript segment pagination...")
    status, paginated = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript?page=1&page_size=2",
        headers=auth,
    )
    assert status == 200, f"Failed segment pagination: {paginated}"
    assert len(paginated["segments"]) <= 2
    print(f"    -> Page 1 segment count: {len(paginated['segments'])} (total: {paginated['total_segments']})")

    # 7. Verify Transcript Status Endpoint
    print("\n[7] Verifying transcript status polling endpoint...")
    status, t_status = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript/status",
        headers=auth,
    )
    assert status == 200, f"Failed status check: {t_status}"
    assert t_status["status"] == "COMPLETED"
    print(f"    -> Status Endpoint: {t_status}")

    # 8. Verify Recording-specific Transcription Endpoint
    print("\n[8] Verifying recording-specific transcription endpoint...")
    status, rec_trans = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcription",
        headers=auth,
    )
    assert status == 200, f"Failed recording transcription: {rec_trans}"
    assert rec_trans["recording_id"] == recording_id
    print(f"    -> Recording Transcription matches recording ID: {rec_trans['recording_id']}")

    # 9. Verify Trigger Transcription Endpoint
    print("\n[9] Triggering transcription explicitly via API...")
    status, job = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcribe",
        headers=auth,
    )
    assert status == 202, f"Failed triggering transcription: {job}"
    print(f"    -> Transcription job queued: {job}")

    # 10. Verify Workspace Isolation (IDOR Protection)
    print("\n[10] Verifying workspace isolation and IDOR protection...")
    stranger_token, _ = create_user_and_token("Stranger")
    stranger_auth = {"Authorization": f"Bearer {stranger_token}"}

    status, _ = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers=stranger_auth,
    )
    assert status == 404, f"Stranger was able to view transcript! Expected 404, got {status}"

    status, _ = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcribe",
        headers=stranger_auth,
    )
    assert status == 404, f"Stranger was able to trigger transcription! Expected 404, got {status}"
    print("    -> Workspace isolation verified: Stranger correctly denied access with 404.")

    print("\n================================================================")
    print("  ALL LIVE TRANSCRIPTION & CELERY VERIFICATIONS PASSED!         ")
    print("================================================================\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[FATAL ERROR] Verification failed: {exc}", file=sys.stderr)
        sys.exit(1)
