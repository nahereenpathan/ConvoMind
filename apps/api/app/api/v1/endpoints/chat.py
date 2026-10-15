"""API endpoints for Chat Conversations, Message History, and RAG Grounded Question Answering."""

import uuid
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.meeting import get_meeting_and_membership
from app.api.dependencies.workspace import get_workspace_and_membership
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.chat import ChatConversation, ChatMessage
from app.models.meeting import Meeting
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.chat import (
    ChatConversationCreate,
    ChatConversationResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    RAGQuestionResponse,
)
from app.services.rag.rag_service import RAGService

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/chat/conversations",
    response_model=ChatConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new AI chat conversation in a workspace",
)
async def create_chat_conversation(
    payload: ChatConversationCreate,
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationResponse:
    """Create a new chat conversation for the authenticated user within a workspace."""
    workspace, member = workspace_context

    # Validate optional meeting if specified
    if payload.meeting_id is not None:
        m_stmt = select(Meeting).where(
            Meeting.id == payload.meeting_id,
            Meeting.workspace_id == workspace.id,
        )
        meeting = (await db.execute(m_stmt)).scalar_one_or_none()
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified meeting not found in this workspace.",
            )

    title = payload.title or ("Meeting Discussion" if payload.meeting_id else "Workspace Knowledge Chat")

    conversation = ChatConversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=current_user.id,
        meeting_id=payload.meeting_id,
        title=title,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ChatConversationResponse.model_validate(conversation)


@router.get(
    "/workspaces/{workspace_id}/chat/conversations",
    response_model=List[ChatConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List chat conversations in a workspace for the authenticated user",
)
async def list_chat_conversations(
    meeting_id: Optional[uuid.UUID] = Query(None, description="Optional meeting filter"),
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ChatConversationResponse]:
    """Retrieve chat conversations belonging to the authenticated user in this workspace."""
    workspace, member = workspace_context

    stmt = select(ChatConversation).where(
        ChatConversation.workspace_id == workspace.id,
        ChatConversation.user_id == current_user.id,
    )

    if meeting_id is not None:
        stmt = stmt.where(ChatConversation.meeting_id == meeting_id)

    stmt = stmt.order_by(ChatConversation.updated_at.desc())

    conversations = list((await db.execute(stmt)).scalars().all())
    return [ChatConversationResponse.model_validate(c) for c in conversations]


@router.get(
    "/workspaces/{workspace_id}/chat/conversations/{conversation_id}",
    response_model=ChatConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chat conversation details",
)
async def get_chat_conversation(
    conversation_id: uuid.UUID,
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationResponse:
    """Retrieve details for a specific chat conversation."""
    workspace, member = workspace_context

    stmt = select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.workspace_id == workspace.id,
        ChatConversation.user_id == current_user.id,
    )
    conversation = (await db.execute(stmt)).scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat conversation not found.",
        )

    return ChatConversationResponse.model_validate(conversation)


@router.delete(
    "/workspaces/{workspace_id}/chat/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat conversation",
)
async def delete_chat_conversation(
    conversation_id: uuid.UUID,
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a chat conversation and all associated messages."""
    workspace, member = workspace_context

    stmt = select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.workspace_id == workspace.id,
        ChatConversation.user_id == current_user.id,
    )
    conversation = (await db.execute(stmt)).scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat conversation not found.",
        )

    await db.delete(conversation)
    await db.commit()


@router.post(
    "/workspaces/{workspace_id}/chat/conversations/{conversation_id}/messages",
    response_model=RAGQuestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Post a question and receive grounded RAG answer with source citations",
)
async def send_chat_message(
    conversation_id: uuid.UUID,
    payload: ChatMessageCreate,
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGQuestionResponse:
    """Submit a question to a chat conversation and execute RAG retrieval and answer generation."""
    workspace, member = workspace_context

    try:
        rag_result = await RAGService.answer_question(
            session=db,
            workspace_id=workspace.id,
            user_id=current_user.id,
            conversation_id=conversation_id,
            question_text=payload.question,
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )

    # Fetch stored messages for response mapping
    user_msg = (
        await db.execute(select(ChatMessage).where(ChatMessage.id == rag_result.user_message_id))
    ).scalar_one()

    assistant_msg = (
        await db.execute(select(ChatMessage).where(ChatMessage.id == rag_result.assistant_message_id))
    ).scalar_one()

    return RAGQuestionResponse(
        conversation_id=rag_result.conversation_id,
        user_message=ChatMessageResponse.model_validate(user_msg),
        assistant_message=ChatMessageResponse.model_validate(assistant_msg),
        sources=rag_result.sources,
        token_usage=rag_result.token_usage,
        model_used=rag_result.model_used,
        provider=rag_result.provider,
    )


@router.get(
    "/workspaces/{workspace_id}/chat/conversations/{conversation_id}/messages",
    response_model=List[ChatMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="List message history in a conversation",
)
async def list_chat_messages(
    conversation_id: uuid.UUID,
    workspace_context: Tuple[Workspace, WorkspaceMember] = Depends(get_workspace_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ChatMessageResponse]:
    """Retrieve message history for a chat conversation."""
    workspace, member = workspace_context

    # Authorize conversation ownership
    c_stmt = select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.workspace_id == workspace.id,
        ChatConversation.user_id == current_user.id,
    )
    conversation = (await db.execute(c_stmt)).scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat conversation not found.",
        )

    m_stmt = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = list((await db.execute(m_stmt)).scalars().all())
    return [ChatMessageResponse.model_validate(m) for m in messages]


@router.post(
    "/meetings/{meeting_id}/chat",
    response_model=RAGQuestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Meeting-specific chat shortcut endpoint",
    description="Shortcut to ask a question scoped specifically to one meeting's transcript.",
)
async def meeting_chat_shortcut(
    payload: ChatMessageCreate,
    meeting_context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGQuestionResponse:
    """Ask a question scoped directly to a specific meeting."""
    meeting, member = meeting_context

    # Find or create a default chat conversation for this meeting and user
    c_stmt = select(ChatConversation).where(
        ChatConversation.workspace_id == meeting.workspace_id,
        ChatConversation.user_id == current_user.id,
        ChatConversation.meeting_id == meeting.id,
    ).order_by(ChatConversation.updated_at.desc())

    conversation = (await db.execute(c_stmt)).scalars().first()

    if not conversation:
        conversation = ChatConversation(
            id=uuid.uuid4(),
            workspace_id=meeting.workspace_id,
            user_id=current_user.id,
            meeting_id=meeting.id,
            title=f"Chat: {meeting.title[:50]}",
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # Execute RAG scoped to this meeting
    rag_result = await RAGService.answer_question(
        session=db,
        workspace_id=meeting.workspace_id,
        user_id=current_user.id,
        conversation_id=conversation.id,
        question_text=payload.question,
        meeting_id_filter=meeting.id,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
    )

    user_msg = (
        await db.execute(select(ChatMessage).where(ChatMessage.id == rag_result.user_message_id))
    ).scalar_one()

    assistant_msg = (
        await db.execute(select(ChatMessage).where(ChatMessage.id == rag_result.assistant_message_id))
    ).scalar_one()

    return RAGQuestionResponse(
        conversation_id=rag_result.conversation_id,
        user_message=ChatMessageResponse.model_validate(user_msg),
        assistant_message=ChatMessageResponse.model_validate(assistant_msg),
        sources=rag_result.sources,
        token_usage=rag_result.token_usage,
        model_used=rag_result.model_used,
        provider=rag_result.provider,
    )


@router.get(
    "/meetings/{meeting_id}/chat/history",
    status_code=status.HTTP_200_OK,
    summary="Get chat history for a specific meeting",
    description="Retrieve chronological chat messages and citations for the authenticated user in this meeting.",
)
async def get_meeting_chat_history(
    meeting_context: Tuple[Meeting, WorkspaceMember] = Depends(get_meeting_and_membership),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve chat message history for this meeting."""
    meeting, member = meeting_context

    c_stmt = (
        select(ChatConversation)
        .where(
            ChatConversation.workspace_id == meeting.workspace_id,
            ChatConversation.user_id == current_user.id,
            ChatConversation.meeting_id == meeting.id,
        )
        .order_by(ChatConversation.updated_at.desc())
    )
    conversation = (await db.execute(c_stmt)).scalars().first()
    if not conversation:
        return []

    m_stmt = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = list((await db.execute(m_stmt)).scalars().all())

    result = []
    for m in messages:
        sources_data = m.sources or []
        result.append({
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "role": m.role,
            "content": m.content,
            "citations": sources_data,
            "sources": sources_data,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return result
