"""Offline integrity audit for the bundled ROS2 domain knowledge data.

This validates structure and referential integrity only. It intentionally does
not claim that a source supports a claim or that a procedure is executable;
those require human/source review and/or the Validator sandbox.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1] / "domain_packages" / "ros2_robotics"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_dag(nodes: set[str], edges: list[dict], relation: str = "prerequisite") -> tuple[bool, list[str]]:
    indeg = {node: 0 for node in nodes}
    graph: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.get("relation") != relation:
            continue
        source, target = edge.get("from"), edge.get("to")
        if source not in nodes or target not in nodes:
            continue
        graph[source].append(target)
        indeg[target] += 1
    q = deque([node for node, deg in indeg.items() if deg == 0])
    seen = []
    while q:
        node = q.popleft(); seen.append(node)
        for nxt in graph[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return len(seen) == len(nodes), [node for node, deg in indeg.items() if deg > 0]


def main() -> int:
    evidence = json.loads((ROOT / "knowledge_documents" / "ros2_knowledge_300.json").read_text(encoding="utf-8"))
    concepts = json.loads((ROOT / "concept_nodes.json").read_text(encoding="utf-8"))
    concept_edges = json.loads((ROOT / "concept_edges.json").read_text(encoding="utf-8"))
    skills = json.loads((ROOT / "skill_nodes.json").read_text(encoding="utf-8"))
    skill_edges = json.loads((ROOT / "skill_edges.json").read_text(encoding="utf-8"))
    assessment = load_jsonl(ROOT / "assessment_bank.jsonl")
    tasks = load_jsonl(ROOT / "practice_tasks.jsonl")
    benchmark = load_jsonl(ROOT / "retrieval_benchmark_seed.jsonl")
    review = load_jsonl(ROOT / "human_review_queue.jsonl")
    validators = json.loads((ROOT / "validator_registry.json").read_text(encoding="utf-8"))

    errors: list[str] = []
    warnings: list[str] = []
    eid = [x.get("evidence_id") for x in evidence]
    cid = [x.get("id") for x in concepts]
    sid = [x.get("id") for x in skills]
    vid = [x.get("id") for x in validators]

    if len(evidence) != 300: errors.append(f"expected 300 evidence records, got {len(evidence)}")
    if len(eid) != len(set(eid)): errors.append("duplicate evidence_id")
    if len({x.get('claim') for x in evidence}) != len(evidence): errors.append("duplicate atomic claims")
    if len(cid) != len(set(cid)): errors.append("duplicate concept id")
    if len(vid) != len(set(vid)): errors.append("duplicate validator id")

    evidence_ids, concept_ids, skill_ids, validator_ids = set(eid), set(cid), set(sid), set(vid)
    required = ["evidence_id","claim","source_id","source_url","source_type","source_trust","source_locator","version","skill_id","concept_ids","importance","risk_level","applicability","verification_status","verification","provenance"]
    for x in evidence:
        missing = [k for k in required if k not in x]
        if missing: errors.append(f"{x.get('evidence_id')}: missing fields {missing}")
        if x.get("skill_id") not in skill_ids: errors.append(f"{x.get('evidence_id')}: unknown skill {x.get('skill_id')}")
        for c in x.get("concept_ids", []):
            if c not in concept_ids: errors.append(f"{x.get('evidence_id')}: unknown concept {c}")
        url = x.get("source_url", "")
        if url and urlparse(url).scheme not in {"http","https"}: errors.append(f"{x.get('evidence_id')}: bad source url")
        if x.get("version") != "humble": warnings.append(f"{x.get('evidence_id')}: non-Humble version")
        if x.get("verification_status") == "verified" and not x.get("verification",{}).get("human_verified"):
            errors.append(f"{x.get('evidence_id')}: verified without human_verified")

    for q in assessment:
        if q.get("skill_id") not in skill_ids: errors.append(f"{q.get('id')}: unknown skill")
        keys = {o.get("key") for o in q.get("options", [])}
        if q.get("type") == "single_choice" and q.get("correct_answer") not in keys:
            errors.append(f"{q.get('id')}: correct answer missing from options")
        for e in q.get("evidence_ids", []):
            if e not in evidence_ids: errors.append(f"{q.get('id')}: unknown evidence {e}")

    for task in tasks:
        if task.get("skill_id") not in skill_ids: errors.append(f"{task.get('id')}: unknown skill")
        if not task.get("failure_cases"): errors.append(f"{task.get('id')}: missing failure_cases")
        if not task.get("rollback"): errors.append(f"{task.get('id')}: missing rollback")
        if not task.get("expected_output"): errors.append(f"{task.get('id')}: missing expected_output")
        for e in task.get("evidence_ids", []):
            if e not in evidence_ids: errors.append(f"{task.get('id')}: unknown evidence {e}")
        for v in task.get("validator_ids", []):
            if v not in validator_ids: errors.append(f"{task.get('id')}: unknown validator {v}")

    for row in review:
        if row.get("evidence_id") not in evidence_ids: errors.append(f"review queue references unknown {row.get('evidence_id')}")
    if {row.get("evidence_id") for row in review} != evidence_ids:
        errors.append("human review queue does not cover every evidence unit")

    skill_ok, skill_cycle = check_dag(skill_ids, skill_edges)
    concept_ok, concept_cycle = check_dag(concept_ids, concept_edges)
    if not skill_ok: errors.append(f"skill prerequisite graph has cycle: {skill_cycle}")
    if not concept_ok: errors.append(f"concept prerequisite graph has cycle: {concept_cycle}")

    stats = {
        "evidence": len(evidence), "unique_evidence_ids": len(set(eid)), "unique_claims": len({x.get('claim') for x in evidence}),
        "concepts": len(concepts), "skills": len(skills), "assessments": len(assessment), "practice_tasks": len(tasks),
        "validator_specs": len(validators), "benchmark_seeds": len(benchmark), "review_queue": len(review),
        "human_verified": sum(bool(x.get("verification",{}).get("human_verified")) for x in evidence),
        "verification_status": Counter(x.get("verification_status") for x in evidence),
        "source_domains": Counter(urlparse(x.get("source_url","")).netloc for x in evidence),
        "risk_levels": Counter(x.get("risk_level") for x in evidence),
        "skill_graph_dag": skill_ok, "concept_graph_dag": concept_ok,
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=dict))
    if warnings:
        print("WARNINGS:")
        for item in warnings[:30]: print("-", item)
    if errors:
        print("ERRORS:")
        for item in errors: print("-", item)
        return 1
    print("PASS: structural and referential integrity checks passed.")
    print("NOTE: PASS does not imply claim-level source verification or executable procedure validation.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
