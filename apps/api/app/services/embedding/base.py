"""Base abstract interface and exceptions for vector embedding providers."""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingError(Exception):
    """Base exception for all embedding provider failures."""

    pass


class EmbeddingTransientError(EmbeddingError):
    """Transient exception suitable for Celery retry (e.g. rate limit, timeout, network blip)."""

    pass


class EmbeddingPermanentError(EmbeddingError):
    """Permanent non-retryable exception (e.g. invalid credentials, dimension mismatch)."""

    pass


class BaseEmbeddingProvider(ABC):
    """Abstract Base Class for text embedding providers."""

    @abstractmethod
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings for a list of text strings."""
        pass

    @abstractmethod
    async def generate_query_embedding(self, text: str) -> List[float]:
        """Generate dense vector embedding for a single search query string."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the vector dimension produced by this provider and model."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the target model identifier string."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name identifier string."""
        pass
