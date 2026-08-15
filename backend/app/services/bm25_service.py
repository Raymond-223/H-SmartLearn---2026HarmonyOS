"""BM25 relevance scoring for multilingual (English + Chinese) knowledge retrieval.

Implements Okapi BM25 with no external NLP dependencies — uses regex tokenization
consistent with the existing retrieval patterns in the codebase.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any


def _tokens(text: str) -> list[str]:
    """Tokenize text into English and Chinese terms (order-preserving, dedup-friendly)."""
    text = text.lower()
    tokens: list[str] = []
    # English alphanumeric groups (2+ chars)
    tokens.extend(re.findall(r"[a-z0-9_+#.-]{2,}", text))
    # Chinese character sequences (2-8 chars sliding)
    chinese_raw = re.findall(r"[一-鿿]+", text)
    for segment in chinese_raw:
        if len(segment) <= 2:
            tokens.append(segment)
        else:
            # bigram sliding window for Chinese
            for i in range(len(segment) - 1):
                tokens.append(segment[i:i + 2])
    return tokens


class BM25Scorer:
    """Okapi BM25 implementation for document ranking.

    Typical usage::

        scorer = BM25Scorer()
        scorer.index(corpus)          # once per corpus
        results = scorer.search(query_tokens, top_k=8)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._doc_count = 0
        self._avg_dl = 0.0
        self._doc_lengths: dict[int, int] = {}
        self._doc_freqs: dict[str, int] = defaultdict(int)
        self._idf_cache: dict[str, float] = {}
        self._doc_terms: dict[int, list[str]] = {}
        self._doc_map: dict[int, dict[str, Any]] = {}
        self._next_id = 0

    def index(self, documents: list[dict[str, Any]]) -> None:
        """Build BM25 index from a list of document dicts.

        Each doc must have at least 'title' and 'content' keys.
        """
        self._doc_count = len(documents)
        self._doc_lengths.clear()
        self._doc_freqs.clear()
        self._idf_cache.clear()
        self._doc_terms.clear()
        self._doc_map.clear()

        total_length = 0
        for doc in documents:
            doc_id = self._next_id
            self._next_id += 1
            searchable = " ".join([
                str(doc.get("title", "")),
                str(doc.get("content", "")),
                str(doc.get("skill_id", "")),
                " ".join(str(s) for s in doc.get("skill_ids", [])),
                str(doc.get("section", "")),
            ])
            terms = _tokens(searchable)
            self._doc_terms[doc_id] = terms
            self._doc_lengths[doc_id] = len(terms)
            self._doc_map[doc_id] = doc
            total_length += len(terms)

            seen_in_doc: set[str] = set()
            for term in terms:
                if term not in seen_in_doc:
                    self._doc_freqs[term] += 1
                    seen_in_doc.add(term)

        self._avg_dl = total_length / max(1, self._doc_count)

    def _idf(self, term: str) -> float:
        if term in self._idf_cache:
            return self._idf_cache[term]
        df = self._doc_freqs.get(term, 0)
        # Smooth IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        value = math.log((self._doc_count - df + 0.5) / max(0.5, df + 0.5) + 1.0)
        self._idf_cache[term] = value
        return value

    def score(self, query_tokens: set[str] | list[str], doc_id: int) -> float:
        """Compute BM25 score for a single document given query tokens."""
        terms = self._doc_terms.get(doc_id)
        if not terms:
            return 0.0
        dl = self._doc_lengths.get(doc_id, 0)
        if dl == 0:
            return 0.0

        term_counts: dict[str, int] = defaultdict(int)
        for t in terms:
            term_counts[t] += 1

        total = 0.0
        for token in query_tokens:
            tf = term_counts.get(token, 0)
            if tf == 0:
                continue
            idf = self._idf(token)
            # BM25 term weight
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / max(1.0, self._avg_dl))
            total += idf * numerator / denominator
        return total

    def search(
        self,
        query_tokens: set[str] | list[str],
        top_k: int = 8,
        skill_boost_map: dict[str, float] | None = None,
    ) -> list[tuple[float, dict[str, Any]]]:
        """Rank all indexed documents by BM25 score against query tokens.

        Args:
            query_tokens: Set or list of query term strings.
            top_k: Maximum number of results to return.
            skill_boost_map: Optional mapping of skill_id → boost weight (0–1)
                             for graph-expanded skill relevance boosting.

        Returns:
            List of (score, doc) tuples sorted by descending score.
        """
        qt = set(query_tokens) if isinstance(query_tokens, list) else query_tokens
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc_id in self._doc_map:
            bm25 = self.score(qt, doc_id)
            if bm25 <= 0:
                continue
            doc = self._doc_map[doc_id]
            score = bm25

            # Skill-graph boost
            if skill_boost_map:
                skill_values = {
                    str(doc.get("skill_id", "")),
                    *[str(s) for s in doc.get("skill_ids", [])],
                }
                for skill_id, boost in skill_boost_map.items():
                    if skill_id in skill_values:
                        score *= (1.0 + boost)
                        break  # apply highest-matched boost only

            scored.append((score, doc))

        scored.sort(key=lambda item: (-item[0], str(item[1].get("title", ""))))
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Convenience singleton for per-request usage
# ---------------------------------------------------------------------------

_instance: BM25Scorer | None = None


def get_bm25() -> BM25Scorer:
    global _instance
    if _instance is None:
        _instance = BM25Scorer()
    return _instance


def reset_bm25() -> None:
    global _instance
    _instance = None
