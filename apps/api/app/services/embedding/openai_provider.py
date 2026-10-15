"""OpenAI vector embedding provider implementation using httpx."""

import logging
from typing import List, Optional
import httpx

from app.core.config import settings
from app.services.embedding.base import (
    BaseEmbeddingProvider,
    EmbeddingError,
    EmbeddingPermanentError,
    EmbeddingTransientError,
)

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI vector embedding provider targeting text-embedding-3-small or custom models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
        timeout_seconds: float = 30.0,
    ):
        self._api_key = api_key or settings.OPENAI_API_KEY
        if not self._api_key:
            raise EmbeddingPermanentError("OPENAI_API_KEY is not configured in settings.")
        self._model = model or settings.EMBEDDING_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._timeout_seconds = timeout_seconds
        self._endpoint = "https://api.openai.com/v1/embeddings"

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings for list of texts via OpenAI API."""
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self._endpoint, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                embedding_objs = data.get("data", [])
                # Ensure ordered results by index field
                sorted_objs = sorted(embedding_objs, key=lambda x: x.get("index", 0))
                vectors = [obj["embedding"] for obj in sorted_objs]

                # Validate dimensions
                for idx, vec in enumerate(vectors):
                    if len(vec) != self._dimension:
                        raise EmbeddingPermanentError(
                            f"Dimension mismatch from OpenAI: expected {self._dimension}, "
                            f"received {len(vec)} at index {idx}"
                        )
                return vectors

            elif response.status_code in (429, 500, 502, 503, 504):
                err_msg = f"OpenAI API transient error HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(err_msg)
                raise EmbeddingTransientError(err_msg)

            elif response.status_code in (400, 401, 403, 404):
                err_msg = f"OpenAI API permanent error HTTP {response.status_code}: {response.text[:200]}"
                logger.error(err_msg)
                raise EmbeddingPermanentError(err_msg)

            else:
                err_msg = f"Unexpected OpenAI API response HTTP {response.status_code}: {response.text[:200]}"
                logger.error(err_msg)
                raise EmbeddingError(err_msg)

        except httpx.TimeoutException as exc:
            logger.warning(f"OpenAI embedding request timed out: {exc}")
            raise EmbeddingTransientError(f"Request timeout after {self._timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            logger.warning(f"OpenAI embedding network error: {exc}")
            raise EmbeddingTransientError(f"Network error: {exc}") from exc

    async def generate_query_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for single search query string."""
        results = await self.generate_embeddings([text])
        if not results:
            raise EmbeddingError("Empty result returned for query embedding.")
        return results[0]

    def get_dimension(self) -> int:
        return self._dimension

    def get_model_name(self) -> str:
        return self._model

    def get_provider_name(self) -> str:
        return "openai"
