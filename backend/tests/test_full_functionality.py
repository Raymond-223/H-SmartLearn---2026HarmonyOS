import asyncio
import os
import tempfile
import subprocess

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_smartlearn.db"
os.environ["WORKFLOW_STEP_DELAY_SECONDS"] = "0"

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.generation_agent import GenerationAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.review_agent import ReviewAgent
from app.api.workflows import run_workflow_task
from app.core.database import init_db, async_session_factory
from app.main import app
from app.models.resource import GeneratedResource
from app.services.domain_package_service import load_skill_nodes, topological_path
from app.workflow.state import WorkflowState


async def wait_for_resource(client: AsyncClient, workflow_id: str) -> str:
    for _ in range(100):
        payload = (await client.get(f"/api/v1/workflows/{workflow_id}")).json()
        if payload["status"] == "PUBLISHED":
            return payload["resource_id"]
        if payload["status"] in {"FAILED"}:
            pytest.fail(payload.get("error_message", payload["status"]))
        await asyncio.sleep(0.02)
    pytest.fail("workflow did not finish")


async def private_test_answers(resource_id: str) -> dict[str, str]:
    async with async_session_factory() as db:
        resource = await db.get(GeneratedResource, resource_id)
        items = (resource.content_json or {})["resources"]["graded_test"]["items"]
        return {str(item["id"]): str(item["correct_answer"]) for item in items}


@pytest.mark.asyncio
async def test_learner_read_update_and_target_skill_workflow():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        learner_id = (await client.post("/api/v1/learners", json={
            "education": "本科", "major": "机械", "target_role": "机器人开发", "weekly_hours": 6,
            "preferences": {"explanation_style": "通俗", "resource_priority": "实践优先"},
        })).json()["learner_id"]
        detail = (await client.get(f"/api/v1/learners/{learner_id}")).json()
        assert detail["major"] == "机械"
        updated = (await client.put(f"/api/v1/learners/{learner_id}", json={
            "major": "信息工程", "weekly_hours": 9,
            "preferences": {"explanation_style": "严格", "resource_priority": "讲义优先"},
        })).json()
        assert updated["major"] == "信息工程"
        assert updated["weekly_hours"] == 9

        workflow = (await client.post("/api/v1/workflows", json={
            "learner_id": learner_id,
            "domain_id": "ros2_robotics",
            "target_skill_id": "ros2_tf2",
            "target_goal": "掌握TF2坐标变换",
        })).json()
        resource_id = await wait_for_resource(client, workflow["workflow_id"])
        # Re-delivering the same background task after publication must be an idempotent no-op.
        await run_workflow_task(workflow["workflow_id"])
        repeated_status = (await client.get(f"/api/v1/workflows/{workflow['workflow_id']}")).json()
        assert repeated_status["status"] == "PUBLISHED"
        assert repeated_status["resource_id"] == resource_id
        resource = (await client.get(f"/api/v1/resources/{resource_id}")).json()
        assert resource["target_skill"] == "ros2_tf2"
        assert all(item["skill_id"] == "ros2_tf2" for item in resource["graded_test"]["items"])
        personalization = resource["metadata"]["personalization"]
        assert personalization["major"] == "信息工程"
        assert personalization["explanation_style"] == "严格"
        assert personalization["resource_priority"] == "讲义优先"

        invalid = await client.post(f"/api/v1/resources/{resource_id}/test", json={
            "answers": [{"item_id": resource["graded_test"]["items"][0]["id"], "answer": "A"}],
        })
        assert invalid.status_code == 422
        assert all("correct_answer" not in item for item in resource["graded_test"]["items"])
        answer_key = await private_test_answers(resource_id)
        valid = await client.post(f"/api/v1/resources/{resource_id}/test", json={
            "answers": [
                {"item_id": item["id"], "answer": answer_key[item["id"]]}
                for item in resource["graded_test"]["items"]
            ],
        })
        assert valid.status_code == 200
        assert valid.json()["score"] == 1.0

        feedback = await client.post(f"/api/v1/resources/{resource_id}/feedback", json={
            "correct_rate": 0.0, "practice_score": 0.0,
            "practice_results": [
                {"order": step["order"], "success": True}
                for step in resource["practice_guide"]["steps"]
            ],
            "subjective_difficulty": "appropriate", "error_tags": [],
        })
        assert feedback.status_code == 200
        duplicate = await client.post(f"/api/v1/resources/{resource_id}/feedback", json={
            "practice_results": [
                {"order": step["order"], "success": True}
                for step in resource["practice_guide"]["steps"]
            ],
            "subjective_difficulty": "appropriate", "error_tags": [],
        })
        assert duplicate.status_code == 200
        assert duplicate.json()["decision"] in {"recorded", "complete"}
        report = (await client.get(
            f"/api/v1/learners/{learner_id}/report?domain_id=ros2_robotics"
        )).json()
        tf2 = next(item for item in report["skill_mastery"] if item["skill_id"] == "ros2_tf2")
        assert tf2["score"] >= 80


@pytest.mark.asyncio
async def test_all_twenty_skill_resources_are_complete_and_reviewable():
    for domain_id in ("ros2_robotics", "c_programming"):
        for skill in load_skill_nodes(domain_id):
            skill_id = skill["id"]
            context = WorkflowState(
                workflow_id=f"full_{domain_id}_{skill_id}",
                learner_id="full_test",
                domain_id=domain_id,
                target_goal=f"掌握{skill['name']}",
                target_skills=[skill_id],
                source_skill_id=skill_id,
                requested_difficulty="intermediate",
                assessment_result={"recommended_level": "intermediate"},
                learning_path=[
                    {"skill_id": row["id"], "name": row["name"]}
                    for row in topological_path(domain_id, skill_id)
                ],
            )
            retrieval = await RetrievalAgent().run(context, {})
            context.evidence_list = retrieval.output["evidence_list"]
            generation = GenerationAgent()._generate_deterministic(context, {})
            context.generated_resources = generation.output["resources"]
            review = await ReviewAgent().run(context, {})
            assert generation.output["target_skill"] == skill_id
            assert len(context.generated_resources["practice_guide"]["steps"]) >= 3
            items = context.generated_resources["graded_test"]["items"]
            assert len(items) >= 3
            assert {item["correct_answer"] for item in items[:3]} == {"A", "B", "C"}
            assert review.output["decision"] == "approve", (domain_id, skill_id, review.output["issues"])

@pytest.mark.asyncio
async def test_final_skill_completes_and_resource_reopens_as_recorded():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        learner_id = (await client.post("/api/v1/learners", json={
            "education": "本科", "major": "信息工程", "target_role": "软件开发", "weekly_hours": 8,
            "preferences": {"explanation_style": "严格", "resource_priority": "实践优先"},
        })).json()["learner_id"]

        invalid = await client.post("/api/v1/workflows", json={
            "learner_id": learner_id,
            "domain_id": "c_programming",
            "target_skill_id": "ros2_topic",
            "target_goal": "非法跨领域目标",
        })
        assert invalid.status_code == 422

        workflow = (await client.post("/api/v1/workflows", json={
            "learner_id": learner_id,
            "domain_id": "c_programming",
            "target_skill_id": "c_pointer",
            "target_goal": "完成C语言学习路径",
        })).json()
        resource_id = await wait_for_resource(client, workflow["workflow_id"])
        resource = (await client.get(f"/api/v1/resources/{resource_id}")).json()
        assert resource["feedback_recorded"] is False

        premature = await client.post(f"/api/v1/resources/{resource_id}/feedback", json={
            "practice_results": [
                {"order": step["order"], "success": True}
                for step in resource["practice_guide"]["steps"]
            ],
            "subjective_difficulty": "appropriate",
        })
        assert premature.status_code == 409

        answer_key = await private_test_answers(resource_id)
        scored = await client.post(f"/api/v1/resources/{resource_id}/test", json={
            "answers": [
                {"item_id": item["id"], "answer": answer_key[item["id"]]}
                for item in resource["graded_test"]["items"]
            ],
        })
        assert scored.status_code == 200
        assert scored.json()["score"] == 1.0

        feedback = await client.post(f"/api/v1/resources/{resource_id}/feedback", json={
            "practice_results": [
                {"order": step["order"], "success": True}
                for step in resource["practice_guide"]["steps"]
            ],
            "subjective_difficulty": "appropriate",
            "error_tags": [],
        })
        assert feedback.status_code == 200
        assert feedback.json()["decision"] == "complete"
        assert feedback.json()["next_workflow_id"] is None

        reopened = (await client.get(f"/api/v1/resources/{resource_id}")).json()
        assert reopened["feedback_recorded"] is True
        assert reopened["feedback_decision"] == "complete"
        assert reopened["next_workflow_id"] is None


@pytest.mark.asyncio
async def test_all_c_practice_commands_execute_successfully():
    for skill in load_skill_nodes("c_programming"):
        with tempfile.TemporaryDirectory() as directory:
            for step in GenerationAgent._practice_steps("c_programming", skill["id"]):
                completed = subprocess.run(
                    ["bash", "-lc", step["command"]],
                    cwd=directory,
                    text=True,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                assert completed.returncode == 0, (
                    skill["id"], step["order"], completed.stdout, completed.stderr
                )
