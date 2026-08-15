"""Focused regression tests for the layered review contract."""

import asyncio
from copy import deepcopy

from app.agents.generation_agent import GenerationAgent
from app.agents.review_agent import ReviewAgent
from app.validators import KnowledgePointValidator
from app.workflow.state import WorkflowState


def _context() -> WorkflowState:
    context = WorkflowState(
        workflow_id="layered_review_test",
        learner_id="reviewer",
        domain_id="ros2_robotics",
        target_goal="掌握Topic话题通信",
        target_skills=["ros2_topic"],
        source_skill_id="ros2_topic",
        requested_difficulty="intermediate",
        assessment_result={"recommended_level": "intermediate"},
        learning_path=[
            {"skill_id": "linux_environment"},
            {"skill_id": "ros2_node"},
            {"skill_id": "ros2_topic"},
        ],
        evidence_list=[
            {
                "evidence_id": "ev_001",
                "title": "ROS2 Topic evidence",
                "source_type": "local",
                "source_url": "packaged://ros2/topic",
                "verification_status": "verified",
                "content": "ROS2 Humble Topic uses publishers and subscribers.",
            },
            {
                "evidence_id": "ev_002",
                "title": "ROS2 command evidence",
                "source_type": "local",
                "source_url": "packaged://ros2/commands",
                "verification_status": "verified",
                "content": "ros2 topic echo and ros2 topic hz provide observable checks.",
            },
            {
                "evidence_id": "ev_003",
                "title": "ROS2 safety evidence",
                "source_type": "local",
                "source_url": "packaged://ros2/safety",
                "verification_status": "verified",
                "content": "Validate commands in an isolated environment first.",
            },
        ],
    )
    generated = GenerationAgent()._generate_deterministic(context, {})
    context.generated_resources = generated.output["resources"]
    return context


def _run(context: WorkflowState, agent_input: dict | None = None) -> dict:
    return asyncio.run(ReviewAgent().run(context, agent_input or {})).output


def test_layered_review_approves_valid_bundle_and_exposes_validator():
    output = _run(_context())

    assert output["decision"] == "approve"
    assert [(layer["level"], layer["name"], layer["status"]) for layer in output["layers"]] == [
        (1, "structure", "pass"),
        (2, "evidence", "pass"),
        (3, "safe_execution", "pass"),
    ]
    assert output["validator"]["valid"] is True
    assert set(output["knowledge_point"]) == set(KnowledgePointValidator.required_fields)
    assert "dificulty" in output["knowledge_point"]


def test_validator_rejects_bad_knowledge_point_contract_in_first_layer():
    context = _context()
    point, _ = KnowledgePointValidator.from_domain("ros2_robotics", "ros2_topic")
    point = deepcopy(point)
    point.pop("tags")
    point["dificulty"] = 9
    point["prerequisite_ids"] = ["ros2_topic", "not_a_skill"]

    output = _run(context, {"knowledge_point": point})
    structure = output["layers"][0]

    assert output["decision"] == "revise"
    assert structure["status"] == "fail"
    assert output["validator"]["valid"] is False
    assert {issue["location"] for issue in output["validator"]["issues"]} >= {
        "knowledge_point.tags",
        "knowledge_point.dificulty",
        "knowledge_point.prerequisite_ids",
    }


def test_second_layer_rejects_unverified_evidence():
    context = _context()
    context.evidence_list[0]["verification_status"] = "pending"

    output = _run(context)

    assert output["layers"][0]["status"] == "pass"
    assert output["layers"][1]["status"] == "fail"
    assert any(issue["type"] == "evidence_unverified" for issue in output["layers"][1]["issues"])


def test_third_layer_rejects_unsafe_execution_command():
    context = _context()
    context.generated_resources["practice_guide"]["steps"][0]["command"] = "sudo rm -rf /"

    output = _run(context)

    assert output["layers"][0]["status"] == "pass"
    assert output["layers"][1]["status"] == "pass"
    assert output["layers"][2]["status"] == "fail"
    assert any(issue["type"] == "unsafe_command" for issue in output["layers"][2]["issues"])
