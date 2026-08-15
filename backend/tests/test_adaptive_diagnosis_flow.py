"""End-to-end tests for the adaptive diagnosis API and its workflow handoff.

Three things are covered:

* the answer-driven loop itself (start -> answer -> ... -> result), including
  that it stops on its own rather than running the whole bank;
* the error surface, because a half-finished session must not be resumable into
  an inconsistent state;
* the workflow integration — 开始诊断 -> 动态出题 -> 更新学习者模型 -> 诊断完成 —
  and the read endpoints that expose the resulting posterior.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_smartlearn.db")
os.environ.setdefault("WORKFLOW_STEP_DELAY_SECONDS", "0")

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import init_db
from app.main import app
from app.services.information_gain_diagnosis_service import MAX_QUESTIONS, MIN_QUESTIONS
from app.services.learner_model_service import UNCERTAIN_THRESHOLD

DOMAIN = "ros2_robotics"
SKILL = "ros2_topic"

STOP_REASONS = {
    "max_questions_reached",
    "item_bank_exhausted",
    "posterior_confident",
    "information_gain_exhausted",
    "time_budget_exhausted",
}

# States a workflow may legitimately be in once diagnosis has handed back
# control. PUBLISHED/FAILED are both accepted: this test is about the handoff,
# not about whether downstream generation succeeds.
POST_DIAGNOSIS_STATES = {
    "PATH_PLANNING", "RETRIEVING", "GENERATING", "REVIEWING",
    "REVISING", "PUBLISHED", "FAILED",
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _new_learner(client: AsyncClient) -> str:
    response = await client.post("/api/v1/learners", json={
        "education": "本科", "major": "机械工程",
        "target_role": "ROS2移动机器人开发工程师", "weekly_hours": 6,
    })
    assert response.status_code == 201
    return response.json()["learner_id"]


def _bank_index() -> dict[str, dict]:
    from app.services.domain_package_service import load_assessment_bank

    return {str(item["id"]): item for item in load_assessment_bank(DOMAIN)}


def _answer_for(item_id: str, correct: bool) -> str:
    """Correct option, or a deliberately wrong one from the same item."""
    item = _bank_index()[item_id]
    key = str(item["correct_answer"])
    if correct:
        return key
    return next(
        (str(option["key"]) for option in item.get("options", []) if str(option["key"]) != key),
        key,
    )


async def _run_session(
    client: AsyncClient,
    session_id: str,
    first_item: dict,
    correct: bool = True,
) -> dict:
    """Answer items until the service decides to stop; returns the final payload."""
    item = first_item
    payload = None
    for _ in range(MAX_QUESTIONS + 5):
        assert item is not None, "session neither finished nor offered an item"
        response = await client.post(f"/api/v1/diagnosis/{session_id}/answer", json={
            "item_id": item["item_id"],
            "answer": _answer_for(item["item_id"], correct),
            "response_time_sec": 30.0,
        })
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["finished"]:
            return payload
        item = payload["next_item"]
    pytest.fail("adaptive session never stopped")


# ------------------------------------------------------------------ the loop


@pytest.mark.asyncio
async def test_adaptive_session_stops_on_its_own_and_reports_a_reason():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        start = await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })
        assert start.status_code == 201, start.text
        started = start.json()
        assert started["status"] == "in_progress"
        assert started["question_count"] == 0

        first = started["next_item"]
        assert first["skill_id"] == SKILL
        assert first["concept_ids"]
        assert first["options"]
        # The selection breakdown is surfaced so the choice is auditable.
        assert first["information_gain"] > 0
        assert first["question_index"] == 1

        final = await _run_session(client, started["session_id"], first)
        assert final["stop_reason"] in STOP_REASONS
        assert final["next_item"] is None
        # It neither stopped early nor ground through the entire bank.
        assert MIN_QUESTIONS <= final["question_count"] <= MAX_QUESTIONS

        result = final["result"]
        assert result["status"] == "completed"
        assert result["question_count"] == final["question_count"]
        assert result["accuracy"] == 1.0
        assert result["correct_count"] == result["question_count"]
        assert result["tested_concept_ids"]
        assert result["summary"].startswith("自适应诊断完成")
        assert len(result["item_results"]) == result["question_count"]
        assert all(row["is_correct"] for row in result["item_results"])


@pytest.mark.asyncio
async def test_each_answer_moves_the_posterior_and_never_repeats_an_item():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()

        seen: list[str] = []
        item = started["next_item"]
        while item is not None:
            seen.append(item["item_id"])
            payload = (await client.post(
                f"/api/v1/diagnosis/{started['session_id']}/answer",
                json={
                    "item_id": item["item_id"],
                    "answer": _answer_for(item["item_id"], correct=False),
                    "response_time_sec": 25.0,
                },
            )).json()
            assert payload["is_correct"] is False
            assert payload["correct_answer"]
            assert payload["explanation"]
            # A wrong answer must push every concept the item touches downward.
            assert payload["concept_deltas"]
            for delta in payload["concept_deltas"]:
                assert delta["mastery_after"] < delta["mastery_before"]
                assert delta["uncertainty_after"] < delta["uncertainty_before"]
            if payload["finished"]:
                break
            item = payload["next_item"]

        assert len(seen) == len(set(seen)), "an item was asked twice"

        result = (await client.get(
            f"/api/v1/diagnosis/{started['session_id']}/result"
        )).json()
        assert result["accuracy"] == 0.0
        assert result["overall_mastery"] < 0.5
        assert result["recommended_level"] == "basic"
        assert result["weak_concepts"]
        assert result["knowledge_gaps"]
        # Wrong answers on tagged items surface the misconceptions behind them.
        assert result["misconceptions"]


@pytest.mark.asyncio
async def test_next_endpoint_is_idempotent_and_survives_a_lost_response():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()
        session_id = started["session_id"]

        first = (await client.get(f"/api/v1/diagnosis/{session_id}/next")).json()
        again = (await client.get(f"/api/v1/diagnosis/{session_id}/next")).json()
        assert first["finished"] is False
        # Re-deriving the pending item reserves nothing, so it must not change.
        assert first["next_item"]["item_id"] == again["next_item"]["item_id"]
        assert first["question_count"] == again["question_count"] == 0
        # ...and it agrees with what /start already handed out.
        assert first["next_item"]["item_id"] == started["next_item"]["item_id"]

        await _run_session(client, session_id, first["next_item"])

        # Once finished, /next reports the terminal state rather than an item.
        closed = (await client.get(f"/api/v1/diagnosis/{session_id}/next")).json()
        assert closed["finished"] is True
        assert closed["stop_reason"] in STOP_REASONS
        assert closed.get("next_item") is None


@pytest.mark.asyncio
async def test_session_state_endpoint_tracks_progress_and_fatigue():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()
        session_id = started["session_id"]

        item = started["next_item"]
        await client.post(f"/api/v1/diagnosis/{session_id}/answer", json={
            "item_id": item["item_id"],
            "answer": _answer_for(item["item_id"], correct=True),
            "response_time_sec": 40.0,
        })

        state = (await client.get(f"/api/v1/diagnosis/{session_id}")).json()
        assert state["status"] == "in_progress"
        assert state["question_count"] == 1
        assert state["answered_item_ids"] == [item["item_id"]]
        assert set(state["tested_concept_ids"]) == set(item["concept_ids"])
        assert state["fatigue_state"]["elapsed_seconds"] == pytest.approx(40.0)
        assert state["target_skill_id"] == SKILL


# --------------------------------------------------------------- error surface


@pytest.mark.asyncio
async def test_invalid_requests_are_rejected_rather_than_silently_accepted():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)

        assert (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": "learner_does_not_exist", "domain_id": DOMAIN,
        })).status_code == 404
        assert (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": "c_pointer",
        })).status_code == 422
        assert (await client.get("/api/v1/diagnosis/sess_missing")).status_code == 404
        assert (await client.get("/api/v1/diagnosis/sess_missing/next")).status_code == 404

        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()
        session_id = started["session_id"]
        item_id = started["next_item"]["item_id"]

        unknown_item = await client.post(f"/api/v1/diagnosis/{session_id}/answer", json={
            "item_id": "ros_q_999", "answer": "A",
        })
        assert unknown_item.status_code == 404

        bad_option = await client.post(f"/api/v1/diagnosis/{session_id}/answer", json={
            "item_id": item_id, "answer": "Z",
        })
        assert bad_option.status_code == 422

        accepted = await client.post(f"/api/v1/diagnosis/{session_id}/answer", json={
            "item_id": item_id, "answer": _answer_for(item_id, correct=True).lower(),
        })
        assert accepted.status_code == 200  # option keys are case-insensitive

        duplicate = await client.post(f"/api/v1/diagnosis/{session_id}/answer", json={
            "item_id": item_id, "answer": _answer_for(item_id, correct=True),
        })
        assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_a_finished_session_refuses_further_answers():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()
        final = await _run_session(client, started["session_id"], started["next_item"])
        assert final["finished"] is True

        # Any unasked item will do: the finished session must be refused before
        # the item is even looked up. A focused run can consume its whole skill,
        # so this deliberately does not restrict itself to SKILL.
        asked = {row["item_id"] for row in final["result"]["item_results"]}
        leftover = next(item_id for item_id in _bank_index() if item_id not in asked)
        late = await client.post(f"/api/v1/diagnosis/{started['session_id']}/answer", json={
            "item_id": leftover, "answer": _answer_for(leftover, correct=True),
        })
        assert late.status_code == 409


# ---------------------------------------------------------- workflow handoff


@pytest.mark.asyncio
async def test_adaptive_workflow_waits_for_the_diagnosis_session_then_resumes():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        workflow_id = (await client.post("/api/v1/workflows", json={
            "learner_id": learner_id, "domain_id": DOMAIN,
            "target_goal": "掌握ROS2 Topic通信", "target_skill_id": SKILL,
            "diagnosis_mode": "adaptive",
        })).json()["workflow_id"]

        # 开始诊断: the workflow parks instead of running straight through.
        parked = (await client.get(f"/api/v1/workflows/{workflow_id}")).json()
        assert parked["status"] == "DIAGNOSIS_QUESTIONING"

        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN,
            "target_skill_id": SKILL, "workflow_id": workflow_id,
        })).json()
        assert started["workflow_id"] == workflow_id

        # 动态出题 -> 更新学习者模型 -> 动态出题 (the adaptive loop).
        item = started["next_item"]
        payload = (await client.post(
            f"/api/v1/diagnosis/{started['session_id']}/answer",
            json={
                "item_id": item["item_id"],
                "answer": _answer_for(item["item_id"], correct=True),
                "response_time_sec": 30.0,
            },
        )).json()
        assert payload["finished"] is False
        mid = (await client.get(f"/api/v1/workflows/{workflow_id}")).json()
        assert mid["status"] == "DIAGNOSIS_QUESTIONING"

        final = await _run_session(client, started["session_id"], payload["next_item"])
        assert final["finished"] is True

        # 诊断完成: control returns to the workflow, which moves on by itself.
        resumed = (await client.get(f"/api/v1/workflows/{workflow_id}")).json()
        assert resumed["status"] in POST_DIAGNOSIS_STATES | {"DIAGNOSIS_COMPLETED"}

        snapshot = (await client.get(f"/api/v1/workflows/{workflow_id}/snapshot")).json()
        learner = snapshot["learner"]
        assert learner is not None
        assert learner["diagnosis_session_id"] == started["session_id"]
        summary = learner["mastery_summary"]
        assert summary["tested_concept_count"] > 0
        assert SKILL in summary["skill_mastery"]
        assert summary["skill_mastery"][SKILL] > 0.5  # answered everything correctly
        assert learner["learner_state"]["learner_id"] == learner_id


@pytest.mark.asyncio
async def test_start_validates_the_linked_workflow():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        other_id = await _new_learner(client)
        workflow_id = (await client.post("/api/v1/workflows", json={
            "learner_id": other_id, "domain_id": DOMAIN,
            "target_goal": "掌握ROS2 Topic通信", "diagnosis_mode": "adaptive",
        })).json()["workflow_id"]

        missing = await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "workflow_id": "wf_missing",
        })
        assert missing.status_code == 404

        mismatched = await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "workflow_id": workflow_id,
        })
        assert mismatched.status_code == 422


@pytest.mark.asyncio
async def test_a_standalone_session_never_fails_for_lack_of_a_workflow():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()
        assert started["workflow_id"] is None
        final = await _run_session(client, started["session_id"], started["next_item"])
        assert final["finished"] is True


# -------------------------------------------------------- learner-model views


@pytest.mark.asyncio
async def test_diagnosis_feeds_the_learner_mastery_endpoints():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        started = (await client.post("/api/v1/diagnosis/start", json={
            "learner_id": learner_id, "domain_id": DOMAIN, "target_skill_id": SKILL,
        })).json()
        await _run_session(client, started["session_id"], started["next_item"], correct=False)

        mastery = (await client.get(
            f"/api/v1/learners/{learner_id}/mastery",
            params={"domain_id": DOMAIN, "skill_id": SKILL, "tested_only": True},
        )).json()
        assert mastery["concept_states"]
        assert all(state["attempt_count"] > 0 for state in mastery["concept_states"])
        assert [state["skill_id"] for state in mastery["skill_states"]] == [SKILL]

        weak = (await client.get(
            f"/api/v1/learners/{learner_id}/weak-concepts",
            params={"domain_id": DOMAIN, "skill_id": SKILL, "limit": 3},
        )).json()
        assert 0 < len(weak["weak_concepts"]) <= 3
        probabilities = [state["mastery_probability"] for state in weak["weak_concepts"]]
        assert probabilities == sorted(probabilities)  # weakest first

        profile = (await client.get(
            f"/api/v1/learners/{learner_id}/ability-profile",
            params={"domain_id": DOMAIN},
        )).json()
        assert profile["tested_concept_count"] > 0
        assert profile["recommended_level"] == "basic"
        assert len(profile["skill_states"]) == 10
        assert all(
            state["uncertainty"] <= 1.0 for state in profile["uncertain_concepts"]
        )
        assert all(
            state["uncertainty"] > UNCERTAIN_THRESHOLD
            for state in profile["uncertain_concepts"]
        )

        # The finished diagnosis is cached on the profile for the app to read.
        detail = (await client.get(f"/api/v1/learners/{learner_id}")).json()
        assert detail["last_diagnosed_at"] is not None
        assert detail["uncertainty"] is not None
        assert detail["ability_profile"]["domain_id"] == DOMAIN
        assert detail["misconceptions"]


@pytest.mark.asyncio
async def test_mastery_endpoints_reject_unknown_learners_and_skills():
    await init_db()
    async with _client() as client:
        learner_id = await _new_learner(client)
        assert (await client.get(
            "/api/v1/learners/learner_missing/ability-profile"
        )).status_code == 404
        assert (await client.get(
            f"/api/v1/learners/{learner_id}/mastery",
            params={"domain_id": DOMAIN, "skill_id": "c_pointer"},
        )).status_code == 404
