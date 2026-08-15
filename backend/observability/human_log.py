"""Human-readable decision log rendering."""

from __future__ import annotations

import json
from typing import Any


def _pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{float(value) * 100:.1f}%"


def _short(value: Any, limit: int = 180) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_human_log(view: dict[str, Any]) -> str:
    overview = view.get("overview", {})
    metrics = view.get("metrics", {})
    layers = view.get("layers", {})
    risk = layers.get("risk_router", {}) or {}
    learner = layers.get("learner_model", {}) or {}
    mastery = learner.get("mastery_summary", {}) or {}
    retrieval = layers.get("retrieval", {}) or {}
    proof = layers.get("proofgraph", {}) or {}
    proof_summary = proof.get("summary", {}) or {}

    lines: list[str] = []
    lines.append("知衡·ProofGraph｜全链路人类可读日志")
    lines.append("=" * 68)
    lines.append(f"Workflow : {overview.get('workflow_id', '-')}")
    lines.append(f"Learner  : {overview.get('learner_id', '-')}")
    lines.append(f"Domain   : {overview.get('domain_id', '-')}")
    lines.append(f"Goal     : {overview.get('target_goal') or '-'}")
    lines.append(f"State    : {overview.get('current_state', '-')}")
    lines.append(f"Decision : {overview.get('final_decision') or '-'}")
    lines.append(f"Updated  : {overview.get('updated_at') or '-'}")
    lines.append("")

    lines.append("[1] LearnerModel / 学情")
    lines.append(f"  overall_mastery     = {_pct(mastery.get('overall_mastery'))}")
    lines.append(f"  overall_uncertainty = {_pct(mastery.get('overall_uncertainty'))}")
    lines.append(f"  recommended_level   = {mastery.get('recommended_level', '-')}")
    weak = learner.get("weak_concepts") or []
    lines.append(f"  weak_concepts       = {_short([item.get('name') or item.get('concept_id') for item in weak[:8]])}")
    lines.append("")

    diagnosis = layers.get("diagnosis", {}) or {}
    diag_session = diagnosis.get("session") or {}
    lines.append("[2] Adaptive Diagnosis / 自适应诊断")
    lines.append(f"  mode           = {diagnosis.get('mode', '-')}")
    lines.append(f"  session        = {diag_session.get('session_id', '-')}")
    lines.append(f"  questions      = {diag_session.get('question_count', len(diagnosis.get('responses') or []))}")
    for index, response in enumerate((diagnosis.get("responses") or [])[:10], start=1):
        selection = response.get("selection_score") or {}
        lines.append(
            f"  Q{index:<2} {response.get('item_id','-')} | correct={response.get('is_correct')} "
            f"| IG={selection.get('information_gain', selection.get('ig', '-'))} "
            f"| score={selection.get('total_score', selection.get('selection_score', '-'))}"
        )
    lines.append("")

    planner = layers.get("planner", {}) or {}
    lines.append("[3] Planner / 学习路径")
    lines.append(f"  target_skills = {_short(planner.get('target_skills') or [])}")
    lines.append(f"  path          = {_short(planner.get('learning_path') or [], 360)}")
    lines.append("")

    lines.append("[4] Retriever / 证据检索")
    meta = retrieval.get("meta") or {}
    lines.append(f"  method        = {meta.get('retrieval_method', '-')}")
    lines.append(f"  evidence      = {len(retrieval.get('evidence') or [])}")
    lines.append(f"  version       = {meta.get('version_filter') or '-'}")
    lines.append(f"  graph_expand  = {meta.get('graph_expansion_applied', False)}")
    lines.append(f"  MMR           = {meta.get('mmr_applied', False)}")
    for item in (retrieval.get("evidence") or [])[:8]:
        lines.append(
            f"  - {item.get('evidence_id','-')} | rel={item.get('relevance_score','-')} "
            f"| verify={item.get('verification_status','-')} | {item.get('title','')}"
        )
    lines.append("")

    lines.append("[5] Risk Router / 风险路由")
    lines.append(f"  route               = {risk.get('route', '-')}")
    lines.append(f"  PreRisk             = {risk.get('pre_risk', '-')}")
    lines.append(f"  DomainRisk          = {risk.get('domain_risk', '-')}")
    lines.append(f"  Uncertainty         = {risk.get('uncertainty', '-')}")
    lines.append(f"  RetrievalWeakness   = {risk.get('retrieval_weakness', '-')}")
    lines.append(f"  Novelty             = {risk.get('novelty', '-')}")
    lines.append(f"  model_call_budget   = {risk.get('model_call_budget', '-')}")
    lines.append(f"  reasons             = {_short(risk.get('reasons') or [])}")
    lines.append("")

    lines.append("[6] Agent Pipeline / Agent 执行")
    for stage in view.get("pipeline", []):
        lines.append(
            f"  {stage.get('label','-'):<16} {stage.get('status','-'):<18} "
            f"attempts={stage.get('attempts',0)} duration={stage.get('duration_ms','-')}ms"
        )
        if stage.get("summary"):
            lines.append(f"      -> {stage['summary']}")
    lines.append("")

    lines.append("[7] ProofGraph / 声明证据验证")
    lines.append(f"  claims             = {proof_summary.get('claim_count', 0)}")
    lines.append(f"  supported          = {proof_summary.get('supported_claim_count', 0)}")
    lines.append(f"  validated          = {proof_summary.get('validated_claim_count', 0)}")
    lines.append(f"  rejected           = {proof_summary.get('rejected_claim_count', 0)}")
    lines.append(f"  need_confirmation  = {proof_summary.get('needs_confirmation_count', 0)}")
    lines.append(f"  high_risk_trace    = {_pct(proof_summary.get('high_risk_traceability'))}")
    for claim in (proof.get("claims") or [])[:10]:
        lines.append(
            f"  - {claim.get('claim_id','-')} | {claim.get('risk_level','-')} "
            f"| {claim.get('evidence_status','-')} | {claim.get('final_disposition','-')}"
        )
        lines.append(f"      {_short(claim.get('text') or claim.get('command') or '-', 220)}")
    lines.append("")

    lines.append("[8] Final / 汇总")
    lines.append(f"  route                    = {metrics.get('route', '-')}")
    lines.append(f"  evidence_count           = {metrics.get('evidence_count', 0)}")
    lines.append(f"  claim_count              = {metrics.get('claim_count', 0)}")
    lines.append(f"  revision_count           = {metrics.get('revision_count', 0)}")
    lines.append(f"  agent_run_count          = {metrics.get('agent_run_count', 0)}")
    lines.append(f"  workflow_duration_ms     = {metrics.get('workflow_duration_ms', '-')}")
    lines.append("")
    lines.append("说明：该日志只展示结构化输入/输出、证据、分数和裁决依据，不展示模型隐式推理。")
    return "\n".join(lines)
