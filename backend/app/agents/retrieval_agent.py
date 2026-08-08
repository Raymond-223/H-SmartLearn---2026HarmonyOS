"""Upgraded retrieval agent with BM25, vector retrieval, version filtering,
skill-graph query expansion, and MMR deduplication.

Pipeline:
1. Collect verified documents from the database (or domain-package fallback)
2. Expand target skills into a weighted boost map via the skill graph
3. Apply version filter if specified
4. Run BM25 keyword search
5. Optionally run vector semantic search (when embedding provider is available)
6. Fuse BM25 + vector scores via weighted reciprocal rank fusion
7. Re-rank final candidates with MMR for diversity
8. Return top-k evidence items with relevance scores
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from sqlalchemy import select

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState
from app.services.domain_package_service import load_knowledge, skill_name_map
from app.core.database import async_session_factory
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.bm25_service import BM25Scorer, _tokens as bm25_tokens
from app.services.vector_service import (
    VectorStore,
    EmbeddingProvider,
    get_vector_store,
    get_embedding_provider,
    doc_to_text,
)
from app.services.mmr_service import mmr_rerank
from app.services.graph_expansion_service import expand_skills


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verified_database_documents(domain_id: str) -> list[dict]:
    """Load verified knowledge chunks from the database."""
    async with async_session_factory() as db:
        rows = list((await db.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeDocument.domain_id == domain_id,
                KnowledgeDocument.verification_status.in_(("verified", "trusted_source")),
                KnowledgeChunk.verification_status.in_(("verified", "trusted_source")),
            )
            .order_by(KnowledgeDocument.title, KnowledgeChunk.section, KnowledgeChunk.id)
        )).all())
    package_metadata = {
        str(item.get("evidence_id")): item
        for item in load_knowledge(domain_id)
        if item.get("evidence_id")
    }
    result: list[dict] = []
    for chunk, document in rows:
        metadata = package_metadata.get(str(chunk.id), {})
        source_type = document.source_type or metadata.get("source_type") or "local"
        result.append({
            "evidence_id": chunk.id,
            "title": document.title,
            "source": document.source_url or metadata.get("source_url") or "",
            "source_type": source_type,
            "source_trust": metadata.get("source_trust", 1.0 if source_type == "official" else 0.8),
            "version": chunk.version or document.version or metadata.get("version") or "knowledge-base",
            "content": chunk.content,
            "skill_id": chunk.skill_id or metadata.get("skill_id") or "",
            "skill_ids": metadata.get("skill_ids", []),
            "concept_ids": metadata.get("concept_ids", []),
            "risk_level": metadata.get("risk_level", "low"),
            "importance": metadata.get("importance", "support"),
            "section": chunk.section or (metadata.get("source_locator") or {}).get("value") or "",
            "verification_status": chunk.verification_status or document.verification_status or "pending",
        })
    return result


def _tokens(value: str) -> set[str]:
    """Backward-compatible query tokenizer; delegates to the BM25 tokenizer."""
    return set(bm25_tokens(value))


def _package_fallback(domain_id: str) -> list[dict]:
    """Load knowledge documents from domain-package JSON files."""
    result = []
    for index, item in enumerate(load_knowledge(domain_id), start=1):
        result.append({
            "evidence_id": item.get("evidence_id") or f"pkg_{domain_id}_{index:03d}",
            "title": item.get("title", ""),
            "source": item.get("source_url") or item.get("source", ""),
            "source_type": item.get("source_type", "local"),
            "source_trust": item.get("source_trust", 0.8),
            "version": item.get("version", "domain-package"),
            "content": item.get("claim") or item.get("content", ""),
            "skill_id": item.get("skill_id", ""),
            "skill_ids": item.get("skill_ids", []),
            "concept_ids": item.get("concept_ids", []),
            "risk_level": item.get("risk_level", "low"),
            "importance": item.get("importance", "support"),
            "section": (item.get("source_locator") or {}).get("value") or item.get("title", ""),
            "verification_status": item.get("verification_status", "pending"),
        })
    return result


# Must match GenerationAgent._assessment_items_from_package's slice: those are
# the bank items whose citations end up in the generated graded test.
GENERATED_TEST_ITEMS = 3


def _cited_evidence_ids(domain_id: str, skill_ids: list[str]) -> set[str]:
    """Evidence the packaged lesson material for these skills already cites.

    GenerationAgent copies ``evidence_ids`` verbatim out of ``practice_tasks``
    and ``assessment_bank``, and ReviewAgent rejects any citation missing from
    the retrieved ``evidence_list``. Relevance ranking alone does not guarantee
    those units land in the top-K, so a perfectly valid packaged citation can be
    reported as "引用不存在的证据" — the package accusing itself. Pinning them
    here keeps the provenance chain intact instead of silently dropping the
    citation at generation time.
    """
    from app.services.domain_package_service import load_assessment_bank, load_practice_tasks

    if not skill_ids:
        return set()
    wanted = set(skill_ids)
    required: set[str] = set()

    def collect(container: dict) -> None:
        for evidence_id in container.get("evidence_ids") or []:
            if evidence_id:
                required.add(str(evidence_id))

    for task in load_practice_tasks(domain_id):
        if str(task.get("skill_id", "")) not in wanted:
            continue
        collect(task)
        for step in task.get("steps") or []:
            collect(step)

    # Only the items generation actually puts in the graded test, selected the
    # same way GenerationAgent._assessment_items_from_package selects them.
    # Pinning the whole bank would swamp the ranked results for no benefit.
    for skill_id in sorted(wanted):
        rows = [
            item for item in load_assessment_bank(domain_id)
            if str(item.get("skill_id", "")) == skill_id
        ]
        rows.sort(key=lambda item: (int(item.get("difficulty", 1)), str(item.get("id", ""))))
        for item in rows[:GENERATED_TEST_ITEMS]:
            collect(item)

    return required


def _apply_version_filter(docs: list[dict], version_filter: str | None) -> list[dict]:
    """Filter documents by version substring match."""
    if not version_filter:
        return docs
    vf = version_filter.strip().lower()
    return [
        doc for doc in docs
        if vf in str(doc.get("version", "")).lower()
    ]


# ---------------------------------------------------------------------------
# Score fusion
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    bm25_results: list[tuple[float, dict]],
    vector_results: list[tuple[float, dict]],
    k: int = 60,
    bm25_weight: float = 0.6,
    vector_weight: float = 0.4,
) -> list[tuple[float, dict]]:
    """Combine BM25 and vector results via weighted Reciprocal Rank Fusion.

    Documents present in both lists get a score from each; documents in only
    one list still contribute (at reduced weight).
    """
    # Build evidence_id → doc map
    doc_map: dict[str, dict] = {}

    # BM25 ranks
    bm25_ranks: dict[str, int] = {}
    for rank, (_, doc) in enumerate(bm25_results):
        eid = str(doc.get("evidence_id", ""))
        doc_map[eid] = doc
        bm25_ranks[eid] = rank + 1

    # Vector ranks
    vector_ranks: dict[str, int] = {}
    for rank, (_, doc) in enumerate(vector_results):
        eid = str(doc.get("evidence_id", ""))
        doc_map[eid] = doc
        vector_ranks[eid] = rank + 1

    all_eids = set(bm25_ranks) | set(vector_ranks)
    fused: list[tuple[float, dict]] = []

    for eid in all_eids:
        doc = doc_map[eid]
        score = 0.0
        if eid in bm25_ranks:
            score += bm25_weight / (k + bm25_ranks[eid])
        if eid in vector_ranks:
            score += vector_weight / (k + vector_ranks[eid])
        fused.append((score, doc))

    fused.sort(key=lambda item: (-item[0], str(item[1].get("title", ""))))
    return fused


# ---------------------------------------------------------------------------
# Retrieval Agent
# ---------------------------------------------------------------------------

class RetrievalAgent(BaseAgent):
    agent_type = "retrieval_agent"

    # Configuration
    TOP_K = 8
    BM25_WEIGHT = 0.6
    VECTOR_WEIGHT = 0.4
    SKILL_BOOST_WEIGHT = 0.25  # max extra multiplier from graph expansion
    MMR_LAMBDA = 0.7
    GRAPH_MAX_HOPS = 2

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        # 1. Load documents
        docs = await _verified_database_documents(context.domain_id)
        source_mode = "verified_database"
        if not docs:
            docs = _package_fallback(context.domain_id)
            source_mode = "domain_package_fallback"

        # 2. Build query tokens
        names = skill_name_map(context.domain_id)
        targets = context.target_skills or (
            [context.source_skill_id] if context.source_skill_id else []
        )
        query_parts = [context.target_goal or ""]
        for skill_id in targets:
            query_parts.extend([skill_id, names.get(skill_id, "")])
        query_string = " ".join(query_parts)
        query_tokens = bm25_tokens(query_string)

        # 3. Skill graph expansion
        skill_boost_map = await expand_skills(
            context.domain_id, targets, max_hops=self.GRAPH_MAX_HOPS
        )

        # 4. Version filter
        version_filter = agent_input.get("version_filter") or getattr(
            context, "version_filter", None
        )
        filtered_docs = _apply_version_filter(docs, version_filter)
        if version_filter and not filtered_docs:
            return AgentResult(
                output={
                    "evidence_list": [],
                    "version_filter_miss": True,
                    "version_filter": version_filter,
                    "message": "没有找到匹配版本的证据"
                },
                confidence=0.2,
                next_action="request_more_context",
                summary="版本约束下无可用证据"
            )

        # 5. BM25 retrieval
        bm25 = BM25Scorer()
        bm25.index(filtered_docs)
        bm25_results = bm25.search(
            query_tokens,
            top_k=self.TOP_K * 3,  # over-fetch for fusion + MMR
            skill_boost_map=skill_boost_map,
        )

        # 6. Vector retrieval (if available)
        vector_results: list[tuple[float, dict]] = []
        vector_available = False
        query_embedding_vector: list[float] | None = None
        doc_vector_map: dict[str, list[float]] = {}
        embedding_provider = get_embedding_provider()
        if embedding_provider.available:
            # Build vector index for filtered docs
            texts = [doc_to_text(doc) for doc in filtered_docs]
            vectors = await embedding_provider.embed(texts)
            if vectors and len(vectors) == len(filtered_docs):
                vector_available = True
                vec_store = get_vector_store()
                vec_store.index(filtered_docs, vectors)
                doc_vector_map = {
                    str(doc.get("evidence_id", "")): vector
                    for doc, vector in zip(filtered_docs, vectors)
                }

                query_embedding = await embedding_provider.embed([query_string])
                if query_embedding and query_embedding[0]:
                    query_embedding_vector = query_embedding[0]
                    vector_results = vec_store.search(
                        query_embedding_vector,
                        top_k=self.TOP_K * 3,
                    )

        # 7. Fuse results
        if vector_available and vector_results:
            fused = _reciprocal_rank_fusion(
                bm25_results,
                vector_results,
                bm25_weight=self.BM25_WEIGHT,
                vector_weight=self.VECTOR_WEIGHT,
            )
        else:
            fused = [(s, doc) for s, doc in bm25_results]

        # 8. MMR deduplication
        # Try to get query vector for MMR; fallback to token-based Jaccard
        query_vector_for_mmr = None
        doc_vectors_for_mmr: dict[str, list[float]] | None = None
        if vector_available:
            doc_vectors_for_mmr = {
                str(doc.get("evidence_id", "")): doc_vector_map[str(doc.get("evidence_id", ""))]
                for _, doc in fused
                if str(doc.get("evidence_id", "")) in doc_vector_map
            }
            query_vector_for_mmr = query_embedding_vector

        ranked = mmr_rerank(
            fused,
            query_vector=query_vector_for_mmr,
            doc_vectors=doc_vectors_for_mmr,
            lambda_param=self.MMR_LAMBDA,
            top_k=self.TOP_K,
        )
        # Lightweight source/concept diversity adjustment inside Agent only.
        # Full schema-level changes are intentionally not introduced here.
        ranked = [
            (
                float(score)
                + 0.05 * float(doc.get("source_trust", 0.8))
                + 0.02 * len(doc.get("concept_ids", doc.get("skill_ids", []))),
                doc,
            )
            for score, doc in ranked
        ]
        ranked.sort(key=lambda item: item[0], reverse=True)
        ranked = ranked[:self.TOP_K]

        # 8b. Pin the evidence the packaged material for these skills cites.
        # These are appended after the ranked head rather than competing with
        # it, so relevance order is unchanged and only the tail grows. TOP_K is
        # therefore the budget for *ranked* evidence, not the length of the
        # list: the pinned tail is bounded by the package (one practice task
        # plus GENERATED_TEST_ITEMS bank items per target skill).
        required_ids = _cited_evidence_ids(context.domain_id, list(targets))
        if required_ids:
            present = {str(doc.get("evidence_id", "")) for _, doc in ranked}
            ranked.extend(
                (0.0, doc)
                for doc in filtered_docs
                if str(doc.get("evidence_id", "")) in required_ids - present
            )

        # 9. Build evidence output
        evidence = []
        for score, doc in ranked:
            source = str(doc.get("source", ""))
            evidence.append({
                "evidence_id": str(doc.get("evidence_id", "")),
                "title": str(doc.get("title", "")),
                "source_url": source,
                "source_type": str(doc.get("source_type", "local")),
                "source_domain": urlparse(source).netloc,
                "version": str(doc.get("version", "knowledge-base")),
                "content": str(doc.get("content", "")),
                "relevance_score": round(float(score), 4),
                "verification_status": str(doc.get("verification_status", "pending")),
                "source_trust": float(doc.get("source_trust", 0.8)),
                "concept_ids": doc.get("concept_ids", doc.get("skill_ids", [])),
                "risk_level": str(doc.get("risk_level", "low")),
                "importance": str(doc.get("importance", "support")),
            })

        local_count = sum(1 for item in evidence if item["source_type"] != "web")
        web_count = sum(1 for item in evidence if item["source_type"] == "web")
        expanded_skills = [
            sid for sid, w in sorted(skill_boost_map.items(), key=lambda x: -x[1])
            if sid not in set(targets) and w >= 0.3
        ]

        return AgentResult(
            output={
                "evidence_list": evidence,
                "local_count": local_count,
                "web_count": web_count,
                "query_terms": sorted(set(query_tokens)),
                "source_mode": source_mode,
                "retrieval_method": (
                    "bm25+vector" if vector_available else "bm25"
                ),
                "vector_search": vector_available,
                "mmr_applied": True,
                "version_filter": version_filter,
                "expanded_skills": expanded_skills,
                "graph_expansion_applied": len(expanded_skills) > 0,
            },
            confidence=(
                0.95
                if evidence and evidence[0].get("relevance_score", 0) >= 0.7
                else 0.78
            ),
            next_action="generate",
            evidence_ids=[item["evidence_id"] for item in evidence],
            summary=(
                f"BM25{' + 向量' if vector_available else ''}检索"
                f"{' + 图谱扩展' if expanded_skills else ''}"
                f" + MMR去重，选取{len(evidence)}条带验证状态的证据"
            ),
        )
