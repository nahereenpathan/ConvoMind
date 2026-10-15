"""V1 API Endpoints package."""

from app.api.v1.endpoints import (
    auth,
    chat,
    embeddings,
    follow_ups,
    intelligence,
    meetings,
    notifications,
    recordings,
    speakers,
    transcripts,
    workspaces,
)

__all__ = [
    "auth",
    "chat",
    "embeddings",
    "follow_ups",
    "intelligence",
    "meetings",
    "notifications",
    "recordings",
    "speakers",
    "transcripts",
    "workspaces",
]
