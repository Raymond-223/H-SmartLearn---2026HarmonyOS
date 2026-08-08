"""Unit tests for the Beta-Bernoulli learner model.

Two layers are covered separately:

* the pure weighting/posterior functions, which need no database at all;
* ``LearnerModelService`` itself, which persists one row per concept.

Every assertion is about a property the rest of the system relies on (an unseen
concept reads as *unknown* rather than *weak*, evidence never resets, a
multi-concept item is not counted as several observations), not about exact
floating-point values that would break on any re-tuning of the constants.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_smartlearn.db")
os.environ.setdefault("WORKFLOW_STEP_DELAY_SECONDS", "0")

import pytest

from app.core.database import async_session_factory, init_db
from app.models.learner import LearnerProfile
from app.services.learner_model_service import (
    PRIOR_ALPHA,
    PRIOR_BETA,
    UNCERTAIN_THRESHOLD,
    WEAK_MASTERY_THRESHOLD,
    LearnerModelService,
    beta_mean,
    beta_variance,
    difficulty_weight,
    normalized_uncertainty,
    response_time_weight,
)

DOMAIN = "ros2_robotics"
SKILL = "ros2_topic"
CONCEPTS = [f"concept_ros2_topic_0{index}" for index in range(1, 6)]


async def _new_learner() -> str:
    """A committed learner row — concept mastery has an FK to learner_profiles."""
    await init_db()
    async with async_session_factory() as db:
        profile = LearnerProfile(
            education="本科",
            major="机械工程",
            target_role="ROS2移动机器人开发工程师",
            weekly_hours=6,
        )
        db.add(profile)
        await db.commit()
        return profile.id


# ------------------------------------------------------------- pure functions


def test_prior_reads_as_unknown_not_as_failure():
    """Beta(1,1) must mean "no idea", not "learner is at 50%"."""
    assert beta_mean(PRIOR_ALPHA, PRIOR_BETA) == 0.5
    assert normalized_uncertainty(PRIOR_ALPHA, PRIOR_BETA) == pytest.approx(1.0)
    # And uncertainty is capped, never above the prior.
    assert normalized_uncertainty(0.5, 0.5) <= 1.0


def test_variance_shrinks_as_evidence_accumulates():
    strong = beta_variance(20.0, 20.0)
    weak = beta_variance(PRIOR_ALPHA, PRIOR_BETA)
    assert strong < weak
    assert normalized_uncertainty(20.0, 20.0) < 0.1


def test_difficulty_weight_rewards_hard_success_and_punishes_easy_failure():
    # Correct: harder item => stronger evidence of mastery.
    assert difficulty_weight(5, True) > difficulty_weight(3, True) > difficulty_weight(1, True)
    # Incorrect: easier item => stronger evidence of a gap.
    assert difficulty_weight(1, False) > difficulty_weight(3, False) > difficulty_weight(5, False)
    # Out-of-range difficulties are clamped rather than extrapolated.
    assert difficulty_weight(99, True) == difficulty_weight(5, True)
    assert difficulty_weight(0, True) == difficulty_weight(1, True)
    assert difficulty_weight(None, True) == difficulty_weight(3, True)


def test_response_time_weight_discounts_only_suspiciously_fast_correct_answers():
    # 5s on a 60s item: likely a guess.
    assert response_time_weight(5.0, 60.0, True) == pytest.approx(0.5)
    # Normal pace: full weight.
    assert response_time_weight(50.0, 60.0, True) == 1.0
    # Between the two: ramps monotonically.
    partial = response_time_weight(0.4 * 60.0, 60.0, True)
    assert 0.5 < partial < 1.0
    # A fast wrong answer is still a wrong answer.
    assert response_time_weight(1.0, 60.0, False) == 1.0
    # Missing timing data must not silently discount anything.
    assert response_time_weight(None, 60.0, True) == 1.0
    assert response_time_weight(5.0, None, True) == 1.0


# ----------------------------------------------------------------- posteriors


@pytest.mark.asyncio
async def test_initialize_learner_is_idempotent_and_never_resets_evidence():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        first = await service.initialize_learner(learner_id, CONCEPTS)
        assert len(first) == len(CONCEPTS)
        assert all(state.attempt_count == 0 for state in first)
        assert all(state.mastery_probability == 0.5 for state in first)

        await service.update_from_answer(learner_id, [CONCEPTS[0]], is_correct=True, difficulty=4)
        await db.commit()

        # Re-running a diagnosis must not wipe what the last one learned.
        again = await service.initialize_learner(learner_id, CONCEPTS)
        await db.commit()
        touched = next(state for state in again if state.concept_id == CONCEPTS[0])
        assert touched.attempt_count == 1
        assert touched.mastery_probability > 0.5


@pytest.mark.asyncio
async def test_correct_and_incorrect_answers_move_the_posterior_in_opposite_directions():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id, CONCEPTS)

        up = (await service.update_from_answer(
            learner_id, [CONCEPTS[0]], is_correct=True, difficulty=3
        ))[0]
        down = (await service.update_from_answer(
            learner_id, [CONCEPTS[1]], is_correct=False, difficulty=3
        ))[0]
        await db.commit()

        assert up.mastery_probability > 0.5
        assert down.mastery_probability < 0.5
        # Either way the model is now *less* uncertain than the prior.
        assert up.uncertainty < 1.0
        assert down.uncertainty < 1.0
        assert (up.attempt_count, up.correct_count) == (1, 1)
        assert (down.attempt_count, down.correct_count) == (1, 0)


@pytest.mark.asyncio
async def test_repeated_consistent_evidence_drives_uncertainty_down():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id, CONCEPTS)

        uncertainties = []
        for _ in range(8):
            state = (await service.update_from_answer(
                learner_id, [CONCEPTS[0]], is_correct=True, difficulty=3
            ))[0]
            uncertainties.append(state.uncertainty)
        await db.commit()

        assert uncertainties == sorted(uncertainties, reverse=True)  # monotone decrease
        assert uncertainties[-1] < UNCERTAIN_THRESHOLD
        final = await service.get_concept_state(learner_id, CONCEPTS[0])
        assert final.mastery_probability > 0.8


@pytest.mark.asyncio
async def test_multi_concept_item_is_not_counted_as_several_observations():
    """One item covering three concepts must carry less per-concept weight."""
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id, CONCEPTS)

        single = (await service.update_from_answer(
            learner_id, [CONCEPTS[0]], is_correct=True, difficulty=3
        ))[0]
        shared = (await service.update_from_answer(
            learner_id, CONCEPTS[1:4], is_correct=True, difficulty=3
        ))[0]
        await db.commit()

        assert shared.mastery_probability < single.mastery_probability
        assert shared.mastery_probability > 0.5  # still evidence, just weaker


@pytest.mark.asyncio
async def test_unknown_concept_ids_are_ignored_rather_than_persisted():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        updated = await service.update_from_answer(
            learner_id, ["concept_does_not_exist"], is_correct=True, difficulty=3
        )
        await db.commit()
        assert updated == []


@pytest.mark.asyncio
async def test_untested_concept_is_unknown_not_weak():
    """The distinction the planner depends on: 0.5 prior != a measured gap."""
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id, CONCEPTS)
        await db.commit()

        assert await service.get_weak_concepts(learner_id) == []
        uncertain = await service.get_uncertain_concepts(learner_id, skill_id=SKILL)
        assert {state.concept_id for state in uncertain} == set(CONCEPTS)

        await service.update_from_answer(
            learner_id, [CONCEPTS[0]], is_correct=False, difficulty=1
        )
        await db.commit()
        weak = await service.get_weak_concepts(learner_id)
        assert [state.concept_id for state in weak] == [CONCEPTS[0]]
        assert weak[0].mastery_probability < WEAK_MASTERY_THRESHOLD


@pytest.mark.asyncio
async def test_weak_concepts_are_ordered_weakest_first_and_can_be_scoped():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id)

        for _ in range(3):
            await service.update_from_answer(learner_id, [CONCEPTS[0]], is_correct=False, difficulty=1)
        await service.update_from_answer(learner_id, [CONCEPTS[1]], is_correct=False, difficulty=1)
        # A different skill, so scoping has something to exclude.
        await service.update_from_answer(
            learner_id, ["concept_ros2_node_01"], is_correct=False, difficulty=1
        )
        await db.commit()

        ordered = await service.get_weak_concepts(learner_id)
        probabilities = [state.mastery_probability for state in ordered]
        assert probabilities == sorted(probabilities)
        assert ordered[0].concept_id == CONCEPTS[0]  # most evidence of failure

        scoped = await service.get_weak_concepts(learner_id, skill_id=SKILL)
        assert {state.concept_id for state in scoped} == {CONCEPTS[0], CONCEPTS[1]}
        assert len(await service.get_weak_concepts(learner_id, limit=2)) == 2


@pytest.mark.asyncio
async def test_skill_rollup_weights_tested_concepts_over_untouched_ones():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id)

        fresh = await service.get_skill_state(learner_id, SKILL)
        assert fresh.concept_count == 5
        assert fresh.tested_concept_count == 0
        assert fresh.mastery_probability == pytest.approx(0.5)
        assert fresh.uncertainty == pytest.approx(1.0)

        for _ in range(4):
            await service.update_from_answer(learner_id, [CONCEPTS[0]], is_correct=True, difficulty=4)
        await db.commit()

        rolled = await service.get_skill_state(learner_id, SKILL)
        assert rolled.tested_concept_count == 1
        assert rolled.attempt_count == 4
        assert rolled.mastery_probability > fresh.mastery_probability
        assert rolled.uncertainty < fresh.uncertainty
        assert len(rolled.concepts) == 5  # untouched concepts still reported
        assert rolled.name  # human-readable name resolved from the skill graph


@pytest.mark.asyncio
async def test_unknown_skill_rolls_up_to_an_empty_state_instead_of_raising():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        state = await service.get_skill_state(learner_id, "no_such_skill")
        assert state.concept_count == 0
        assert state.concepts == []


@pytest.mark.asyncio
async def test_ability_profile_reports_coverage_and_recommended_level():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id)
        await db.commit()

        blank = await service.get_ability_profile(learner_id)
        assert blank["total_concept_count"] == 50
        assert blank["tested_concept_count"] == 0
        assert blank["concept_coverage"] == 0.0
        assert blank["overall_uncertainty"] == pytest.approx(1.0)
        assert len(blank["skill_states"]) == 10

        for concept_id in CONCEPTS:
            for _ in range(4):
                await service.update_from_answer(
                    learner_id, [concept_id], is_correct=True, difficulty=5
                )
        await db.commit()

        profile = await service.get_ability_profile(learner_id)
        assert profile["tested_concept_count"] == len(CONCEPTS)
        assert profile["concept_coverage"] == pytest.approx(len(CONCEPTS) / 50)
        assert profile["total_attempts"] == 4 * len(CONCEPTS)
        # Only tested concepts count toward mastery, so a strong focused run
        # reads as advanced even though most of the domain is untouched.
        assert profile["overall_mastery"] > 0.75
        assert profile["recommended_level"] == "advanced"
        # ...while overall uncertainty stays high, because it is not.
        assert profile["overall_uncertainty"] > 0.8
        assert profile["weak_concepts"] == []
        assert profile["strong_concepts"]


@pytest.mark.asyncio
async def test_recommended_level_tracks_measured_mastery():
    learner_id = await _new_learner()
    async with async_session_factory() as db:
        service = LearnerModelService(db, domain_id=DOMAIN)
        await service.initialize_learner(learner_id)
        for concept_id in CONCEPTS:
            for _ in range(4):
                await service.update_from_answer(
                    learner_id, [concept_id], is_correct=False, difficulty=1
                )
        await db.commit()

        profile = await service.get_ability_profile(learner_id)
        assert profile["overall_mastery"] < 0.5
        assert profile["recommended_level"] == "basic"
        assert len(profile["weak_concepts"]) == len(CONCEPTS)
