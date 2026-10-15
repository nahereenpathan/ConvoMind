"""Conversation history windowing and memory management for RAG chat."""

from typing import Dict, List
from app.models.chat import ChatMessage


class ChatMemoryManager:
    """Manages chat conversation message memory windowing to prevent token explosion."""

    @staticmethod
    def format_recent_messages(
        messages: List[ChatMessage],
        max_messages: int = 10,
    ) -> List[Dict[str, str]]:
        """Return the N most recent user and assistant messages formatted for LLM input."""
        if not messages:
            return []

        # Take last N messages
        recent = messages[-max_messages:]
        formatted = []
        for msg in recent:
            if msg.role in ("user", "assistant"):
                formatted.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return formatted
