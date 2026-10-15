"""Factory module for instantiating embedding provider implementations."""

import logging
from typing import Optional

from app.core.config import settings
from app.services.embedding.base import BaseEmbeddingProvider, EmbeddingPermanentError
from app.services.embedding.mock_provider import MockEmbeddingProvider
from app.services.embedding.openai_provider import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


def get_embedding_provider(
    provider_override: Optional[str] = None,
) -> BaseEmbeddingProvider:
    """Instantiate and return configured embedding provider."""
    provider_name = (provider_override or settings.EMBEDDING_PROVIDER or "mock").lower().strip()

    if provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY is missing. Falling back to MockEmbeddingProvider for embeddings."
            )
            return MockEmbeddingProvider()
        return OpenAIEmbeddingProvider()

    elif provider_name == "mock":
        return MockEmbeddingProvider()

    else:
        logger.warning(
            f"Unknown embedding provider '{provider_name}'. Defaulting to MockEmbeddingProvider."
        )
        return MockEmbeddingProvider()
