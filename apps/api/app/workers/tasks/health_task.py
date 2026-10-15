"""Celery health check task."""

from typing import Dict

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.health_task.health_check_task")
def health_check_task() -> Dict[str, str]:
    """Background task to verify Celery worker functionality."""
    return {
        "status": "ok",
        "service": "celery",
    }
