"""Convert persisted core state into visualization-safe, human-readable views.

Only explicit structured inputs/outputs and decision metadata are exposed.  This
module never attempts to reconstruct or display hidden model reasoning.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import WorkflowBundle


STAGES: list[tuple[str, str, str]] = [
    ("diagnosis_agent", "学情诊断", "Beta/BKT 学情、薄弱点与不确定性"),
    ("planner_agent", "路径规划", "先修约束与个性化学习顺序"),
    ("retrieval_agent", "知识检索", "BM25 / Vector / Graph / Version / MMR"),
    ("risk_router_service", "风险路由", "Fast / Standard / Strict 与调用预算"),
    ("generation_agent", "资源生成", "讲义、实操指南、分阶测试"),
    ("proofgraph_service", "ProofGraph", "Claim → Evidence → Validator → Result"),
    ("review_agent", "内容审核", "结构、证据、难度与发布条件"),
    ("critic_agent", "定向 Critic", "中高风险争议声明复查"),
    ("judge_agent", "Judge 裁决", "Strict 路径最终裁决"),
    ("feedback_agent", "反馈更新", "学习结果回写 LearnerModel"),
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


def _duration_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
    if started_at is None or finished_at is None:
        return None
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _run_dict(run: Any) -> dict[str, Any]:
    output_json = _jsonable(run.output_json or {})
    return {
        "run_id": run.id,
        "agent": run.agent_type,
        "status": run.status,
        "confidence": run.confidence,
        "summary": output_json.get("summary", "") if isinstance(output_json, dict) else "",
        "input": _jsonable(run.input_json or {}),
        "output": output_json,
        "error": run.error_message,
        "started_at": _jsonable(run.started_at),
        "finished_at": _jsonable(run.finished_at),
        "duration_ms": _duration_ms(run.started_at, run.finished_at),
    }


def _stage_status(stage_key: str, stage_runs: list[dict[str, Any]], state: dict[str, Any], terminal: bool) -> str:
    if stage_runs:
        latest = stage_runs[-1]
        if latest.get("status") == "failed":
            return "failed"
        return "success" if terminal or latest.get("finished_at") else "running"
    route = str((state.get("risk_route") or {}).get("route", "")).lower()
    if terminal and stage_key == "critic_agent" and route == "fast":
        return "skipped"
    if terminal and stage_key == "judge_agent" and route in {"fast", "standard"}:
        return "skipped"
    if terminal and stage_key == "feedback_agent":
        return "not_in_generation_request"
    return "pending"


def _diagnosis_view(bundle: "WorkflowBundle") -> dict[str, Any]:
    session = bundle.diagnosis_session
    if session is None:
        return {"mode": (bundle.session.state_data or {}).get("diagnosis_mode", "auto"), "session": None, "responses": []}
    responses = []
    for row in bundle.diagnosis_responses:
        selection = _jsonable(row.selection_score_json or {})
        responses.append({
            "item_id": row.item_id,
            "skill_id": row.skill_id,
            "concept_ids": _jsonable(row.concept_ids or []),
            "is_correct": bool(row.is_correct),
            "difficulty": row.difficulty,
            "response_time_sec": row.response_time_sec,
            "selection_score": selection,
            "answered_at": _jsonable(row.answered_at),
        })
    return {
        "mode": "adaptive",
        "session": {
            "session_id": session.id,
            "status": session.status,
            "target_skill_id": session.target_skill_id,
            "question_count": session.question_count,
            "tested_concept_ids": _jsonable(session.tested_concept_ids or []),
            "fatigue_state": _jsonable(session.fatigue_state or {}),
            "result": _jsonable(session.result_json or {}),
            "started_at": _jsonable(session.started_at),
            "finished_at": _jsonable(session.finished_at),
        },
        "responses": responses,
    }


def build_observability_view(bundle: "WorkflowBundle") -> dict[str, Any]:
    session = bundle.session
    state = _jsonable(session.state_data or {})
    runs = [_run_dict(run) for run in bundle.runs]
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_agent[str(run["agent"])].append(run)

    terminal = session.current_state in {"PUBLISHED", "FAILED"}
    pipeline = []
    for key, label, description in STAGES:
        stage_runs = by_agent.get(key, [])
        latest = stage_runs[-1] if stage_runs else None
        pipeline.append({
            "key": key,
            "label": label,
            "description": description,
            "status": _stage_status(key, stage_runs, state, terminal),
            "attempts": len(stage_runs),
            "summary": (latest or {}).get("summary", ""),
            "confidence": (latest or {}).get("confidence"),
            "duration_ms": (latest or {}).get("duration_ms"),
            "latest_output": (latest or {}).get("output", {}),
        })

    risk = state.get("risk_route") or ((by_agent.get("risk_router_service") or [{}])[-1].get("output", {}).get("output", {}).get("risk_route", {}))
    evidence = state.get("evidence_list") or []
    claim_graph = state.get("claim_graph") or {}
    graph_summary = claim_graph.get("summary") or {}

    workflow_duration_ms = None
    if session.created_at and session.updated_at:
        workflow_duration_ms = max(0, int((session.updated_at - session.created_at).total_seconds() * 1000))

    metrics = {
        "workflow_duration_ms": workflow_duration_ms,
        "agent_run_count": len(runs),
        "revision_count": session.revision_count,
        "evidence_count": len(evidence),
        "claim_count": int(graph_summary.get("claim_count", 0) or 0),
        "supported_claim_count": int(graph_summary.get("supported_claim_count", 0) or 0),
        "validated_claim_count": int(graph_summary.get("validated_claim_count", 0) or 0),
        "rejected_claim_count": int(graph_summary.get("rejected_claim_count", 0) or 0),
        "needs_confirmation_count": int(graph_summary.get("needs_confirmation_count", 0) or 0),
        "high_risk_traceability": graph_summary.get("high_risk_traceability"),
        "route": risk.get("route") if isinstance(risk, dict) else None,
        "pre_risk": risk.get("pre_risk") if isinstance(risk, dict) else None,
        "model_call_budget": risk.get("model_call_budget") if isinstance(risk, dict) else None,
    }

    resource = None
    if bundle.resource is not None:
        resource = {
            "resource_id": bundle.resource.id,
            "status": bundle.resource.status,
            "skill_id": bundle.resource.skill_id,
            "difficulty": bundle.resource.difficulty,
            "model_name": bundle.resource.model_name,
            "prompt_version": bundle.resource.prompt_version,
            "created_at": _jsonable(bundle.resource.created_at),
        }

    return {
        "read_only": True,
        "reasoning_policy": "仅展示结构化输入、输出、评分、证据和裁决，不展示模型隐式推理过程。",
        "overview": {
            "workflow_id": session.id,
            "learner_id": session.learner_id,
            "domain_id": session.domain_id,
            "target_goal": session.target_goal,
            "current_state": session.current_state,
            "revision_count": session.revision_count,
            "final_decision": state.get("final_decision"),
            "resource_id": state.get("resource_id"),
            "created_at": _jsonable(session.created_at),
            "updated_at": _jsonable(session.updated_at),
        },
        "metrics": metrics,
        "pipeline": pipeline,
        "layers": {
            "learner_model": {
                "learner_state": state.get("learner_state"),
                "mastery_summary": state.get("mastery_summary"),
                "weak_concepts": state.get("weak_concepts") or [],
                "uncertain_concepts": state.get("uncertain_concepts") or [],
            },
            "diagnosis": _diagnosis_view(bundle),
            "planner": {
                "learning_path": state.get("learning_path") or [],
                "target_skills": state.get("target_skills") or [],
            },
            "retrieval": {
                "meta": state.get("retrieval_meta") or {},
                "evidence": evidence,
            },
            "risk_router": risk or {},
            "generation": state.get("generated_resources") or {},
            "proofgraph": claim_graph,
            "review": state.get("review_result") or {},
            "critic": state.get("critic_result") or {},
            "judge": state.get("judge_result") or {},
            "feedback": state.get("feedback") or {},
        },
        "timeline": runs,
        "resource": resource,
        "raw_state": state,
    }


def recent_workflow_view(session: Any) -> dict[str, Any]:
    state = _jsonable(session.state_data or {})
    risk = state.get("risk_route") or {}
    return {
        "workflow_id": session.id,
        "learner_id": session.learner_id,
        "domain_id": session.domain_id,
        "target_goal": session.target_goal,
        "status": session.current_state,
        "route": risk.get("route") if isinstance(risk, dict) else None,
        "resource_id": state.get("resource_id"),
        "created_at": _jsonable(session.created_at),
        "updated_at": _jsonable(session.updated_at),
    }
