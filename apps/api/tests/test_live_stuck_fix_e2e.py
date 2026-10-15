"""E2E test verifying AI intelligence processing and RAG isolation for ConvoMind Real Test Meeting."""

import asyncio
import os
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.meeting import Meeting, Speaker, MeetingParticipant
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript, TranscriptSegment
from app.models.enums import WorkspaceRole, MeetingStatus, RecordingStatus, TranscriptStatus, IntelligenceStatus
from app.models.intelligence import MeetingIntelligenceJob
from app.services.intelligence_service import IntelligenceService
from app.services.rag.rag_service import RAGService
from app.core.security import create_access_token, hash_password


@pytest.mark.asyncio
async def test_live_stuck_fix_and_rag_grounding():
    async with AsyncSessionLocal() as db:
        # Create test user
        uid = uuid.uuid4()
        user = User(
            id=uid,
            email=f"e2e_user_{uid.hex[:6]}@example.com",
            full_name="Rahul Sharma",
            hashed_password=hash_password("TestPassword123!"),
            is_active=True,
        )
        db.add(user)

        # Create workspace
        ws_id = uuid.uuid4()
        workspace = Workspace(
            id=ws_id,
            name="ConvoMind Production Workspace",
            slug=f"convomind-ws-{ws_id.hex[:6]}",
            created_by_id=uid,
        )
        db.add(workspace)

        member = WorkspaceMember(
            workspace_id=ws_id,
            user_id=uid,
            role=WorkspaceRole.OWNER,
        )
        db.add(member)

        # Create ConvoMind Real Test Meeting
        meeting_id = uuid.uuid4()
        meeting = Meeting(
            id=meeting_id,
            workspace_id=ws_id,
            creator_id=uid,
            title="ConvoMind Real Test Meeting",
            description="Discussion regarding billing integration, Razorpay testing, frontend verification, and security.",
            status=MeetingStatus.COMPLETED,
            platform="UPLOAD",
            is_native=False,
        )
        db.add(meeting)

        # Create Recording
        rec_id = uuid.uuid4()
        recording = MeetingRecording(
            id=rec_id,
            meeting_id=meeting_id,
            workspace_id=ws_id,
            uploaded_by_id=uid,
            original_filename="real_test_meeting.mp4",
            storage_key=f"recordings/{ws_id}/{meeting_id}/real_test.mp4",
            file_size=1024,
            mime_type="video/mp4",
            status=RecordingStatus.COMPLETED,
        )
        db.add(recording)

        # Create Speaker
        spk_id = uuid.uuid4()
        speaker = Speaker(
            id=spk_id,
            meeting_id=meeting_id,
            user_id=uid,
            label="SPEAKER_00",
            name="Rahul Sharma",
        )
        db.add(speaker)

        # Create Participant
        participant = MeetingParticipant(
            meeting_id=meeting_id,
            user_id=uid,
            name="Rahul Sharma",
            email=user.email,
            role="OWNER",
        )
        db.add(participant)

        # 11 Grounded Transcript Segments
        seg_texts = [
            "Welcome everyone to the ConvoMind Real Test Meeting.",
            "Our primary focus today is completing the billing integration by Friday.",
            "Rahul will be testing the Razorpay payment flow thoroughly in staging.",
            "The frontend team needs to verify the dashboard and action items interface.",
            "We have finalized the first release requirements for production readiness.",
            "Workspace security rules must be strictly enforced across all database queries.",
            "Can someone clarify the question regarding email notification settings?",
            "Yes, email notifications will be sent automatically when action items are assigned.",
            "We decided to enable email notifications for all workspace members.",
            "We will review the final deployment progress tomorrow morning at 10 AM.",
            "Thank you everyone for attending this planning session.",
        ]

        full_transcript = " ".join(seg_texts)

        transcript_id = uuid.uuid4()
        transcript = Transcript(
            id=transcript_id,
            meeting_id=meeting_id,
            recording_id=rec_id,
            workspace_id=ws_id,
            language="en",
            status=TranscriptStatus.COMPLETED,
            full_text=full_transcript,
            word_count=len(full_transcript.split()),
        )
        db.add(transcript)

        for i, txt in enumerate(seg_texts):
            seg = TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript_id,
                speaker_id=spk_id,
                sequence_order=i,
                start_time=float(i * 10),
                end_time=float(i * 10 + 9),
                text=txt,
                confidence=0.98,
            )
            db.add(seg)

        await db.commit()

        # Trigger AI Intelligence Processing
        job = await IntelligenceService.trigger_intelligence_processing(
            db=db,
            meeting_id=meeting_id,
            current_user=user,
        )

        assert job is not None

        # Execute async worker directly for test verification
        from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
        await _async_process_meeting_intelligence(str(meeting_id), str(job.id))

        db.expunge_all()

        status_job = await IntelligenceService.get_intelligence_job_status(
            db=db,
            meeting_id=meeting_id,
            current_user=user,
            job_id=job.id,
        )

        assert status_job.status == IntelligenceStatus.COMPLETED

        # Fetch consolidated meeting intelligence
        intel_resp = await IntelligenceService.get_meeting_intelligence(
            db=db,
            meeting_id=meeting_id,
            current_user=user,
        )

        assert intel_resp.meeting_id == meeting_id
        assert intel_resp.workspace_id == ws_id
        assert intel_resp.summary is not None
        assert len(intel_resp.summary.overview) > 0

        # Process embeddings for vector RAG search
        from app.workers.tasks.embedding_tasks import _async_process_transcript_embeddings
        await _async_process_transcript_embeddings(str(transcript_id))

        # Create ChatConversation for meeting-scoped RAG
        from app.models.chat import ChatConversation
        conv_id = uuid.uuid4()
        conversation = ChatConversation(
            id=conv_id,
            workspace_id=ws_id,
            user_id=uid,
            meeting_id=meeting_id,
            title="Meeting Q&A Chat",
        )
        db.add(conversation)
        await db.commit()

        # Test RAG chat answering against this exact meeting
        ans_friday = await RAGService.answer_question(
            session=db,
            workspace_id=ws_id,
            user_id=uid,
            conversation_id=conv_id,
            question_text="What needs to be completed by Friday?",
            meeting_id_filter=meeting_id,
        )
        assert "billing" in ans_friday.answer.lower() or "friday" in ans_friday.answer.lower()

        ans_rahul = await RAGService.answer_question(
            session=db,
            workspace_id=ws_id,
            user_id=uid,
            conversation_id=conv_id,
            question_text="Who will test the Razorpay payment flow?",
            meeting_id_filter=meeting_id,
        )
        assert "rahul" in ans_rahul.answer.lower()
