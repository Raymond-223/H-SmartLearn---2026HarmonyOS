"""MMR + concept/source gain re-ranking.

The online selector follows the report's cheap path:
relevance - redundancy + concept gain + source gain, with a soft source quota.
"""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlparse


def _token_jaccard(a_tokens: set[str], b_tokens: set[str]) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return intersection / union if union > 0 else 0.0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _doc_tokens(doc: dict[str, Any]) -> set[str]:
    from app.services.bm25_service import _tokens as bm25_tokens
    text = " ".join([
        str(doc.get("title", "")),
        str(doc.get("content", "")),
        str(doc.get("skill_id", "")),
    ])
    return set(bm25_tokens(text))


def _concepts(doc: dict[str, Any]) -> set[str]:
    raw = doc.get("concept_ids") or doc.get("skill_ids") or ([doc.get("skill_id")] if doc.get("skill_id") else [])
    return {str(item) for item in raw if item}


def _source_key(doc: dict[str, Any]) -> str:
    url = str(doc.get("source") or doc.get("source_url") or "")
    host = urlparse(url).netloc.lower()
    if host:
        return host
    source_type = str(doc.get("source_type", "local"))
    title = str(doc.get("title", ""))
    return f"{source_type}:{title[:80]}"


def mmr_rerank(
    candidates: list[tuple[float, dict[str, Any]]],
    query_vector: list[float] | None = None,
    doc_vectors: dict[str, list[float]] | None = None,
    lambda_param: float = 0.7,
    top_k: int = 8,
    concept_gain_weight: float = 0.12,
    source_gain_weight: float = 0.08,
    source_quota: int = 3,
) -> list[tuple[float, dict[str, Any]]]:
    """Re-rank candidates using MMR plus cheap coverage signals.

    ``source_quota`` is a soft quota: once a source fills its quota, its score is
    penalized, but it is still eligible if alternatives are worse. This avoids
    dropping the only valid evidence for a concept.
    """
    if not candidates:
        return []
    if len(candidates) == 1:
        score, doc = candidates[0]
        enriched = dict(doc)
        enriched["selection_signals"] = {
            "concept_gain": 1.0 if _concepts(doc) else 0.0,
            "source_gain": 1.0,
            "source_quota_penalty": 0.0,
        }
        return [(score, enriched)]

    use_vectors = query_vector is not None and doc_vectors is not None and len(query_vector) > 0
    doc_token_cache: dict[str, set[str]] = {}
    for _, doc in candidates:
        eid = str(doc.get("evidence_id", doc.get("title", "")))
        doc_token_cache[eid] = _doc_tokens(doc)

    max_score = max(s for s, _ in candidates) if candidates else 1.0
    min_score = min(s for s, _ in candidates) if candidates else 0.0
    span = max(1e-9, max_score - min_score)
    normalized = [((s - min_score) / span if span else 1.0, doc) for s, doc in candidates]

    selected: list[tuple[str, float, dict[str, Any]]] = []
    remaining = list(normalized)
    covered_concepts: set[str] = set()
    source_counts: dict[str, int] = {}

    while remaining and len(selected) < top_k:
        best_idx = -1
        best_score = float("-inf")
        best_signals: dict[str, float] = {}

        for idx, (rel, doc) in enumerate(remaining):
            eid = str(doc.get("evidence_id", doc.get("title", "")))
            max_sim = 0.0
            for sel_eid, _, _sel_doc in selected:
                if use_vectors and doc_vectors:
                    v_a = doc_vectors.get(eid)
                    v_b = doc_vectors.get(sel_eid)
                    sim = _cosine_similarity(v_a, v_b) if v_a and v_b else _token_jaccard(
                        doc_token_cache.get(eid, set()), doc_token_cache.get(sel_eid, set())
                    )
                else:
                    sim = _token_jaccard(doc_token_cache.get(eid, set()), doc_token_cache.get(sel_eid, set()))
                max_sim = max(max_sim, sim)

            concepts = _concepts(doc)
            new_concepts = concepts - covered_concepts
            concept_gain = len(new_concepts) / max(1, len(concepts)) if concepts else 0.0
            source = _source_key(doc)
            source_gain = 1.0 if source_counts.get(source, 0) == 0 else 0.0
            quota_penalty = 0.12 if source_quota > 0 and source_counts.get(source, 0) >= source_quota else 0.0

            score = (
                lambda_param * rel
                - (1.0 - lambda_param) * max_sim
                + concept_gain_weight * concept_gain
                + source_gain_weight * source_gain
                - quota_penalty
            )
            if score > best_score:
                best_score = score
                best_idx = idx
                best_signals = {
                    "concept_gain": round(concept_gain, 4),
                    "source_gain": round(source_gain, 4),
                    "source_quota_penalty": round(quota_penalty, 4),
                    "redundancy": round(max_sim, 4),
                }

        _, doc = remaining.pop(best_idx)
        enriched = dict(doc)
        enriched["selection_signals"] = best_signals
        eid = str(enriched.get("evidence_id", enriched.get("title", "")))
        selected.append((eid, best_score, enriched))
        covered_concepts.update(_concepts(enriched))
        key = _source_key(enriched)
        source_counts[key] = source_counts.get(key, 0) + 1

    return [(round(score, 4), doc) for _, score, doc in selected]
