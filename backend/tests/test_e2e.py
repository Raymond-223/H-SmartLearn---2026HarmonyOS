import asyncio
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_smartlearn.db"
os.environ["WORKFLOW_STEP_DELAY_SECONDS"] = "0"

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.resource import GeneratedResource
from app.core.database import init_db, async_session_factory


async def private_test_answers(resource_id: str) -> dict[str, str]:
    async with async_session_factory() as db:
        resource = await db.get(GeneratedResource, resource_id)
        items = (resource.content_json or {})["resources"]["graded_test"]["items"]
        return {str(item["id"]): str(item["correct_answer"]) for item in items}


@pytest.mark.asyncio
async def test_complete_learning_loop():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        learner = (await client.post("/api/v1/learners", json={
            "education": "本科", "major": "机械工程",
            "target_role": "ROS2移动机器人开发工程师", "weekly_hours": 6,
        })).json()
        learner_id = learner["learner_id"]

        assessment = (await client.post("/api/v1/assessments", json={
            "learner_id": learner_id, "domain_id": "ros2_robotics",
            "target_goal": "掌握ROS2 Topic通信",
        })).json()
        assert len(assessment["items"]) == 10
        ros_answers = {
            "ros_q_001": "A", "ros_q_002": "A", "ros_q_003": "A", "ros_q_004": "B",
            "ros_q_005": "B", "ros_q_006": "B", "ros_q_007": "A", "ros_q_008": "A",
            "ros_q_009": "A", "ros_q_010": "A",
        }
        answers = [{
            "item_id": item["item_id"],
            "answer": ros_answers[item["item_id"]],
            "duration_seconds": 20,
        } for item in assessment["items"]]
        partial = await client.post(
            f"/api/v1/assessments/{assessment['assessment_id']}/submit",
            json={"answers": answers[:-1]},
        )
        assert partial.status_code == 422
        fake_practice = await client.post(
            f"/api/v1/assessments/{assessment['assessment_id']}/submit",
            json={"answers": answers, "practice_results": [{"task_id": "fake", "score": 1.0}]},
        )
        assert fake_practice.status_code == 422
        submit = (await client.post(
            f"/api/v1/assessments/{assessment['assessment_id']}/submit",
            json={"answers": answers},
        )).json()
        assert submit["status"] == "completed"

        workflow = (await client.post("/api/v1/workflows", json={
            "learner_id": learner_id, "domain_id": "ros2_robotics",
            "assessment_id": assessment["assessment_id"],
            "target_goal": "掌握ROS2 Topic通信",
        })).json()
        workflow_id = workflow["workflow_id"]

        resource_id = None
        for _ in range(60):
            status = (await client.get(f"/api/v1/workflows/{workflow_id}")).json()
            if status["status"] == "PUBLISHED":
                resource_id = status["resource_id"]
                break
            if status["status"] == "FAILED":
                pytest.fail(status.get("error_message", "workflow failed"))
            await asyncio.sleep(0.05)
        assert resource_id

        resource = (await client.get(f"/api/v1/resources/{resource_id}")).json()
        assert resource["lecture"] and resource["practice_guide"] and resource["graded_test"]
        assert resource["citations"]

        test_items = resource["graded_test"]["items"]
        assert all("correct_answer" not in item and "explanation" not in item for item in test_items)
        answer_key = await private_test_answers(resource_id)
        test_response = await client.post(f"/api/v1/resources/{resource_id}/test", json={
            "answers": [{"item_id": item["id"], "answer": answer_key[item["id"]]} for item in test_items],
        })
        assert test_response.status_code == 200
        assert test_response.json()["score"] == 1.0

        feedback = await client.post(f"/api/v1/resources/{resource_id}/feedback", json={
            "correct_rate": 0.0,
            "practice_score": 0.0,
            "practice_results": [
                {"order": step["order"], "success": True}
                for step in resource["practice_guide"]["steps"]
            ],
            "subjective_difficulty": "too_hard",
            "error_tags": ["qos", "command_usage"],
        })
        assert feedback.status_code == 200
        assert feedback.json()["decision"] in {"lower_difficulty", "add_practice", "advance", "complete"}
        assert feedback.json()["next_workflow_id"]

        report = (await client.get(f"/api/v1/learners/{learner_id}/report")).json()
        assert report["skill_mastery"]
        assert len(report["difficulty_curve"]) == 3
        assert report["progress_history"]
        assert any(item["event_type"] == "resource_feedback" for item in report["progress_history"])

        c_graph = (await client.get("/api/v1/knowledge/graph?domain_id=c_programming")).json()
        assert len(c_graph["nodes"]) == 10

        c_assessment = (await client.post("/api/v1/assessments", json={
            "learner_id": learner_id, "domain_id": "c_programming",
            "target_goal": "掌握C语言基础与指针",
        })).json()
        assert len(c_assessment["items"]) == 10
        c_answers = {
            "c_q_001": "B", "c_q_002": "B", "c_q_003": "A", "c_q_004": "A",
            "c_q_005": "B", "c_q_006": "A", "c_q_007": "A", "c_q_008": "C",
            "c_q_009": "A", "c_q_010": "B",
        }
        await client.post(
            f"/api/v1/assessments/{c_assessment['assessment_id']}/submit",
            json={
                "answers": [{
                    "item_id": item["item_id"], "answer": c_answers[item["item_id"]],
                    "duration_seconds": 18,
                } for item in c_assessment["items"]],
            },
        )
        c_workflow = (await client.post("/api/v1/workflows", json={
            "learner_id": learner_id, "domain_id": "c_programming",
            "assessment_id": c_assessment["assessment_id"],
            "target_goal": "掌握C语言基础与指针",
        })).json()
        c_resource_id = None
        for _ in range(60):
            c_status = (await client.get(f"/api/v1/workflows/{c_workflow['workflow_id']}")).json()
            if c_status["status"] == "PUBLISHED":
                c_resource_id = c_status["resource_id"]
                break
            if c_status["status"] == "FAILED":
                pytest.fail(c_status.get("error_message", "C workflow failed"))
            await asyncio.sleep(0.05)
        assert c_resource_id
        c_resource = (await client.get(f"/api/v1/resources/{c_resource_id}")).json()
        assert c_resource["target_skill"] == "c_pointer"
        assert c_resource["lecture"]["title"].startswith("C语言")

        upload = await client.post(
            "/api/v1/admin/documents",
            data={"title": "C变量补充资料", "domain_id": "c_programming", "version": "C17"},
            files={"file": ("variables.md", "变量应先声明后使用。数组下标必须检查边界。", "text/markdown")},
        )
        assert upload.status_code == 201
        doc_id = upload.json()["document_id"]
        parsed = await client.post(f"/api/v1/admin/documents/{doc_id}/parse?skill_id=c_variable")
        assert parsed.json()["chunks"] >= 1
        verified = await client.post(f"/api/v1/admin/documents/{doc_id}/verify")
        assert verified.json()["status"] == "verified"
        search = (await client.get("/api/v1/admin/knowledge/search", params={
            "q": "变量", "domain_id": "c_programming",
        })).json()
        assert search["results"]

        from app.agents.retrieval_agent import RetrievalAgent
        from app.workflow.state import WorkflowState
        retrieval_context = WorkflowState(
            workflow_id="admin_retrieval", learner_id=learner_id, domain_id="c_programming",
            target_goal="掌握变量", target_skills=["c_variable"], source_skill_id="c_variable",
        )
        retrieved = await RetrievalAgent().run(retrieval_context, {})
        assert any(item["title"] == "C变量补充资料" for item in retrieved.output["evidence_list"])



@pytest.mark.asyncio
async def test_competition_benchmark_summary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/benchmarks/summary")
        assert response.status_code == 200
        payload = response.json()
        assert payload["case_count"] >= 50
        assert payload["profile_count"] >= 3
        assert payload["metrics"]["hallucination_rate"] < 5
        assert payload["metrics"]["difficulty_match_accuracy"] >= 85
        assert payload["metrics"]["core_knowledge_coverage"] >= 90
        assert "60个领域技能×画像组合" in payload["disclaimer"]
        assert payload["metrics"]["review_pass_rate"] >= 95
