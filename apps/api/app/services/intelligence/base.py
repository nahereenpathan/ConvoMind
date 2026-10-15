"""Abstract base class and exceptions for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.services.intelligence.schemas import MeetingIntelligenceOutput


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    pass


class LLMTransientError(LLMError):
    """Transient LLM failure (e.g. rate limits, network timeouts, 503) safe to retry with backoff."""

    pass


class LLMPermanentError(LLMError):
    """Permanent LLM failure (e.g. invalid auth, schema violation, model context length) that should not be retried."""

    pass


class LLMProvider(ABC):
    """Abstract interface for large language model providers generating structured meeting intelligence."""

    @abstractmethod
    async def generate_meeting_intelligence(
        self,
        transcript_text: str,
        segments: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> MeetingIntelligenceOutput:
        """Analyze a meeting transcript and return structured meeting intelligence."""
        pass

    @abstractmethod
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate conversational chat response for RAG context. Returns dict with 'answer' and 'token_usage'."""
        pass

    @abstractmethod
    async def generate_structured_json(
        self,
        prompt: str,
        response_schema: Any,
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """Generate structured response validated against response_schema (a Pydantic BaseModel)."""
        pass


