"""API v1 router configuration."""

from typing import Dict
from fastapi import APIRouter

from app.api.v1.endpoints import (
    action_items,
    auth,
    chat,
    embeddings,
    follow_ups,
    intelligence,
    meetings,
    notifications,
    recordings,
    speakers,
    system,
    transcripts,
    workspaces,
    billing,
)

api_v1_router = APIRouter(prefix="/api/v1", tags=["v1"])


@api_v1_router.get("/health", summary="V1 Service Health Check")
async def v1_health_check() -> Dict[str, str]:
    """Health check endpoint for API v1."""
    return {
        "status": "ok",
        "service": "convomind-api",
    }


# Register authentication routes
api_v1_router.include_router(auth.router, prefix="/auth")

# Register workspace routes
api_v1_router.include_router(
    workspaces.router, prefix="/workspaces", tags=["Workspaces"]
)

# Register meeting routes
api_v1_router.include_router(
    meetings.router, prefix="/meetings", tags=["Meetings"]
)

# Alias for top-level trash endpoint
api_v1_router.add_api_route(
    "/trash",
    meetings.list_trashed_meetings,
    methods=["GET"],
    response_model=meetings.MeetingListResponse,
    summary="List trashed meetings (Top-level alias)",
    tags=["Meetings"],
)


# Register meeting recordings routes
api_v1_router.include_router(
    recordings.router,
    prefix="/meetings/{meeting_id}/recordings",
    tags=["Meeting Recordings"],
)

# Register meeting transcripts routes
api_v1_router.include_router(
    transcripts.router,
    prefix="/meetings/{meeting_id}/transcript",
    tags=["Meeting Transcripts"],
)

# Register meeting speakers routes
api_v1_router.include_router(
    speakers.router,
    prefix="/meetings/{meeting_id}/speakers",
    tags=["Meeting Speakers"],
)

# Register meeting intelligence routes
api_v1_router.include_router(
    intelligence.router,
    prefix="/meetings/{meeting_id}",
    tags=["Meeting Intelligence"],
)

# Register embedding and vector search routes
api_v1_router.include_router(
    embeddings.router,
    prefix="",
    tags=["Embeddings & Vector Search"],
)

# Register RAG & AI Chat routes
api_v1_router.include_router(
    chat.router,
    prefix="",
    tags=["RAG & AI Chat"],
)

# Register notifications routes
api_v1_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)

# Register AI follow-up routes
api_v1_router.include_router(
    follow_ups.router,
    prefix="",
    tags=["AI Follow-Ups"],
)

# Register standalone workspace action item routes
api_v1_router.include_router(
    action_items.router,
    prefix="/action-items",
    tags=["Action Items"],
)

# Register AI Engine telemetry and system health routes
api_v1_router.include_router(
    system.router,
    prefix="/system",
    tags=["System Telemetry"],
)

# Register SaaS Billing & Razorpay routes
api_v1_router.include_router(
    billing.router,
    prefix="/billing",
    tags=["SaaS Billing"],
)




