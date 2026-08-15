"""Read-only loader for pluggable domain packages.

The loader keeps backwards compatibility with the original v1.x domain package
layout while exposing the richer ProofGraph KB 2.x data contract (concept graph,
procedures, validator registry, review queue and benchmark seeds).
"""

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

import yaml


DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "domain_packages"


def _package_dir(domain_id: str) -> Path:
    path = (DOMAIN_ROOT / domain_id).resolve()
    if DOMAIN_ROOT.resolve() not in path.parents:
        raise ValueError("invalid domain_id")
    if not path.exists():
        raise FileNotFoundError(f"domain package not found: {domain_id}")
    return path


@lru_cache(maxsize=16)
def load_domain_manifest(domain_id: str) -> dict[str, Any]:
    path = _package_dir(domain_id) / "manifest.yaml"
    if not path.exists():
        return {"domain_id": domain_id}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {"domain_id": domain_id}


@lru_cache(maxsize=16)
def load_knowledge_data_manifest(domain_id: str) -> dict[str, Any]:
    path = _package_dir(domain_id) / "knowledge_data_manifest.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=16)
def load_skill_nodes(domain_id: str) -> list[dict]:
    with (_package_dir(domain_id) / "skill_nodes.json").open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=16)
def load_skill_edges(domain_id: str) -> list[dict]:
    with (_package_dir(domain_id) / "skill_edges.json").open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=16)
def load_assessment_bank(domain_id: str) -> list[dict]:
    result: list[dict] = []
    path = _package_dir(domain_id) / "assessment_bank.jsonl"
    if not path.exists():
        return result
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                result.append(json.loads(line))
    return result


@lru_cache(maxsize=16)
def load_knowledge(domain_id: str) -> list[dict]:
    """Load evidence records.

    KB 2.x may explicitly point to the canonical evidence file in manifest.yaml.
    Older domain packages are still supported by globbing knowledge_documents/*.json.
    """
    package_dir = _package_dir(domain_id)
    manifest = load_domain_manifest(domain_id)
    evidence_file = (manifest.get("knowledge_files") or {}).get("evidence")
    if evidence_file:
        path = package_dir / str(evidence_file)
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else [data]

    docs_dir = package_dir / "knowledge_documents"
    result: list[dict] = []
    for path in sorted(docs_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            result.extend(data if isinstance(data, list) else [data])
    return result


@lru_cache(maxsize=16)
def load_concept_nodes(domain_id: str) -> list[dict]:
    path = _package_dir(domain_id) / "concept_nodes.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=16)
def load_concept_edges(domain_id: str) -> list[dict]:
    path = _package_dir(domain_id) / "concept_edges.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=16)
def load_practice_tasks(domain_id: str) -> list[dict]:
    path = _package_dir(domain_id) / "practice_tasks.jsonl"
    if not path.exists():
        return []
    result: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                result.append(json.loads(line))
    return result


@lru_cache(maxsize=16)
def load_validator_registry(domain_id: str) -> list[dict]:
    path = _package_dir(domain_id) / "validator_registry.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=16)
def load_human_review_queue(domain_id: str) -> list[dict]:
    path = _package_dir(domain_id) / "human_review_queue.jsonl"
    if not path.exists():
        return []
    result: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                result.append(json.loads(line))
    return result


@lru_cache(maxsize=16)
def load_retrieval_benchmark_seed(domain_id: str) -> list[dict]:
    path = _package_dir(domain_id) / "retrieval_benchmark_seed.jsonl"
    if not path.exists():
        return []
    result: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                result.append(json.loads(line))
    return result


def load_retrieval_benchmark_seeds(domain_id: str) -> list[dict]:
    """Plural compatibility alias used by evaluation/integration code."""
    return load_retrieval_benchmark_seed(domain_id)


def skill_name_map(domain_id: str) -> dict[str, str]:
    return {item["id"]: item["name"] for item in load_skill_nodes(domain_id)}


def topological_path(domain_id: str, target_skill: str | None = None) -> list[dict]:
    nodes = {item["id"]: item for item in load_skill_nodes(domain_id)}
    edges = load_skill_edges(domain_id)
    prereq: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        source = edge.get("from_skill_id") or edge.get("from")
        target = edge.get("to_skill_id") or edge.get("to")
        relation = edge.get("relation_type") or edge.get("relation")
        if relation == "prerequisite" and source in nodes and target in nodes:
            prereq[target].append(source)

    visited: set[str] = set()
    visiting: set[str] = set()
    ordered: list[str] = []

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError(f"cyclic prerequisite detected at skill: {node_id}")
        visiting.add(node_id)
        for parent in prereq.get(node_id, []):
            visit(parent)
        visiting.remove(node_id)
        visited.add(node_id)
        ordered.append(node_id)

    if target_skill and target_skill in nodes:
        visit(target_skill)
    else:
        for node_id in nodes:
            visit(node_id)

    return [nodes[node_id] for node_id in ordered]
