"""Mock embedding provider for zero-cost, offline testing and development."""

import hashlib
import math
from typing import List

from app.core.config import settings
from app.services.embedding.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider generating normalized vectors without external API calls."""

    def __init__(
        self,
        dimension: int = settings.EMBEDDING_DIMENSION,
        model_name: str = "mock-embedding-1536",
    ):
        self._dimension = dimension
        self._model_name = model_name

    def _generate_vector_from_text(self, text: str) -> List[float]:
        """Generate a zero-centered semantic feature unit vector from text tokens for accurate similarity scoring."""
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "what", "how", "why", "did", "this"}
        words = [w.lower().strip(".,!?:;\"'()[]{}") for w in text.split() if w.strip()]

        raw_vals = [0.0] * self._dimension

        # Concept synonyms map for semantic projection
        concept_synonyms = {
            "decision": ["agreed", "consensus", "finalized", "completed", "decide", "approved", "adopted"],
            "action": ["task", "milestone", "todo", "assign", "assigned", "responsible", "owner", "next", "step", "encompass"],
            "api": ["integration", "api", "backend", "schema", "endpoint", "module"],
            "isolation": ["workspace", "idempotency", "security", "tenant", "isolation", "strictly"],
            "pipeline": ["audio", "storage", "preparation", "recording", "speech", "indexing"],
        }

        # 1. Base domain vector (zero-centered)
        base_digest = hashlib.sha256(b"convomind_shared_meeting_domain").digest()
        for i in range(self._dimension):
            b_byte = base_digest[i % len(base_digest)]
            val = ((b_byte % 256) / 255.0) - 0.5
            raw_vals[i] += val * 0.1

        # 2. Token projections with semantic expansion
        for w in words:
            if len(w) < 2:
                continue

            weight = 0.2 if w in stop_words else 2.0

            # Direct word hashing
            w_hash = int(hashlib.sha256(w.encode("utf-8")).hexdigest()[:8], 16)
            idx1 = w_hash % self._dimension
            idx2 = (w_hash * 31 + 7) % self._dimension
            raw_vals[idx1] += weight
            raw_vals[idx2] += weight * 0.5

            # Synonym concept expansion
            for concept, syns in concept_synonyms.items():
                if w == concept or w in syns:
                    c_hash = int(hashlib.sha256(concept.encode("utf-8")).hexdigest()[:8], 16)
                    c_idx1 = c_hash % self._dimension
                    c_idx2 = (c_hash * 17 + 13) % self._dimension
                    raw_vals[c_idx1] += 1.8
                    raw_vals[c_idx2] += 1.2

        # L2 normalize vector
        sq_sum = sum(x * x for x in raw_vals)
        norm = math.sqrt(sq_sum) if sq_sum > 0 else 1.0
        normalized = [round(x / norm, 6) for x in raw_vals]
        return normalized

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts."""
        if not texts:
            return []
        return [self._generate_vector_from_text(t) for t in texts]

    async def generate_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for search query string."""
        return self._generate_vector_from_text(text)

    def get_dimension(self) -> int:
        return self._dimension

    def get_model_name(self) -> str:
        return self._model_name

    def get_provider_name(self) -> str:
        return "mock"
