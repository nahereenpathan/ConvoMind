"""Comprehensive E2E Verification Script for ConvoMind Real Recording Pipeline.

Uploads FOUR different real WAV audio files (Alpha, Beta, Gamma, Delta)
and verifies complete isolation across Recording -> Transcription -> AI -> RAG.
"""

import os
import sys
import uuid
import asyncio
import json
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.meeting import Meeting
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript, TranscriptSegment
from app.models.intelligence import MeetingSummary, Decision, ActionItem, MeetingQuestion
from app.models.embedding import TranscriptEmbedding
from app.models.enums import WorkspaceRole, MeetingStatus, RecordingStatus, TranscriptStatus
from app.services.recording_service import RecordingService
from app.workers.tasks.recording_tasks import _async_process_recording
from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
from app.services.rag.rag_service import RAGService
from app.models.chat import ChatConversation

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class DummyUploadFile:
    def __init__(self, filename: str, content_type: str, file_bytes: bytes):
        self.filename = filename
        self.content_type = content_type
        self._bytes = file_bytes
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if size == -1:
            chunk = self._bytes[self._pos:]
            self._pos = len(self._bytes)
            return chunk
        else:
            chunk = self._bytes[self._pos:self._pos + size]
            self._pos += len(self._bytes)
            return chunk

    async def seek(self, pos: int):
        self._pos = pos


async def get_test_user_and_workspace():
    async with AsyncSessionLocal() as db:
        user_res = await db.execute(select(User).where(User.email == "test_real_pipeline@convomind.ai"))
        test_user = user_res.scalar_one_or_none()
        if not test_user:
            test_user = User(
                id=uuid.uuid4(),
                email="test_real_pipeline@convomind.ai",
                full_name="Real Pipeline Tester",
                hashed_password="hashed_pw_test",
                is_active=True,
            )
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)

        ws_res = await db.execute(select(Workspace).where(Workspace.name == "Real Pipeline Workspace"))
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            workspace = Workspace(
                id=uuid.uuid4(),
                name="Real Pipeline Workspace",
                slug=f"real-pipeline-ws-{uuid.uuid4().hex[:6]}",
                created_by_id=test_user.id,
            )
            db.add(workspace)
            await db.commit()
            await db.refresh(workspace)

            wm = WorkspaceMember(
                workspace_id=workspace.id,
                user_id=test_user.id,
                role=WorkspaceRole.OWNER,
            )
            db.add(wm)
            await db.commit()

        return test_user, workspace


async def run_e2e_verification():
    print("=" * 80)
    print("STARTING REAL 4-RECORDING PIPELINE VERIFICATION")
    print("=" * 80)

    audio_files = {
        "A": os.path.join(ROOT_DIR, "recording_a.wav"),
        "B": os.path.join(ROOT_DIR, "recording_b.wav"),
        "C": os.path.join(ROOT_DIR, "recording_c.wav"),
        "D": os.path.join(ROOT_DIR, "recording_d.wav"),
    }

    for key, fpath in audio_files.items():
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Required audio file {fpath} does not exist!")

    test_user, workspace = await get_test_user_and_workspace()
    workspace_id = workspace.id
    user_id = test_user.id

    meeting_ids = {}
    recording_ids = {}

    # 1. Upload & Process all 4 recordings
    for letter in ["A", "B", "C", "D"]:
        print(f"\n--- UPLOADING AND PROCESSING RECORDING {letter} ---")
        async with AsyncSessionLocal() as db:
            m = Meeting(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                creator_id=user_id,
                title=f"Project {letter} Discussion Sync",
                status=MeetingStatus.SCHEDULED,
            )
            db.add(m)
            await db.commit()
            meeting_ids[letter] = m.id

            wav_path = audio_files[letter]
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()

            upload_file = DummyUploadFile(
                filename=f"recording_{letter.lower()}.wav",
                content_type="audio/wav",
                file_bytes=wav_bytes,
            )

            rec = await RecordingService.upload_recording(
                db=db,
                meeting_id=m.id,
                current_user=test_user,
                file=upload_file,
                dispatch_worker=False,
            )
            recording_ids[letter] = rec.id
            rec_id = rec.id
            m_id = m.id

        # Process audio transcription & AI intelligence outside the upload DB session
        print(f"Executing pipeline for Recording {letter} (rec_id: {rec_id}, m_id: {m_id})...")
        await _async_process_recording(str(rec_id), force=True)
        await _async_process_meeting_intelligence(str(m_id))

    # 2. Verification of Results per Meeting
    keywords = {
        "A": ["Alpha"],
        "B": ["Beta"],
        "C": ["Gamma"],
        "D": ["Delta"],
    }

    negative_keywords = {
        "A": ["Beta", "Gamma", "Delta"],
        "B": ["Alpha", "Gamma", "Delta"],
        "C": ["Alpha", "Beta", "Delta"],
        "D": ["Alpha", "Beta", "Gamma"],
    }

    print("\n" + "=" * 80)
    print("VERIFYING TRANSCRIPTS AND INTELLIGENCE ISOLATION")
    print("=" * 80)

    for letter in ["A", "B", "C", "D"]:
        m_id = meeting_ids[letter]
        print(f"\n>>> Checking Meeting {letter} (ID: {m_id})")

        async with AsyncSessionLocal() as db:
            # Check Transcript
            t_res = await db.execute(select(Transcript).where(Transcript.meeting_id == m_id))
            tr = t_res.scalar_one_or_none()
            assert tr is not None, f"Transcript for Meeting {letter} missing!"
            assert tr.status == TranscriptStatus.COMPLETED, f"Transcript for Meeting {letter} status is {tr.status}!"
            print(f"Meeting {letter} Transcript text:\n  '{tr.full_text}'")

            for kw in keywords[letter]:
                assert kw.lower() in tr.full_text.lower(), f"Expected keyword '{kw}' missing from Meeting {letter} transcript!"

            for neg_kw in negative_keywords[letter]:
                assert neg_kw.lower() not in tr.full_text.lower(), f"CONTAMINATION ERROR: Negative keyword '{neg_kw}' found in Meeting {letter} transcript!"

            # Check AI Summary
            s_res = await db.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == m_id))
            summary = s_res.scalar_one_or_none()
            assert summary is not None, f"Meeting {letter} summary missing!"
            print(f"Meeting {letter} Executive Summary:\n  '{summary.overview}'")

            for kw in keywords[letter]:
                assert kw.lower() in summary.overview.lower() or kw.lower() in str(summary.key_points).lower(), f"Keyword '{kw}' missing in Meeting {letter} AI summary!"

            for neg_kw in negative_keywords[letter]:
                assert neg_kw.lower() not in summary.overview.lower(), f"CONTAMINATION ERROR: Negative keyword '{neg_kw}' found in Meeting {letter} AI summary!"

            # Check RAG Isolation
            print(f"Testing RAG Question Answering for Meeting {letter}...")
            chat_conv = ChatConversation(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                meeting_id=m_id,
                user_id=user_id,
                title=f"Chat for Meeting {letter}",
            )
            db.add(chat_conv)
            await db.commit()

            rag_res = await RAGService.answer_question(
                session=db,
                workspace_id=workspace_id,
                user_id=user_id,
                conversation_id=chat_conv.id,
                question_text=f"What is the budget and owner for Project {letter}?",
                meeting_id_filter=m_id,
            )
            print(f"RAG Answer for Meeting {letter}:\n  '{rag_res.answer}'")

            for neg_kw in negative_keywords[letter]:
                assert neg_kw.lower() not in rag_res.answer.lower(), f"CONTAMINATION ERROR: Negative keyword '{neg_kw}' found in Meeting {letter} RAG answer!"

    # 3. Retry Test
    print("\n" + "=" * 80)
    print("VERIFYING RETRY / RE-ANALYSIS ON MEETING A")
    print("=" * 80)

    mA_id = meeting_ids["A"]
    re_intel_res = await _async_process_meeting_intelligence(str(mA_id))
    print(f"Re-analysis result: {re_intel_res}")

    async with AsyncSessionLocal() as db:
        sA_res = await db.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == mA_id))
        summaryA = sA_res.scalar_one_or_none()
        assert summaryA is not None
        assert "Alpha" in summaryA.overview
        assert "Beta" not in summaryA.overview

    # 4. Database Isolation Relationship Audit
    print("\n" + "=" * 80)
    print("DATABASE RELATIONSHIP & ISOLATION AUDIT")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        for letter in ["A", "B", "C", "D"]:
            m_id = meeting_ids[letter]
            t = (await db.execute(select(Transcript).where(Transcript.meeting_id == m_id))).scalar_one()
            s = (await db.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == m_id))).scalar_one()
            emb = (await db.execute(select(TranscriptEmbedding).where(TranscriptEmbedding.meeting_id == m_id))).scalars().all()

            print(f"Meeting {letter}:")
            print(f"  meeting_id    : {m_id}")
            print(f"  workspace_id  : {workspace_id}")
            print(f"  transcript_id : {t.id} (meeting_id match: {t.meeting_id == m_id})")
            print(f"  summary_id    : {s.id} (meeting_id match: {s.meeting_id == m_id})")
            print(f"  embeddings    : {len(emb)} chunks (all match meeting_id: {all(e.meeting_id == m_id for e in emb)})")

            assert t.meeting_id == m_id
            assert s.meeting_id == m_id
            assert all(e.meeting_id == m_id for e in emb)

    print("\n" + "=" * 80)
    print("SUCCESS: ALL FOUR E2E RUNS AND ISOLATION TESTS PASSED CLEANLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
