"""Services package."""

from app.services.auth_service import AuthService, auth_service
from app.services.ffmpeg_service import FFmpegService, get_ffmpeg_service
from app.services.meeting_service import MeetingService, meeting_service
from app.services.recording_service import RecordingService
from app.services.storage_service import LocalStorageBackend, StorageBackend, get_storage_service
from app.services.workspace_service import WorkspaceService, workspace_service

__all__ = [
    "AuthService",
    "auth_service",
    "WorkspaceService",
    "workspace_service",
    "MeetingService",
    "meeting_service",
    "RecordingService",
    "StorageBackend",
    "LocalStorageBackend",
    "get_storage_service",
    "FFmpegService",
    "get_ffmpeg_service",
]



