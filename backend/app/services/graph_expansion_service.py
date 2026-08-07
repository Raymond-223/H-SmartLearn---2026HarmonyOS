"""Skill-graph query expansion.

Expands a set of target skill IDs into a weighted boost map by walking
prerequisite, dependent, and related edges in the skill graph. This increases
retrieval recall for documents tagged with skills connected to the targets.
"""

from __future__ import annotations

from collections import deque

from app.models.skill_graph import SkillNode, SkillEdge
from app.core.database import async_session_factory
from sqlalchemy import select


# ---------------------------------------------------------------------------
# Expansion weights
# ---------------------------------------------------------------------------

# How far to expand along each relation type
_DEFAULT_MAX_HOPS = 2

# Decay factor per hop: weight = base_weight * (decay ** hop_distance)
_DECAY: dict[str, float] = {
    "prerequisite": 0.6,   # prerequisite skills get moderate boost
    "related": 0.5,        # related skills get lighter boost
    "postrequisite": 0.4,  # skills that depend on the target get lightest boost
}

# Base weights per relation (applied at hop 0, i.e. direct neighbors)
_BASE_WEIGHT: dict[str, float] = {
    "prerequisite": 0.35,
    "related": 0.25,
    "postrequisite": 0.20,
}


async def _load_edges(domain_id: str) -> list[SkillEdge]:
    """Load all edges for a domain from the database."""
    async with async_session_factory() as db:
        rows = list((await db.execute(
            select(SkillEdge).join(
                SkillNode, SkillEdge.from_skill_id == SkillNode.id
            ).where(SkillNode.domain_id == domain_id)
        )).scalars().all())
    return rows


async def expand_skills(
    domain_id: str,
    target_skill_ids: list[str],
    max_hops: int = _DEFAULT_MAX_HOPS,
) -> dict[str, float]:
    """Compute a boost map for skill-graph-expanded retrieval.

    Args:
        domain_id: The domain to load edges from.
        target_skill_ids: The original target skill IDs from the workflow.
        max_hops: Maximum expansion depth along edges.

    Returns:
        Dict mapping skill_id → boost weight (0.0 – 1.0). Higher = more relevant.
    """
    if not target_skill_ids:
        return {}

    target_set = set(target_skill_ids)
    edges = await _load_edges(domain_id)
    if not edges:
        return {sid: 0.0 for sid in target_set}

    # Build adjacency: source -> [(target, relation)]
    forward: dict[str, list[tuple[str, str]]] = {}
    backward: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        src = edge.from_skill_id
        tgt = edge.to_skill_id
        rel = edge.relation_type or "related"
        forward.setdefault(src, []).append((tgt, rel))
        backward.setdefault(tgt, []).append((src, rel))

    # BFS from each target skill along all relation directions
    boosts: dict[str, float] = {}

    for start in target_set:
        boosts[start] = max(boosts.get(start, 0.0), 1.0)  # exact target = max boost

        queue: deque[tuple[str, int, str, float]] = deque()

        # Edge semantics: A --prerequisite--> B means A is a prerequisite of B.
        # Therefore an incoming prerequisite edge points to a prerequisite of the
        # current target, while an outgoing prerequisite edge points to a
        # postrequisite/dependent skill.
        for neighbor, rel in forward.get(start, []):
            effective_rel = "postrequisite" if rel == "prerequisite" else rel
            weight = _BASE_WEIGHT.get(effective_rel, 0.25)
            queue.append((neighbor, 1, effective_rel, weight))
        for neighbor, rel in backward.get(start, []):
            effective_rel = "prerequisite" if rel == "prerequisite" else rel
            weight = _BASE_WEIGHT.get(effective_rel, 0.25)
            queue.append((neighbor, 1, effective_rel, weight))

        visited: set[str] = {start}
        while queue:
            node, hop, rel, weight = queue.popleft()
            if node in visited:
                continue
            if hop > max_hops:
                continue
            visited.add(node)

            boosts[node] = max(boosts.get(node, 0.0), weight)

            decay = _DECAY.get(rel, 0.5)
            next_weight = weight * decay
            if next_weight < 0.05:  # prune negligible weights
                continue

            # Beyond the direct neighborhood, use a conservative related
            # relation. Direct prerequisite/postrequisite semantics above are
            # exact; multi-hop paths can mix directions and should not inherit a
            # misleading hard label.
            for neighbor, _next_rel in forward.get(node, []):
                if neighbor not in visited:
                    queue.append((neighbor, hop + 1, "related", next_weight * 0.8))
            for neighbor, _next_rel in backward.get(node, []):
                if neighbor not in visited:
                    queue.append((neighbor, hop + 1, "related", next_weight * 0.8))

    return boosts
