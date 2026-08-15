import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_smartlearn.db"
os.environ["WORKFLOW_STEP_DELAY_SECONDS"] = "0"

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.generation_agent import GenerationAgent
from app.core.database import init_db
from app.main import app
from app.workflow.state import WorkflowState


@pytest.mark.asyncio
async def test_c_report_and_assessment_review_are_domain_correct():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        learner = (await client.post("/api/v1/learners", json={
            "education": "本科", "major": "计算机", "target_role": "C开发工程师",
        })).json()
        learner_id = learner["learner_id"]
        assessment = (await client.post("/api/v1/assessments", json={
            "learner_id": learner_id,
            "domain_id": "c_programming",
            "target_goal": "掌握C语言基础与指针",
        })).json()
        response = await client.post(
            f"/api/v1/assessments/{assessment['assessment_id']}/submit",
            json={
                "answers": [{
                    "item_id": item["item_id"],
                    "answer": "A",
                    "duration_seconds": 15,
                } for item in assessment["items"]],
                "practice_results": [],
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert len(result["item_results"]) == len(assessment["items"])
        assert all("correct_answer" in item and "explanation" in item for item in result["item_results"])

        report = (await client.get(f"/api/v1/learners/{learner_id}/report")).json()
        assert report["domain"] == "c_programming"
        assert report["learning_path"]
        assert all(item["skill_id"].startswith("c_") for item in report["learning_path"])


@pytest.mark.asyncio
async def test_generation_revision_changes_actual_resource_content():
    context = WorkflowState(
        workflow_id="wf_regression",
        learner_id="learner_regression",
        domain_id="ros2_robotics",
        target_skills=["linux_environment", "ros2_node", "ros2_topic"],
        evidence_list=[
            {"evidence_id": "ev_001", "source_url": "https://docs.ros.org/1"},
            {"evidence_id": "ev_002", "source_url": "https://docs.ros.org/2"},
            {"evidence_id": "ev_003", "source_url": "https://docs.ros.org/3"},
        ],
        revision_count=1,
    )
    agent = GenerationAgent()
    original = await agent.run(context, {})
    revised = await agent.run(context, {
        "revision_instructions": ["讲义章节没有证据引用", "缺少安全提示"],
    })

    original_sections = original.output["resources"]["lecture"]["sections"]
    revised_sections = revised.output["resources"]["lecture"]["sections"]
    assert revised_sections != original_sections
    assert len(revised_sections) == len(original_sections) + 1
    assert "审核修订" in revised_sections[-1]["heading"]
    assert revised.output["metadata"]["revision_instructions_applied"]
    assert revised.output["metadata"]["model_version"] == "domain-driven-generator-v3"
