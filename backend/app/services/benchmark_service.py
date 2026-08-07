"""Executable functional regression benchmark for all packaged skills and profiles.

This suite runs retrieval, deterministic generation and review for every skill in
both domain packages and for each supported learner profile. It measures internal
functional consistency; it is not a substitute for an independent expert-labelled
quality evaluation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.agents.generation_agent import GenerationAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.review_agent import ReviewAgent
from app.services.domain_package_service import load_skill_nodes, topological_path
from app.workflow.state import WorkflowState


@dataclass(frozen=True)
class BenchmarkThresholds:
    max_hallucination_rate: float = 5.0
    min_difficulty_match_accuracy: float = 95.0
    min_core_knowledge_coverage: float = 95.0
    min_review_pass_rate: float = 95.0
    min_case_count: int = 60
    min_profile_count: int = 3


PROFILES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("beginner", "basic", {
        "education": "专科", "major": "零基础转专业", "target_role": "入门开发工程师",
        "weekly_hours": 4,
        "preferences": {"explanation_style": "通俗", "resource_priority": "理论优先"},
    }),
    ("mechanical", "intermediate", {
        "education": "本科", "major": "机械工程", "target_role": "机器人系统工程师",
        "weekly_hours": 7,
        "preferences": {"explanation_style": "类比为主", "resource_priority": "实践优先"},
    }),
    ("developer", "advanced", {
        "education": "本科", "major": "软件工程", "target_role": "高级平台开发工程师",
        "weekly_hours": 12,
        "preferences": {"explanation_style": "专业", "resource_priority": "均衡"},
    }),
)
DOMAINS: tuple[str, ...] = ("ros2_robotics", "c_programming")
_CACHE: dict[str, Any] | None = None
_CACHE_LOCK = asyncio.Lock()


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _valid_verified_evidence(item: dict[str, Any]) -> bool:
    """Internal functional acceptance, not an expert claim-level verification.

    Human ``verified`` evidence is always accepted. Curated ``trusted_source``
    evidence is accepted only for low-risk material, matching ReviewAgent.
    """
    status = str(item.get("verification_status", ""))
    risk_level = str(item.get("risk_level", "low")).lower()
    if status != "verified" and not (status == "trusted_source" and risk_level == "low"):
        return False
    source_type = str(item.get("source_type", "local"))
    source_url = str(item.get("source_url", "")).strip()
    if source_type in {"web", "official"}:
        return _valid_http_url(source_url)
    return bool(source_url or item.get("title") or item.get("content"))


async def _run_case(
    domain_id: str, skill: dict, profile_id: str, expected_level: str, learner_profile: dict[str, Any]
) -> dict[str, Any]:
    skill_id = str(skill["id"])
    path = topological_path(domain_id, skill_id)
    context = WorkflowState(
        workflow_id=f"benchmark_{domain_id}_{skill_id}_{profile_id}",
        learner_id=f"benchmark_{profile_id}",
        domain_id=domain_id,
        target_goal=f"掌握{skill.get('name', skill_id)}",
        target_skills=[skill_id],
        learning_path=[{"skill_id": str(node["id"]), "name": str(node.get("name", node["id"]))} for node in path],
        source_skill_id=skill_id,
        requested_difficulty=expected_level,
        assessment_result={"recommended_level": expected_level},
        learner_profile=learner_profile,
    )

    retrieval = await RetrievalAgent().run(context, {})
    context.evidence_list = list(retrieval.output.get("evidence_list", []))
    generation = GenerationAgent()._generate_deterministic(context, {})
    payload = generation.output
    context.generated_resources = payload.get("resources", {})
    review = await ReviewAgent().run(context, {})

    citations = payload.get("citations", [])
    evidence_map = {str(item.get("evidence_id")): item for item in context.evidence_list}
    invalid_citations = [
        citation for citation in citations
        if citation not in evidence_map or not _valid_verified_evidence(evidence_map[citation])
    ]
    resources = context.generated_resources or {}
    lecture = resources.get("lecture", {})
    practice = resources.get("practice_guide", {})
    test = resources.get("graded_test", {})
    sections = lecture.get("sections", [])
    steps = practice.get("steps", [])
    items = test.get("items", [])

    required_checks = [
        len(sections) >= 3,
        all(section.get("content") and section.get("citations") for section in sections),
        len(steps) >= 3,
        all(step.get("command") and step.get("expected_result") for step in steps),
        len(items) >= 3,
        all(item.get("skill_id") == skill_id for item in items),
        all(item.get("correct_answer") in {option.get("key") for option in item.get("options", [])} for item in items),
        payload.get("target_skill") == skill_id,
        payload.get("metadata", {}).get("personalization", {}).get("explanation_style") ==
            learner_profile.get("preferences", {}).get("explanation_style"),
        payload.get("metadata", {}).get("personalization", {}).get("resource_priority") ==
            learner_profile.get("preferences", {}).get("resource_priority"),
    ]
    coverage = sum(1 for check in required_checks if check) / len(required_checks) * 100.0
    return {
        "domain_id": domain_id,
        "skill_id": skill_id,
        "profile_type": profile_id,
        "expected_level": expected_level,
        "predicted_level": str(payload.get("difficulty", "")),
        "invalid_citation_count": len(invalid_citations),
        "citation_count": len(citations),
        "core_knowledge_coverage": coverage,
        "review_decision": review.output.get("decision"),
        "review_issue_count": len(review.output.get("issues", [])),
    }


async def get_benchmark_summary(*, force_refresh: bool = False) -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None and not force_refresh:
        return _CACHE

    async with _CACHE_LOCK:
        if _CACHE is not None and not force_refresh:
            return _CACHE

        cases: list[dict[str, Any]] = []
        for domain_id in DOMAINS:
            for skill in load_skill_nodes(domain_id):
                for profile_id, expected_level, learner_profile in PROFILES:
                    cases.append(await _run_case(
                        domain_id, skill, profile_id, expected_level, learner_profile
                    ))

        thresholds = BenchmarkThresholds()
        case_count = len(cases)
        citation_total = sum(int(case["citation_count"]) for case in cases)
        invalid_total = sum(int(case["invalid_citation_count"]) for case in cases)
        hallucination_rate = round((invalid_total / citation_total * 100.0) if citation_total else 100.0, 2)
        difficulty_match = round(
            sum(1 for case in cases if case["expected_level"] == case["predicted_level"]) / case_count * 100.0,
            2,
        )
        coverage = round(sum(float(case["core_knowledge_coverage"]) for case in cases) / case_count, 2)
        review_pass_rate = round(
            sum(1 for case in cases if case["review_decision"] == "approve") / case_count * 100.0,
            2,
        )
        profiles = [profile_id for profile_id, _, _ in PROFILES]
        checks = {
            "hallucination": hallucination_rate < thresholds.max_hallucination_rate,
            "difficulty_match": difficulty_match >= thresholds.min_difficulty_match_accuracy,
            "core_coverage": coverage >= thresholds.min_core_knowledge_coverage,
            "review_pass": review_pass_rate >= thresholds.min_review_pass_rate,
            "case_count": case_count >= thresholds.min_case_count,
            "profile_count": len(profiles) >= thresholds.min_profile_count,
        }
        _CACHE = {
            "suite": "competition-functional-regression-v4",
            "status": "pass" if all(checks.values()) else "needs_attention",
            "case_count": case_count,
            "profile_count": len(profiles),
            "profiles": profiles,
            "domains": list(DOMAINS),
            "metrics": {
                "hallucination_rate": hallucination_rate,
                "difficulty_match_accuracy": difficulty_match,
                "core_knowledge_coverage": coverage,
                "review_pass_rate": review_pass_rate,
            },
            "thresholds": {
                "hallucination_rate": f"<{thresholds.max_hallucination_rate}%",
                "difficulty_match_accuracy": f">={thresholds.min_difficulty_match_accuracy}%",
                "core_knowledge_coverage": f">={thresholds.min_core_knowledge_coverage}%",
                "review_pass_rate": f">={thresholds.min_review_pass_rate}%",
                "case_count": f">={thresholds.min_case_count}",
                "profile_count": f">={thresholds.min_profile_count}",
            },
            "checks": checks,
            "failed_cases": [
                case for case in cases
                if case["review_decision"] != "approve"
                or case["expected_level"] != case["predicted_level"]
                or case["invalid_citation_count"] > 0
                or case["core_knowledge_coverage"] < 100.0
            ],
            "disclaimer": (
                "该结果由项目在运行时执行60个领域技能×画像组合得到，用于验证检索、生成、审核、已审核证据引用和难度匹配的一致性；"
                "它不是独立专家标注的教学质量或事实准确性外部评测。"
            ),
        }
        return _CACHE
