from app.services.risk_router_service import RiskRouterService
from app.services.validation_service import ValidationService
from app.services.claim_graph_service import ClaimGraphService
from app.services.mmr_service import mmr_rerank
from app.workflow.state import WorkflowState


def _state(**kwargs):
    base = dict(
        workflow_id="wf_test",
        learner_id="learner",
        domain_id="ros2_robotics",
        target_goal="学习ROS2 Topic",
        source_skill_id="ros2_topic",
        target_skills=["ros2_topic"],
        mastery_summary={"overall_uncertainty": 0.15},
        evidence_list=[
            {
                "evidence_id": "e1",
                "title": "Topic",
                "content": "ROS2 Topic publisher subscriber chatter",
                "source_type": "official",
                "source_url": "https://docs.ros.org/a",
                "source_trust": 1.0,
                "verification_status": "verified",
                "risk_level": "low",
                "concept_ids": ["c_topic"],
            },
            {
                "evidence_id": "e2",
                "title": "CLI",
                "content": "ros2 topic echo chatter",
                "source_type": "official",
                "source_url": "https://docs.ros.org/b",
                "source_trust": 1.0,
                "verification_status": "verified",
                "risk_level": "low",
                "concept_ids": ["c_cli"],
            },
        ],
    )
    base.update(kwargs)
    return WorkflowState(**base)


def test_risk_router_fast_for_supported_low_risk_request():
    route = RiskRouterService().assess(_state())
    assert route.route in {"fast", "standard"}
    assert route.model_call_budget in {1, 2}
    assert 0 <= route.pre_risk <= 1


def test_risk_router_forces_strict_for_destructive_request():
    route = RiskRouterService().assess(_state(target_goal="请 sudo fdisk 修改 /dev/sda 分区"))
    assert route.route == "strict"
    assert route.force_strict is True
    assert route.model_call_budget == 4


def test_static_validator_blocks_destructive_command_without_execution():
    result = ValidationService.shell_safety("sudo rm -rf /")
    assert result.status == "fail"


def test_claim_graph_binds_claim_evidence_and_validator():
    state = _state()
    state.generated_resources = {
        "lecture": {
            "sections": [{"heading": "定义", "content": "Topic用于发布订阅通信", "citations": ["e1"]}]
        },
        "practice_guide": {
            "risk_level": "low",
            "evidence_ids": ["e2"],
            "validator_ids": ["val_command_safety"],
            "steps": [{
                "order": 1,
                "title": "查看话题",
                "command": "ros2 topic list",
                "expected_result": "显示话题列表",
                "evidence_ids": ["e2"],
                "validator_ids": ["val_command_safety"],
                "risk_level": "low",
                "ros_version": "humble",
            }],
        },
        "graded_test": {"items": []},
    }
    graph = ClaimGraphService("ros2_robotics").build(state)
    assert graph["summary"]["claim_count"] == 2
    assert graph["summary"]["supported_claim_count"] == 2
    practice_claim = next(c for c in graph["claims"] if c["path"].startswith("practice_guide"))
    assert practice_claim["final_disposition"] == "PASS"
    assert any(r["validator_id"] == "val_command_safety" and r["status"] == "pass" for r in practice_claim["validation_results"])


def test_claim_graph_rejects_destructive_command():
    state = _state(target_goal="高风险操作")
    state.generated_resources = {
        "lecture": {"sections": []},
        "practice_guide": {
            "risk_level": "high",
            "evidence_ids": ["e2"],
            "validator_ids": ["val_command_safety"],
            "steps": [{
                "order": 1,
                "title": "危险操作",
                "command": "rm -rf /",
                "expected_result": "无",
                "evidence_ids": ["e2"],
                "validator_ids": ["val_command_safety"],
                "risk_level": "high",
            }],
        },
        "graded_test": {"items": []},
    }
    graph = ClaimGraphService("ros2_robotics").build(state)
    assert graph["summary"]["rejected_claim_count"] == 1
    assert graph["claims"][0]["final_disposition"] == "REJECT"


def test_mmr_rewards_new_concepts_and_sources():
    candidates = [
        (1.0, {"evidence_id": "a", "title": "A", "content": "topic basics", "concept_ids": ["c1"], "source_url": "https://one.example/a"}),
        (0.95, {"evidence_id": "b", "title": "B", "content": "topic basics duplicate", "concept_ids": ["c1"], "source_url": "https://one.example/b"}),
        (0.90, {"evidence_id": "c", "title": "C", "content": "qos compatibility", "concept_ids": ["c2"], "source_url": "https://two.example/c"}),
    ]
    ranked = mmr_rerank(candidates, top_k=3)
    assert ranked[0][1]["selection_signals"]["source_gain"] == 1.0
    assert any(doc["selection_signals"]["concept_gain"] > 0 for _, doc in ranked[1:])
