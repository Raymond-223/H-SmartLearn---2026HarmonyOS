"""Maximal Marginal Relevance (MMR) re-ranking for search result deduplication.

MMR balances relevance (similarity to query) against novelty (dissimilarity to
already-selected results), producing a diverse final ranking.
"""

from __future__ import annotations

import math
from typing import Any


def _token_jaccard(a_tokens: set[str], b_tokens: set[str]) -> float:
    """Jaccard similarity between two token sets (fallback when vectors unavailable)."""
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return intersection / union if union > 0 else 0.0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two dense vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _doc_tokens(doc: dict[str, Any]) -> set[str]:
    """Extract a token set from a document for fallback comparison."""
    from app.services.bm25_service import _tokens as bm25_tokens
    text = " ".join([
        str(doc.get("title", "")),
        str(doc.get("content", "")),
        str(doc.get("skill_id", "")),
    ])
    return set(bm25_tokens(text))


def mmr_rerank(
    candidates: list[tuple[float, dict[str, Any]]],
    query_vector: list[float] | None = None,
    doc_vectors: dict[str, list[float]] | None = None,
    lambda_param: float = 0.7,
    top_k: int = 8,
) -> list[tuple[float, dict[str, Any]]]:
    """Re-rank candidates using Maximal Marginal Relevance.

    Args:
        candidates: List of (score, doc) tuples sorted by relevance.
        query_vector: Optional dense vector for the query. If None, falls back
                      to token-level Jaccard for similarity calculations.
        doc_vectors: Optional mapping of evidence_id → embedding vector.
        lambda_param: Trade-off between relevance and diversity (0 = max diversity,
                      1 = original ranking). Default 0.7.
        top_k: Maximum number of results to return.

    Returns:
        Re-ranked list of (mmr_score, doc) tuples.
    """
    if len(candidates) <= 1:
        return candidates[:top_k]

    use_vectors = (
        query_vector is not None
        and doc_vectors is not None
        and len(query_vector) > 0
    )

    # Precompute token sets for fallback mode
    query_tokens: set[str] = set()
    doc_token_cache: dict[str, set[str]] = {}
    if not use_vectors:
        for _, doc in candidates:
            eid = str(doc.get("evidence_id", doc.get("title", "")))
            doc_token_cache[eid] = _doc_tokens(doc)

    # Normalize relevance scores to [0, 1] range for scale consistency
    max_score = max(s for s, _ in candidates) if candidates else 1.0
    normalized = [
        (s / max(0.0001, max_score), doc) for s, doc in candidates
    ]

    selected: list[tuple[str, float, dict[str, Any]]] = []  # (eid, mmr, doc)
    remaining = list(normalized)  # copy

    while remaining and len(selected) < top_k:
        best_idx = -1
        best_mmr = -1.0

        for idx, (rel, doc) in enumerate(remaining):
            eid = str(doc.get("evidence_id", doc.get("title", "")))

            # Compute max similarity to already-selected docs
            max_sim = 0.0
            if selected:
                for sel_eid, _, sel_doc in selected:
                    if use_vectors and doc_vectors:
                        v_a = doc_vectors.get(eid)
                        v_b = doc_vectors.get(sel_eid)
                        if v_a and v_b:
                            sim = _cosine_similarity(v_a, v_b)
                        else:
                            sim = _token_jaccard(
                                doc_token_cache.get(eid, set()),
                                doc_token_cache.get(sel_eid, set()),
                            )
                    else:
                        sim = _token_jaccard(
                            doc_token_cache.get(eid, set()),
                            doc_token_cache.get(sel_eid, set()),
                        )
                    if sim > max_sim:
                        max_sim = sim

            # MMR = λ * relevance - (1-λ) * max_similarity
            mmr = lambda_param * rel - (1.0 - lambda_param) * max_sim
            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = idx

        if best_idx >= 0:
            _, doc = remaining.pop(best_idx)
            eid = str(doc.get("evidence_id", doc.get("title", "")))
            selected.append((eid, best_mmr, doc))

    # Return with original-format scores (reconstructed to reflect relevance+novelty)
    return [(round(mmr, 4), doc) for _, mmr, doc in selected]
