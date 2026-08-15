"""Vector embedding service using the configured LLM provider.

When the LLM provider supports embeddings (OpenAI-compatible), this module
handles encoding text into dense vectors, building an in-memory vector index,
and performing cosine-similarity nearest-neighbor search.

When no embedding-capable provider is configured, search gracefully degrades
to returning no vector results rather than failing.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.config import settings
from app.providers.llm.factory import create_llm_provider


# ---------------------------------------------------------------------------
# Embedding provider abstraction
# ---------------------------------------------------------------------------

class EmbeddingProvider:
    """Minimal wrapper around the LLM provider's embedding endpoint."""

    def __init__(self) -> None:
        self._provider = create_llm_provider()
        self._available = False
        if self._provider is not None:
            # Check if the provider exposes an embedding method
            self._available = hasattr(self._provider, "embed")
        self._dim: int | None = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def dimension(self) -> int | None:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Encode a batch of texts into embedding vectors.

        Returns None if the provider is unavailable or the call fails.
        """
        if not self._available or self._provider is None:
            return None
        try:
            result = await self._provider.embed(texts)
            if result and self._dim is None:
                self._dim = len(result[0]) if result else None
            return result
        except Exception:
            return None


# ---------------------------------------------------------------------------
# In-memory vector store
# ---------------------------------------------------------------------------

class VectorStore:
    """Simple in-memory vector index with cosine-similarity search.

    Designed for knowledge-base scale (hundreds to low thousands of chunks).
    For larger collections, replace with an external vector DB.
    """

    def __init__(self) -> None:
        self._vectors: list[list[float]] = []
        self._docs: list[dict[str, Any]] = []

    @property
    def size(self) -> int:
        return len(self._docs)

    def clear(self) -> None:
        self._vectors.clear()
        self._docs.clear()

    def index(self, documents: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        """Load pre-computed vectors with their corresponding documents."""
        if len(documents) != len(vectors):
            raise ValueError(
                f"Document count ({len(documents)}) must match vector count ({len(vectors)})"
            )
        self._docs = list(documents)
        self._vectors = [list(v) for v in vectors]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 8,
    ) -> list[tuple[float, dict[str, Any]]]:
        """Return top-k documents by cosine similarity."""
        if not self._vectors:
            return []
        scored: list[tuple[float, int]] = []
        for idx, vec in enumerate(self._vectors):
            sim = self._cosine(query_vector, vec)
            if sim > 0:
                scored.append((sim, idx))
        scored.sort(key=lambda item: -item[0])
        return [(score, self._docs[idx]) for score, idx in scored[:top_k]]


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

_vector_store: VectorStore | None = None
_embedding_provider: EmbeddingProvider | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = EmbeddingProvider()
    return _embedding_provider


def reset_vector_services() -> None:
    global _vector_store, _embedding_provider
    _vector_store = None
    _embedding_provider = None


# ---------------------------------------------------------------------------
# Document-to-text helper
# ---------------------------------------------------------------------------

def doc_to_text(doc: dict[str, Any]) -> str:
    """Build a single searchable text from a knowledge document for embedding."""
    return " ".join([
        str(doc.get("title", "")),
        str(doc.get("content", "")),
        str(doc.get("skill_id", "")),
        " ".join(str(s) for s in (doc.get("skill_ids") or [])),
        str(doc.get("section", "")),
    ])
