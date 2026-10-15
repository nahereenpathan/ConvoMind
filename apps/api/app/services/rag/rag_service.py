"""Core Retrieval-Augmented Generation (RAG) service orchestrating vector search, context building, LLM execution, and source attribution."""

from dataclasses import dataclass
import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatConversation, ChatMessage
from app.models.meeting import Meeting
from app.services.embedding.search_service import VectorSearchResult, VectorSearchService
from app.services.intelligence.factory import get_llm_provider
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.memory import ChatMemoryManager
from app.services.rag.prompts import RAG_SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


@dataclass
class RAGAnswerResult:
    """Structured response output from RAG question answering."""

    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID
    answer: str
    sources: List[Dict[str, Any]]
    token_usage: Dict[str, int]
    model_used: str
    provider: str


class RAGService:
    """Service providing grounded Retrieval-Augmented Generation (RAG) and conversational AI chat."""

    @staticmethod
    async def answer_question(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        question_text: str,
        meeting_id_filter: Optional[uuid.UUID] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> RAGAnswerResult:

        """Execute RAG pipeline to generate a grounded answer backed by verifiable transcript sources."""
        # 1. Fetch and authorize conversation
        c_stmt = (
            select(ChatConversation)
            .options(selectinload(ChatConversation.messages))
            .where(
                ChatConversation.id == conversation_id,
                ChatConversation.workspace_id == workspace_id,
                ChatConversation.user_id == user_id,
            )
        )
        conversation = (await session.execute(c_stmt)).scalar_one_or_none()
        if not conversation:
            raise ValueError(f"Chat conversation {conversation_id} not found or unauthorized.")

        # Determine meeting scope (if meeting-specific chat or filter provided)
        target_meeting_id = meeting_id_filter or conversation.meeting_id

        # Save User Question Message to DB first
        user_msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=question_text.strip(),
        )
        session.add(user_msg)
        await session.flush()

        # 2. Execute Vector Search with STRICT WORKSPACE ISOLATION IN SQL
        search_results: List[VectorSearchResult] = await VectorSearchService.search_similar_chunks(
            session=session,
            workspace_id=workspace_id,
            query_text=question_text.strip(),
            meeting_id=target_meeting_id,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        # If 0 results returned and target_meeting_id specified, check if completed transcript needs embedding generation
        if not search_results and target_meeting_id:
            from app.models.transcript import Transcript, TranscriptStatus
            from app.workers.tasks.embedding_tasks import _async_process_transcript_embeddings

            t_stmt = select(Transcript).where(
                Transcript.meeting_id == target_meeting_id,
                Transcript.workspace_id == workspace_id,
                Transcript.status == TranscriptStatus.COMPLETED,
            )
            t_res = await session.execute(t_stmt)
            transcript_obj = t_res.scalars().first()
            if transcript_obj:
                logger.info(f"Auto-triggering embedding generation for completed transcript {transcript_obj.id}")
                try:
                    await _async_process_transcript_embeddings(str(transcript_obj.id))
                    # Re-run vector search after embedding generation
                    search_results = await VectorSearchService.search_similar_chunks(
                        session=session,
                        workspace_id=workspace_id,
                        query_text=question_text.strip(),
                        meeting_id=target_meeting_id,
                        top_k=top_k,
                        score_threshold=score_threshold,
                    )
                except Exception as emb_err:
                    logger.warning(f"Auto-embedding generation failed: {emb_err}")

        # 3. Grounding Guardrail: Check if relevant context exists
        if not search_results:
            logger.info(
                f"RAG search returned 0 chunks above threshold {score_threshold} for workspace {workspace_id}. "
                "Returning grounded refusal without calling LLM."
            )
            grounded_answer = "I couldn't find this information in the transcript of this meeting."

            assistant_msg = ChatMessage(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role="assistant",
                content=grounded_answer,
                sources=[],
                tokens_used=0,
            )
            session.add(assistant_msg)
            await session.commit()

            return RAGAnswerResult(
                conversation_id=conversation.id,
                user_message_id=user_msg.id,
                assistant_message_id=assistant_msg.id,
                answer=grounded_answer,
                sources=[],
                token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                model_used="none",
                provider="guardrail",
            )

        # 4. Fetch Meeting Titles for context enrichment
        meeting_ids = list({r.meeting_id for r in search_results})
        m_stmt = select(Meeting.id, Meeting.title).where(Meeting.id.in_(meeting_ids))
        m_rows = (await session.execute(m_stmt)).all()
        meeting_titles = {str(r[0]): r[1] for r in m_rows}

        # 5. Build Context Blocks & Sources List
        context_str, sources = ContextBuilder.build_context(search_results, meeting_titles)
        system_prompt = RAG_SYSTEM_PROMPT_TEMPLATE.format(context_str=context_str)

        # 6. Format History Window Memory
        recent_messages = ChatMemoryManager.format_recent_messages(conversation.messages, max_messages=8)
        # Ensure latest question is included
        if not recent_messages or recent_messages[-1].get("content") != question_text.strip():
            recent_messages.append({"role": "user", "content": question_text.strip()})

        # 7. Invoke LLM Provider
        llm_provider = get_llm_provider()
        llm_output = await llm_provider.generate_chat_response(
            messages=recent_messages,
            system_prompt=system_prompt,
        )

        answer_text = llm_output.get("answer", "").strip()
        if not answer_text:
            answer_text = "I couldn't find this information in the transcript of this meeting."

        # If answer is a refusal indicating evidence was not found, do not present unrelated chunks as proof
        refusal_markers = ["couldn't find", "could not find", "could not be found", "not present in", "not found in"]
        if any(marker in answer_text.lower() for marker in refusal_markers):
            sources = []

        tokens_used = llm_output.get("token_usage", {}).get("total_tokens", 0)

        # 8. Persist Assistant Message with Sources metadata
        assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="assistant",
            content=answer_text,
            sources=sources,
            tokens_used=tokens_used,
        )
        session.add(assistant_msg)
        await session.commit()

        logger.info(
            f"RAG question answered successfully: conversation_id={conversation.id} "
            f"workspace_id={workspace_id} sources={len(sources)} tokens={tokens_used}"
        )

        return RAGAnswerResult(
            conversation_id=conversation.id,
            user_message_id=user_msg.id,
            assistant_message_id=assistant_msg.id,
            answer=answer_text,
            sources=sources,
            token_usage=llm_output.get("token_usage", {}),
            model_used=llm_output.get("model_used", "default"),
            provider=llm_output.get("provider", "mock"),
        )
