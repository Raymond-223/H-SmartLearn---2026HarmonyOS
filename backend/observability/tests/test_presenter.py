from datetime import datetime, timedelta
from types import SimpleNamespace

from observability.human_log import render_human_log
from observability.presenter import build_observability_view


def _run(agent, output, summary, seconds=0.05):
    start = datetime(2026, 8, 15, 12, 0, 0)
    return SimpleNamespace(
        id=f"run_{agent}",
        agent_type=agent,
        input_json={},
        output_json={"status": "success", "output": output, "summary": summary},
        status="success",
        confidence=0.9,
        started_at=start,
        finished_at=start + timedelta(seconds=seconds),
        error_message=None,
    )


def test_view_exposes_structured_layers_without_mutating_bundle():
    start = datetime(2026, 8, 15, 12, 0, 0)
    state = {
        "mastery_summary": {"overall_mastery": 0.62, "overall_uncertainty": 0.31, "recommended_level": "intermediate"},
        "weak_concepts": [{"concept_id": "nav2_lifecycle", "name": "Nav2生命周期", "mastery_probability": 0.35}],
        "learning_path": [{"skill_id": "tf2"}, {"skill_id": "nav2"}],
        "target_skills": ["nav2"],
        "evidence_list": [{"evidence_id": "E1", "title": "Nav2 docs", "verification_status": "trusted_source", "relevance_score": 0.88}],
        "retrieval_meta": {"retrieval_method": "bm25", "mmr_applied": True},
        "risk_route": {"route": "standard", "pre_risk": 0.51, "domain_risk": 0.55, "uncertainty": 0.31, "retrieval_weakness": 0.4, "novelty": 0.3, "model_call_budget": 2, "reasons": ["版本相关"]},
        "claim_graph": {"claims": [{"claim_id": "C1", "risk_level": "medium", "evidence_ids": ["E1"], "validator_ids": ["V1"], "evidence_status": "supported", "final_disposition": "PASS", "text": "Nav2 claim"}], "summary": {"claim_count": 1, "supported_claim_count": 1, "validated_claim_count": 1, "rejected_claim_count": 0, "needs_confirmation_count": 0, "high_risk_traceability": 1.0}},
        "final_decision": "published",
        "resource_id": "res_1",
    }
    session = SimpleNamespace(
        id="wf_1", learner_id="learner_1", domain_id="ros2_robotics", target_goal="学习Nav2",
        current_state="PUBLISHED", revision_count=0, state_data=state, created_at=start,
        updated_at=start + timedelta(seconds=2),
    )
    runs = [
        _run("retrieval_agent", {"evidence_list": state["evidence_list"]}, "检索完成"),
        _run("risk_router_service", {"risk_route": state["risk_route"]}, "风险路由=standard"),
        _run("proofgraph_service", {"claim_graph": state["claim_graph"]}, "ProofGraph完成"),
    ]
    bundle = SimpleNamespace(session=session, runs=runs, diagnosis_session=None, diagnosis_responses=[], resource=None)

    view = build_observability_view(bundle)
    assert view["read_only"] is True
    assert view["metrics"]["evidence_count"] == 1
    assert view["metrics"]["claim_count"] == 1
    assert view["layers"]["risk_router"]["route"] == "standard"
    assert view["pipeline"][2]["status"] == "success"
    assert view["pipeline"][8]["status"] == "skipped"  # Judge skipped on standard route.
    assert state["resource_id"] == "res_1"

    human = render_human_log(view)
    assert "全链路人类可读日志" in human
    assert "Risk Router" in human
    assert "ProofGraph" in human
