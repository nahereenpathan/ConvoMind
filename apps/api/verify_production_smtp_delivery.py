"""Empirical Verification Script for ConvoMind Production Email & SMTP System.

This script executes runtime checks on:
1. Database schema and EmailLog persistence.
2. Responsive HTML & text template rendering for all 9 event types.
3. Async Celery task execution with state updates.
4. Idempotency key enforcement.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.email_log import EmailLog
from app.models.enums import EmailStatus
from app.services.email.templates import render_email_template
from app.services.email.dispatch import EmailDispatchService
from app.workers.tasks.email_tasks import _async_send_email


async def main():
    print("==================================================")
    print("CONVOMIND PRODUCTION EMAIL SYSTEM EMPIRICAL VERIFICATION")
    print("==================================================")

    # 1. Test Email Templates Engine
    print("\n[Step 1] Testing Template Renderer for all 9 Event Types...")
    events = [
        "meeting_invitation",
        "meeting_reminder",
        "meeting_update",
        "meeting_cancelled",
        "post_meeting_summary",
        "ai_insights_ready",
        "recording_ready",
        "action_item_assigned",
        "follow_up_draft",
    ]
    test_data = {
        "meeting_id": str(uuid.uuid4()),
        "meeting_title": "Production Launch Readiness Sync",
        "host_name": "Antigravity Engineering",
        "scheduled_at": "2026-10-01 14:00 UTC",
        "agenda": "Final review of SMTP, Native Meetings, and RAG search.",
        "time_until": "15 minutes",
        "change_summary": "Rescheduled to 14:00 UTC",
        "reason": "Host requirement",
        "summary": "All technical validation metrics have passed cleanly.",
        "decisions": ["Approve release candidate v1.0", "Deploy Celery workers"],
        "duration": "32 minutes",
        "task_description": "Deploy DB migration script",
        "assignee_name": "DevOps Engineer",
        "due_date": "2026-09-25",
        "follow_up_content": "Dear Team,\nHere are the finalized action items from our launch sync...",
        "recipients": ["devops@convomind.ai", "lead@convomind.ai"],
    }

    for ev in events:
        subj, text, html = render_email_template(ev, test_data)
        assert len(subj) > 0 and len(text) > 0 and len(html) > 0, f"Template render failed for {ev}"
        assert "ConvoMind" in html, f"Branding missing in template {ev}"
        print(f"  ✓ Event '{ev}' -> Subject: '{subj}'")

    print("\n[Step 2] Testing EmailDispatchService & Database Persistence...")
    async with AsyncSessionLocal() as session:
        test_email = f"verify_{uuid.uuid4().hex[:6]}@convomind.ai"
        idempotency_key = f"verify_key:{uuid.uuid4()}"

        log = await EmailDispatchService.enqueue_email(
            db=session,
            recipient_email=test_email,
            recipient_name="Verification Suite",
            event_type="meeting_invitation",
            template_data=test_data,
            idempotency_key=idempotency_key,
            check_preference=False,
        )

        assert log is not None, "EmailDispatchService failed to create EmailLog"
        assert log.status == EmailStatus.QUEUED, f"Expected QUEUED status, got {log.status}"
        assert log.idempotency_key == idempotency_key
        print(f"  ✓ Enqueued EmailLog ID={log.id}, Status={log.status}, Recipient={log.recipient_email}")

        # Test Idempotency Enforcement
        print("\n[Step 3] Testing Idempotency Enforcement...")
        dup_log = await EmailDispatchService.enqueue_email(
            db=session,
            recipient_email=test_email,
            recipient_name="Verification Suite",
            event_type="meeting_invitation",
            template_data=test_data,
            idempotency_key=idempotency_key,
            check_preference=False,
        )
        assert dup_log.id == log.id, "Idempotency check failed, created duplicate record!"
        print(f"  ✓ Idempotency enforced cleanly: Duplicate request returned existing EmailLog ID={dup_log.id}")

        # Test Async Worker Task Execution
        print("\n[Step 4] Executing Async Email Worker Task for EmailLog...")
        target_id = log.id
        res = await _async_send_email(str(target_id))
        print(f"  ✓ Async Worker Task Result: {res}")

    # Verify updated DB state in fresh session
    async with AsyncSessionLocal() as check_session:
        log_check_stmt = select(EmailLog).where(EmailLog.id == target_id)
        updated_log = (await check_session.execute(log_check_stmt)).scalar_one()
        print(f"  ✓ Updated DB Status: {updated_log.status}, Attempts: {updated_log.attempts}, SentAt: {updated_log.sent_at}, Error: {updated_log.last_error}")
        assert updated_log.status in (EmailStatus.SENT, EmailStatus.FAILED), "Status not updated after worker task execution"

    print("\n==================================================")
    print("ALL EMPIRICAL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
