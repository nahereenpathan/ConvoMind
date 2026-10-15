"""Factory for resolving configured LLM intelligence providers."""

from functools import lru_cache
import logging
from app.core.config import settings
from app.services.intelligence.base import LLMProvider
from app.services.intelligence.mock_provider import MockLLMProvider
from app.services.intelligence.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Instantiate and return the configured LLM provider singleton."""
    provider_name = (settings.LLM_PROVIDER or "mock").lower().strip()

    if provider_name == "mock":
        logger.info("Using MockLLMProvider for meeting intelligence.")
        return MockLLMProvider(default_model="mock-gpt-4o")

    elif provider_name == "openai":
        if not (settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip()):
            if settings.ENVIRONMENT != "production":
                logger.info("OPENAI_API_KEY unconfigured for OpenAI LLM. Using MockLLMProvider for dev fallback.")
                return MockLLMProvider(default_model="mock-gpt-4o")
        logger.info(f"Using OpenAIProvider (model: {settings.OPENAI_MODEL}) for meeting intelligence.")
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
        )

    else:
        logger.warning(
            f"Unknown LLM_PROVIDER '{provider_name}'. Falling back to MockLLMProvider."
        )
        return MockLLMProvider(default_model="mock-gpt-4o")

