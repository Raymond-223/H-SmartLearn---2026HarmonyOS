"""Unit tests for information-gain item selection.

The four objective terms are tested as pure functions against hand-built
posteriors — no database, no LLM — because their whole point is that they are
auditable. Candidate filtering, ranking and the stop rule are then tested
against the real packaged ROS2 bank so a change to the domain package that
breaks selection shows up here rather than in an end-to-end run.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_smartlearn.db")
os.environ.setdefault("WORKFLOW_STEP_DELAY_SECONDS", "0")

import pytest

from app.core.database import async_session_factory, init_db
from app.models.learner import LearnerProfile
from app.services.information_gain_diagnosis_service import (
    COVERAGE_WEIGHT,
    FATIGUE_WEIGHT,
    MAX_QUESTIONS,
    MAX_SESSION_SECONDS,
    MIN_GAIN_TO_CONTINUE,
    MIN_QUESTIONS,
    TIME_WEIGHT,
    CandidateScore,
    InformationGainDiagnosisService,
    SessionContext,
    item_concept_ids,
    item_estimated_time,
)
from app.services.learner_model_service import ConceptState, LearnerModelService

DOMAIN = "ros2_robotics"
TOPIC_CONCEPTS = [f"concept_ros2_topic_0{index}" for index in range(1, 6)]


def _service(db=None) -> InformationGainDiagnosisService:
    """Selector wired to a learner model; ``db`` is only needed for async paths."""
    return InformationGainDiagnosisService(LearnerModelService(db, domain_id=DOMAIN))


def _state(concept_id: str, alpha: float, beta: float, attempts: int = 0) -> ConceptState:
    from app.services.learner_model_service import beta_mean, normalized_uncertainty

    return ConceptState(
        concept_id=concept_id,
        skill_id="ros2_topic",
        alpha=alpha,
        beta=beta,
        mastery_probability=beta_mean(alpha, beta),
        uncertainty=normalized_uncertainty(alpha, beta),
        attempt_count=attempts,
    )


def _item(**overrides) -> dict:
    item = {
        "id": "synthetic_001",
        "skill_id": "ros2_topic",
        "concept_ids": [TOPIC_CONCEPTS[0]],
        "difficulty": 3,
        "estimated_time_sec": 45,
        "importance": 3,
    }
    item.update(overrides)
    return item


async def _new_learner() -> str:
    await init_db()
    async with async_session_factory() as db:
        profile = LearnerProfile(
            education="本科", major="自动化",
            target_role="ROS2移动机器人开发工程师", weekly_hours=6,
        )
        db.add(profile)
        await db.commit()
        return profile.id


# --------------------------------------------------------- information gain


def test_gain_is_normalised_into_unit_scale_at_the_prior():
    """A fresh concept must read close to 1.0, not 1/12 of it.

    The objective adds coverage/time/fatigue terms that all live on a unit
    scale; if gain were left in raw variance units it would be swamped.
    """
    service = _service()
    gain = service.calculate_information_gain(
        _item(), {TOPIC_CONCEPTS[0]: _state(TOPIC_CONCEPTS[0], 1.0, 1.0)}
    )
    assert 0.0 < gain <= 1.0
    assert gain > 0.3


def test_gain_collapses_once_the_posterior_is_confident():
    service = _service()
    unknown = service.calculate_information_gain(
        _item(), {TOPIC_CONCEPTS[0]: _state(TOPIC_CONCEPTS[0], 1.0, 1.0)}
    )
    mastered = service.calculate_information_gain(
        _item(), {TOPIC_CONCEPTS[0]: _state(TOPIC_CONCEPTS[0], 30.0, 2.0, attempts=30)}
    )
    failed = service.calculate_information_gain(
        _item(), {TOPIC_CONCEPTS[0]: _state(TOPIC_CONCEPTS[0], 2.0, 30.0, attempts=30)}
    )
    assert mastered < unknown
    assert failed < unknown
    # Confident either way => not worth asking again.
    assert mastered < MIN_GAIN_TO_CONTINUE
    assert failed < MIN_GAIN_TO_CONTINUE


def test_gain_is_averaged_so_broad_items_do_not_win_by_breadth_alone():
    service = _service()
    states = {cid: _state(cid, 1.0, 1.0) for cid in TOPIC_CONCEPTS}
    narrow = service.calculate_information_gain(_item(concept_ids=TOPIC_CONCEPTS[:1]), states)
    broad = service.calculate_information_gain(_item(concept_ids=TOPIC_CONCEPTS), states)
    assert broad < narrow


def test_gain_is_zero_when_the_item_maps_to_no_known_concept():
    service = _service()
    assert service.calculate_information_gain(
        _item(concept_ids=[], skill_id="no_such_skill"), {}
    ) == 0.0
    # Concepts with no state contribute nothing rather than raising.
    assert service.calculate_information_gain(_item(), {}) == 0.0


def test_item_concept_ids_falls_back_to_the_skill_for_legacy_items():
    service = _service()
    legacy = {"id": "legacy", "skill_id": "ros2_topic"}
    assert sorted(item_concept_ids(legacy, service.concept_index)) == sorted(TOPIC_CONCEPTS)
    # Unknown concept ids are dropped, not trusted.
    mixed = {"id": "mixed", "skill_id": "ros2_topic", "concept_ids": ["nope"]}
    assert sorted(item_concept_ids(mixed, service.concept_index)) == sorted(TOPIC_CONCEPTS)


# ---------------------------------------------------- coverage / time / fatigue


def test_coverage_gain_falls_to_zero_once_the_concepts_were_probed():
    service = _service()
    states = {cid: _state(cid, 1.0, 1.0) for cid in TOPIC_CONCEPTS}
    item = _item(concept_ids=TOPIC_CONCEPTS[:2])

    fresh = service.calculate_coverage_gain(item, SessionContext(), states)
    half = service.calculate_coverage_gain(
        item, SessionContext(tested_concept_ids=[TOPIC_CONCEPTS[0]]), states
    )
    done = service.calculate_coverage_gain(
        item, SessionContext(tested_concept_ids=TOPIC_CONCEPTS[:2]), states
    )
    assert fresh > half > done == 0.0


def test_coverage_gain_favours_concepts_with_no_history_at_all():
    service = _service()
    concept_id = TOPIC_CONCEPTS[0]
    item = _item(concept_ids=[concept_id])
    never_seen = service.calculate_coverage_gain(
        item, SessionContext(), {concept_id: _state(concept_id, 1.0, 1.0, attempts=0)}
    )
    seen_before = service.calculate_coverage_gain(
        item, SessionContext(), {concept_id: _state(concept_id, 3.0, 2.0, attempts=4)}
    )
    assert never_seen > seen_before


def test_time_cost_is_relative_to_the_bank_median_and_capped():
    service = _service()
    median = service.median_time
    assert service.calculate_time_cost(_item(estimated_time_sec=median)) == pytest.approx(1.0)
    assert service.calculate_time_cost(_item(estimated_time_sec=median / 3)) < 1.0
    assert service.calculate_time_cost(_item(estimated_time_sec=median * 50)) == 3.0


def test_estimated_time_falls_back_when_the_item_has_no_usable_value():
    from app.services.information_gain_diagnosis_service import DEFAULT_ESTIMATED_TIME

    assert item_estimated_time({"estimated_time_sec": 30}) == 30.0
    assert item_estimated_time({"estimated_seconds": 90}) == 90.0
    assert item_estimated_time({}) == DEFAULT_ESTIMATED_TIME
    assert item_estimated_time({"estimated_time_sec": 0}) == DEFAULT_ESTIMATED_TIME
    assert item_estimated_time({"estimated_time_sec": "abc"}) == DEFAULT_ESTIMATED_TIME


def test_fatigue_grows_with_session_length_hard_streaks_and_elapsed_time():
    service = _service()
    easy = _item(difficulty=2)
    hard = _item(difficulty=5)

    assert service.calculate_fatigue(easy, SessionContext(question_count=0)) == 0.0
    assert (
        service.calculate_fatigue(easy, SessionContext(question_count=MAX_QUESTIONS))
        > service.calculate_fatigue(easy, SessionContext(question_count=MIN_QUESTIONS))
    )
    # A run of hard items penalises the next hard item, not the next easy one.
    streak = SessionContext(consecutive_hard=3)
    assert service.calculate_fatigue(hard, streak) > service.calculate_fatigue(hard, SessionContext())
    assert service.calculate_fatigue(easy, streak) == service.calculate_fatigue(easy, SessionContext())
    # Wall-clock fatigue saturates rather than growing without bound.
    long_run = SessionContext(elapsed_seconds=MAX_SESSION_SECONDS * 5)
    assert service.calculate_fatigue(easy, long_run) == pytest.approx(1.0)


# ------------------------------------------------------------ candidate pool


def test_answered_items_are_never_offered_again():
    service = _service()
    first = service.get_candidate_items(SessionContext())
    assert len(first) == len(service.bank)

    answered = [str(item["id"]) for item in first[:5]]
    remaining = service.get_candidate_items(SessionContext(answered_item_ids=answered))
    assert len(remaining) == len(first) - 5
    assert not {str(item["id"]) for item in remaining} & set(answered)


def test_a_focused_session_only_draws_from_its_target_skill():
    service = _service()
    candidates = service.get_candidate_items(SessionContext(target_skill_id="ros2_topic"))
    assert candidates
    assert {item["skill_id"] for item in candidates} == {"ros2_topic"}


def test_scope_widens_to_prerequisites_only_below_the_question_floor():
    """Running out of tf2 items early is worth a prerequisite probe; later it is not."""
    service = _service()
    assert service.prerequisite_skills({"ros2_tf2"}) == {
        "ros2_topic", "ros2_node", "linux_environment",
    }

    exhausted = [
        str(item["id"]) for item in service.bank if item.get("skill_id") == "ros2_tf2"
    ]
    early = service.get_candidate_items(SessionContext(
        answered_item_ids=exhausted, question_count=2, target_skill_id="ros2_tf2",
    ))
    assert early
    assert {item["skill_id"] for item in early} <= {"ros2_topic", "ros2_node", "linux_environment"}

    late = service.get_candidate_items(SessionContext(
        answered_item_ids=exhausted, question_count=MIN_QUESTIONS, target_skill_id="ros2_tf2",
    ))
    assert late == []  # session ends instead of quietly becoming a general survey


def test_explicit_skill_scope_overrides_the_session_target():
    service = _service()
    candidates = service.get_candidate_items(
        SessionContext(target_skill_id="ros2_tf2"), skill_ids=["ros2_slam"]
    )
    assert {item["skill_id"] for item in candidates} == {"ros2_slam"}


# --------------------------------------------------------- ranking & stopping


@pytest.mark.asyncio
async def test_ranking_is_deterministic_and_matches_the_objective():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = _service(db)
        await service.learner_model.initialize_learner(learner_id)
        await db.commit()

        context = SessionContext(target_skill_id="ros2_topic")
        scored = await service.score_candidates(learner_id, context)
        assert len(scored) == 12

        # The stored total is exactly the documented objective.
        for row in scored:
            expected = (
                row.information_gain
                + COVERAGE_WEIGHT * row.coverage_gain
                - TIME_WEIGHT * row.time_cost
                - FATIGUE_WEIGHT * row.fatigue
            )
            assert row.total_score == pytest.approx(expected)

        assert [row.total_score for row in scored] == sorted(
            (row.total_score for row in scored), reverse=True
        )
        # Same state in, same item out — selection must be reproducible.
        again = await service.score_candidates(learner_id, context)
        assert [row.item_id for row in again] == [row.item_id for row in scored]
        best = await service.select_next_item(learner_id, context)
        assert best.item_id == scored[0].item_id


@pytest.mark.asyncio
async def test_selection_moves_on_once_a_concept_is_well_evidenced():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = _service(db)
        model = service.learner_model
        await model.initialize_learner(learner_id)

        context = SessionContext(target_skill_id="ros2_topic")
        first = await service.select_next_item(learner_id, context)
        for _ in range(10):
            await model.update_from_answer(
                learner_id, first.concept_ids, is_correct=True, difficulty=5
            )
        await db.commit()

        context.answered_item_ids = [first.item_id]
        context.tested_concept_ids = list(first.concept_ids)
        context.question_count = 1
        second = await service.select_next_item(learner_id, context)
        assert second is not None
        assert second.item_id != first.item_id
        # The now-settled concepts are no longer what the session is chasing.
        assert not set(second.concept_ids) <= set(first.concept_ids)


@pytest.mark.asyncio
async def test_stop_rule_honours_the_question_floor_and_ceiling():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = _service(db)
        await service.learner_model.initialize_learner(learner_id)
        await db.commit()

        stop, reason = await service.should_stop(
            learner_id, SessionContext(question_count=MAX_QUESTIONS)
        )
        assert (stop, reason) == (True, "max_questions_reached")

        # Below the floor the session continues even if the next item is dull.
        dull = CandidateScore(
            item_id="dull", skill_id="ros2_topic", concept_ids=[TOPIC_CONCEPTS[0]],
            difficulty=1, estimated_time_sec=45.0, information_gain=0.0,
            coverage_gain=0.0, time_cost=1.0, fatigue=0.0, total_score=-0.15,
        )
        stop, reason = await service.should_stop(
            learner_id, SessionContext(question_count=1), next_candidate=dull
        )
        assert (stop, reason) == (False, "min_questions_not_reached")

        # Past the floor, the same dull item ends the session.
        stop, reason = await service.should_stop(
            learner_id, SessionContext(question_count=MIN_QUESTIONS), next_candidate=dull
        )
        assert (stop, reason) == (True, "information_gain_exhausted")


@pytest.mark.asyncio
async def test_stop_rule_reports_an_exhausted_bank():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = _service(db)
        await service.learner_model.initialize_learner(learner_id)
        await db.commit()

        context = SessionContext(
            answered_item_ids=[str(item["id"]) for item in service.bank],
            question_count=MIN_QUESTIONS,
        )
        assert await service.select_next_item(learner_id, context) is None
        assert await service.should_stop(learner_id, context) == (True, "item_bank_exhausted")


@pytest.mark.asyncio
async def test_stop_rule_ends_a_confident_session_before_the_ceiling():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = _service(db)
        model = service.learner_model
        await model.initialize_learner(learner_id)
        for concept_id in TOPIC_CONCEPTS:
            for _ in range(20):
                await model.update_from_answer(
                    learner_id, [concept_id], is_correct=True, difficulty=3
                )
        await db.commit()

        context = SessionContext(
            question_count=MIN_QUESTIONS + 1,
            tested_concept_ids=list(TOPIC_CONCEPTS),
            target_skill_id="ros2_topic",
        )
        stop, reason = await service.should_stop(learner_id, context)
        assert stop is True
        assert reason == "posterior_confident"


@pytest.mark.asyncio
async def test_stop_rule_respects_the_time_budget():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = _service(db)
        await service.learner_model.initialize_learner(learner_id)
        await db.commit()

        interesting = CandidateScore(
            item_id="interesting", skill_id="ros2_topic", concept_ids=[TOPIC_CONCEPTS[0]],
            difficulty=3, estimated_time_sec=45.0, information_gain=0.9,
            coverage_gain=1.0, time_cost=1.0, fatigue=0.0, total_score=1.0,
        )
        context = SessionContext(
            question_count=MIN_QUESTIONS + 1,
            tested_concept_ids=[TOPIC_CONCEPTS[0]],
            elapsed_seconds=MAX_SESSION_SECONDS + 1,
        )
        stop, reason = await service.should_stop(
            learner_id, context, next_candidate=interesting
        )
        assert (stop, reason) == (True, "time_budget_exhausted")
