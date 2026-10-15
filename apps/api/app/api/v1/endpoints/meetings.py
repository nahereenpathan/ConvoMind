"""Meeting management and participant API routes."""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_any_meeting_and_membership,
    get_current_user,
    get_meeting_and_membership,
    get_trashed_meeting_and_membership,
    require_meeting_delete_permission,
    require_meeting_update_permission,
    require_trashed_meeting_permission,
)
from app.core.database import get_db
from app.models.enums import MeetingStatus
from app.models.meeting import Meeting
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.auth import MessageResponse
from app.schemas.meeting import (
    JoinRoomResponse,
    MeetingCreate,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdate,
    NativeRoomInitResponse,
    ParticipantCreate,
    ParticipantResponse,
    RoomStatusResponse,
    MeetingMessageCreate,
    MeetingMessageResponse,
    NativeRecordingStartResponse,
    NativeRecordingStopResponse,
    ParticipantModerationResponse,
)
from app.services.meeting_service import meeting_service

router = APIRouter()


@router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new meeting",
    description="Create a meeting within an authorized workspace. The creator is recorded as the meeting owner.",
)
async def create_meeting(
    data: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """Create a new meeting."""
    meeting = await meeting_service.create_meeting(
        db=db,
        current_user=current_user,
        data=data,
    )
    return MeetingResponse.model_validate(meeting)


@router.get(
    "",
    response_model=MeetingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List meetings with pagination and filtering",
    description="Retrieve paginated meetings across all user's authorized workspaces, with support for status, type, creator, date, and search filters.",
)
async def list_meetings(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    workspace_id: Optional[uuid.UUID] = Query(default=None, description="Filter by workspace UUID"),
    status: Optional[MeetingStatus] = Query(default=None, description="Filter by meeting lifecycle status"),
    meeting_type: Optional[str] = Query(default=None, description="Filter by meeting type"),
    created_by: Optional[uuid.UUID] = Query(default=None, description="Filter by meeting creator UUID"),
    search: Optional[str] = Query(default=None, max_length=100, description="Search meetings by title substring"),
    date_from: Optional[datetime] = Query(default=None, description="Filter meetings scheduled/created after timestamp"),
    date_to: Optional[datetime] = Query(default=None, description="Filter meetings scheduled/created before timestamp"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingListResponse:
    """List meetings with pagination and rich filters."""
    items, total, total_pages = await meeting_service.list_meetings(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        meeting_status=status,
        meeting_type=meeting_type,
        created_by=created_by,
        search=search,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return MeetingListResponse(
        items=[MeetingResponse.model_validate(m) for m in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get(
    "/trash",
    response_model=MeetingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List trashed meetings",
    description="Retrieve paginated list of soft-deleted meetings in Trash for user's authorized workspaces.",
)
async def list_trashed_meetings(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    workspace_id: Optional[uuid.UUID] = Query(default=None, description="Filter by workspace UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingListResponse:
    """List trashed meetings."""
    items, total, total_pages = await meeting_service.list_trashed_meetings(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
    )
    return MeetingListResponse(
        items=[MeetingResponse.model_validate(m) for m in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meeting details",
    description="Retrieve meeting details. Accessible by any member of the meeting's workspace; returns 404 for non-members.",
)
async def get_meeting_details(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
) -> MeetingResponse:
    """Get meeting by ID."""
    meeting, _ = context
    return MeetingResponse.model_validate(meeting)


@router.patch(
    "/{meeting_id}",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK,
    summary="Update meeting",
    description="Update meeting attributes, timestamps, and lifecycle status. Restricted to meeting creator and workspace OWNER/ADMIN.",
)
async def update_meeting(
    data: MeetingUpdate,
    context: Tuple[Meeting, WorkspaceMember] = Depends(
        require_meeting_update_permission
    ),
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """Update meeting details."""
    meeting, _ = context
    updated = await meeting_service.update_meeting(
        db=db,
        meeting=meeting,
        data=data,
    )
    return MeetingResponse.model_validate(updated)


@router.delete(
    "/{meeting_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Move meeting to Trash",
    description="Soft delete a meeting by moving it to Trash. Restricted to meeting creator and workspace OWNER/ADMIN.",
)
async def delete_meeting(
    context: Tuple[Meeting, WorkspaceMember] = Depends(
        require_meeting_delete_permission
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Move meeting to Trash."""
    meeting, _ = context
    await meeting_service.soft_delete_meeting(
        db=db,
        meeting=meeting,
        current_user=current_user,
    )
    return MessageResponse(message="Meeting moved to Trash successfully.")


@router.post(
    "/{meeting_id}/restore",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore meeting from Trash",
    description="Restore a soft-deleted meeting from Trash back to active status.",
)
async def restore_meeting(
    context: Tuple[Meeting, WorkspaceMember] = Depends(
        require_trashed_meeting_permission
    ),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Restore meeting from Trash."""
    meeting, _ = context
    await meeting_service.restore_meeting(db=db, meeting=meeting)
    return MessageResponse(message="Meeting restored successfully.")


@router.delete(
    "/{meeting_id}/permanent",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Permanently delete meeting",
    description="Permanently delete a meeting from database and clean up associated recording files from storage.",
)
async def permanent_delete_meeting(
    context: Tuple[Meeting, WorkspaceMember] = Depends(
        require_trashed_meeting_permission
    ),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Permanently delete a meeting."""
    meeting, _ = context
    await meeting_service.permanent_delete_meeting(db=db, meeting=meeting)
    return MessageResponse(message="Meeting permanently deleted.")


@router.post(
    "/{meeting_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add participant to meeting",
    description="Add an attendee or participant to the meeting. Prevents duplicate attendees.",
)
async def add_participant(
    data: ParticipantCreate,
    context: Tuple[Meeting, WorkspaceMember] = Depends(
        require_meeting_update_permission
    ),
    db: AsyncSession = Depends(get_db),
) -> ParticipantResponse:
    """Add a participant to the meeting."""
    meeting, _ = context
    participant = await meeting_service.add_participant(
        db=db,
        meeting=meeting,
        data=data,
    )
    return ParticipantResponse.model_validate(participant)


@router.get(
    "/{meeting_id}/participants",
    response_model=List[ParticipantResponse],
    status_code=status.HTTP_200_OK,
    summary="List meeting participants",
    description="Return all participants attending the specified meeting.",
)
async def list_participants(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    db: AsyncSession = Depends(get_db),
) -> List[ParticipantResponse]:
    """List participants attending the meeting."""
    meeting, _ = context
    participants = await meeting_service.list_participants(
        db=db,
        meeting_id=meeting.id,
    )
    return [ParticipantResponse.model_validate(p) for p in participants]


@router.delete(
    "/{meeting_id}/participants/{participant_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove participant from meeting",
    description="Remove a participant from the meeting. Permitted for meeting creator, workspace OWNER/ADMIN, or the participant themselves.",
)
async def remove_participant(
    participant_id: uuid.UUID,
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove a participant from the meeting."""
    meeting, member = context
    await meeting_service.remove_participant(
        db=db,
        meeting=meeting,
        participant_id=participant_id,
        current_user=current_user,
        member=member,
    )
    return MessageResponse(message="Participant removed successfully.")


@router.post(
    "/{meeting_id}/native-room",
    response_model=NativeRoomInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize native meeting room",
    description="Initialize or retrieve a secure native room for the meeting. Restricted to meeting creator or workspace OWNER/ADMIN.",
)
async def initialize_native_room(
    context: Tuple[Meeting, WorkspaceMember] = Depends(
        require_meeting_update_permission
    ),
    db: AsyncSession = Depends(get_db),
) -> NativeRoomInitResponse:
    """Initialize a native meeting room."""
    meeting, _ = context
    updated = await meeting_service.initialize_native_room(db=db, meeting=meeting)
    return NativeRoomInitResponse(
        meeting_id=updated.id,
        room_id=updated.room_id or "",
        room_provider=updated.room_provider or "livekit",
        room_status=updated.room_status or "IDLE",
        is_native=updated.is_native,
    )


@router.post(
    "/{meeting_id}/join",
    response_model=JoinRoomResponse,
    status_code=status.HTTP_200_OK,
    summary="Join native meeting room",
    description="Join native meeting room, record presence, and receive a short-lived media access token. Accessible by authorized workspace members.",
)
async def join_native_room(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JoinRoomResponse:
    """Join native meeting room and obtain access token."""
    meeting, _ = context
    result = await meeting_service.join_native_room(
        db=db,
        meeting=meeting,
        current_user=current_user,
    )
    return JoinRoomResponse(**result)


@router.post(
    "/{meeting_id}/leave",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Leave native meeting room",
    description="Record participant exit from the native room.",
)
async def leave_native_room(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Leave native meeting room."""
    meeting, _ = context
    await meeting_service.leave_native_room(
        db=db,
        meeting=meeting,
        current_user=current_user,
    )
    return MessageResponse(message="Successfully left native meeting room.")


@router.post(
    "/{meeting_id}/end",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK,
    summary="End native meeting room for all",
    description="End native meeting room for all participants and terminate media session. Restricted to meeting creator or workspace OWNER/ADMIN.",
)
async def end_native_room(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """End native meeting room."""
    meeting, member = context
    ended_meeting = await meeting_service.end_native_room(
        db=db,
        meeting=meeting,
        current_user=current_user,
        member=member,
    )
    return MeetingResponse.model_validate(ended_meeting)


@router.get(
    "/{meeting_id}/room",
    response_model=RoomStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get native room status & presence",
    description="Fetch live room status and active participant presence for a native meeting.",
)
async def get_native_room_status(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    db: AsyncSession = Depends(get_db),
) -> RoomStatusResponse:
    """Get native room status."""
    meeting, _ = context
    status_data = await meeting_service.get_native_room_status(
        db=db,
        meeting=meeting,
    )
    return RoomStatusResponse(**status_data)


@router.post(
    "/{meeting_id}/messages",
    response_model=MeetingMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send in-meeting chat message",
    description="Send and persist a chat message for an active native meeting. Restricted to workspace members.",
)
async def send_meeting_message(
    payload: MeetingMessageCreate,
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingMessageResponse:
    """Send in-meeting chat message."""
    meeting, _ = context
    msg = await meeting_service.send_meeting_message(
        db=db,
        meeting=meeting,
        current_user=current_user,
        message_text=payload.message,
    )
    return MeetingMessageResponse.model_validate(msg)


@router.get(
    "/{meeting_id}/messages",
    response_model=List[MeetingMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="List in-meeting chat messages",
    description="Fetch persistent chat history for a meeting ordered by timestamp. Restricted to workspace members.",
)
async def list_meeting_messages(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    db: AsyncSession = Depends(get_db),
) -> List[MeetingMessageResponse]:
    """List in-meeting chat messages."""
    meeting, _ = context
    messages = await meeting_service.list_meeting_messages(
        db=db,
        meeting=meeting,
    )
    return [MeetingMessageResponse.model_validate(m) for m in messages]


@router.post(
    "/{meeting_id}/recording/start",
    response_model=NativeRecordingStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start native meeting recording",
    description="Initiate native WebRTC room recording and broadcast REC consent to participants. Restricted to meeting host or workspace OWNER/ADMIN.",
)
async def start_native_recording(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NativeRecordingStartResponse:
    """Start native meeting recording."""
    meeting, member = context
    res = await meeting_service.start_native_recording(
        db=db,
        meeting=meeting,
        current_user=current_user,
        member=member,
    )
    return NativeRecordingStartResponse(**res)


@router.post(
    "/{meeting_id}/recording/stop",
    response_model=NativeRecordingStopResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop native meeting recording",
    description="Finalize native meeting recording artifact and enqueue Celery task for Whisper transcription & AI intelligence. Restricted to host/ADMIN.",
)
async def stop_native_recording(
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NativeRecordingStopResponse:
    """Stop native meeting recording."""
    meeting, member = context
    res = await meeting_service.stop_native_recording(
        db=db,
        meeting=meeting,
        current_user=current_user,
        member=member,
    )
    return NativeRecordingStopResponse(**res)


@router.post(
    "/{meeting_id}/participants/{participant_id}/mute",
    response_model=ParticipantModerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mute participant audio",
    description="Mute a participant's microphone. Restricted to meeting host or workspace ADMIN/OWNER.",
)
async def mute_participant(
    participant_id: uuid.UUID,
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParticipantModerationResponse:
    """Mute a participant in the meeting room."""
    meeting, member = context
    res = await meeting_service.mute_participant(
        db=db,
        meeting=meeting,
        participant_id=participant_id,
        current_user=current_user,
        member=member,
    )
    return ParticipantModerationResponse(**res)


@router.post(
    "/{meeting_id}/participants/{participant_id}/kick",
    response_model=ParticipantModerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Kick participant from meeting",
    description="Remove/kick a participant from an active room. Restricted to meeting host or workspace ADMIN/OWNER.",
)
async def kick_participant(
    participant_id: uuid.UUID,
    context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParticipantModerationResponse:
    """Kick a participant from the meeting room."""
    meeting, member = context
    res = await meeting_service.kick_participant(
        db=db,
        meeting=meeting,
        participant_id=participant_id,
        current_user=current_user,
        member=member,
    )
    return ParticipantModerationResponse(**res)



