"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "convomind_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.health_task",
        "app.workers.tasks.recording_tasks",
        "app.workers.tasks.intelligence_tasks",
        "app.workers.tasks.embedding_tasks",
        "app.workers.tasks.diarization_tasks",
        "app.workers.tasks.notification_tasks",
        "app.workers.tasks.email_tasks",
    ],
)

import os

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=2,
    beat_schedule={
        "check-meeting-reminders-every-15-min": {
            "task": "app.workers.tasks.email_tasks.check_meeting_reminders",
            "schedule": 900.0,  # every 15 minutes
        },
        "check-action-item-reminders-hourly": {
            "task": "app.workers.tasks.notification_tasks.check_action_item_due_reminders",
            "schedule": 3600.0,  # every hour
        },
    },
)

if os.getenv("TESTING"):
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )

