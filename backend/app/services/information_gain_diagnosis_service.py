"""Adaptive item selection driven by expected information gain.

Every candidate item is scored on four deterministic terms:

``InformationGain``
    Expected reduction in posterior variance across the concepts the item
    touches. Peaks when the learner sits near p=0.5 on those concepts and
    collapses once the posterior is confident either way — that is what makes
    the session stop asking about things it already knows.

``CoverageGain``
    Bonus for concepts that have never been tested in this session, so a run
    spreads over the skill instead of drilling one concept.

``TimeCost``
    Penalty proportional to the item's expected answering time, normalised
    against the bank median, so a long item must earn its place.

``Fatigue``
    Penalty that grows with session length and consecutive hard items, so the
    tail of a session drifts toward shorter and easier probes.

    score = InformationGain + w_c*CoverageGain - w_t*TimeCost - w_f*Fatigue

The weights are module-level constants rather than learned parameters: with a
bank this size there is not enough response data to fit them honestly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Optional, Sequence

from app.services.domain_package_service import (
    load_assessment_bank,
    load_concept_nodes,
    load_skill_edges,
)
from app.services.learner_model_service import (
    PRIOR_VARIANCE,
    ConceptState,
    LearnerModelService,
    beta_variance,
    difficulty_weight,
    normalized_uncertainty,
)


# Objective weights. Every term is scaled to roughly [0, 1] before weighting,
# so these numbers mean what they look like: coverage is worth about a third of
# information gain, fatigue a quarter, time an eighth.
COVERAGE_WEIGHT = 0.35
TIME_WEIGHT = 0.15
FATIGUE_WEIGHT = 0.25

# Stop rule.
MIN_QUESTIONS = 5
MAX_QUESTIONS = 20
CONFIDENT_UNCERTAINTY = 0.30
# In prior-variance units: stop once the best remaining item would shave off
# less than ~5% of a fresh concept's uncertainty.
MIN_GAIN_TO_CONTINUE = 0.048

# Fatigue model.
HARD_DIFFICULTY = 4
FATIGUE_FREE_QUESTIONS = 6
MAX_SESSION_SECONDS = 20 * 60

DEFAULT_ESTIMATED_TIME = 45.0


@dataclass
class CandidateScore:
    """Full, auditable breakdown of why an item was or was not chosen."""

    item_id: str
    skill_id: Optional[str]
    concept_ids: list[str]
    difficulty: int
    estimated_time_sec: float
    information_gain: float
    coverage_gain: float
    time_cost: float
    fatigue: float
    total_score: float
    importance: int = 3

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "skill_id": self.skill_id,
            "concept_ids": list(self.concept_ids),
            "difficulty": self.difficulty,
            "estimated_time_sec": self.estimated_time_sec,
            "information_gain": round(self.information_gain, 6),
            "coverage_gain": round(self.coverage_gain, 6),
            "time_cost": round(self.time_cost, 6),
            "fatigue": round(self.fatigue, 6),
            "total_score": round(self.total_score, 6),
            "importance": self.importance,
        }


@dataclass
class SessionContext:
    """Everything the selector needs to know about the run so far."""

    answered_item_ids: list[str] = field(default_factory=list)
    tested_concept_ids: list[str] = field(default_factory=list)
    question_count: int = 0
    consecutive_hard: int = 0
    elapsed_seconds: float = 0.0
    target_skill_id: Optional[str] = None

    @classmethod
    def from_session(cls, session) -> "SessionContext":
        fatigue = session.fatigue_state or {}
        return cls(
            answered_item_ids=list(session.answered_item_ids or []),
            tested_concept_ids=list(session.tested_concept_ids or []),
            question_count=int(session.question_count or 0),
            consecutive_hard=int(fatigue.get("consecutive_hard", 0)),
            elapsed_seconds=float(fatigue.get("elapsed_seconds", 0.0)),
            target_skill_id=session.target_skill_id,
        )


def item_concept_ids(item: dict, concept_index: dict[str, dict]) -> list[str]:
    """Concepts an item measures.

    Prefers the explicit ``concept_ids`` field. Items authored before the
    concept graph existed fall back to every concept of their skill, which is a
    weaker but still usable signal.
    """
    explicit = [cid for cid in (item.get("concept_ids") or []) if cid in concept_index]
    if explicit:
        return explicit
    skill_id = item.get("skill_id")
    return [cid for cid, node in concept_index.items() if node.get("skill_id") == skill_id]


def item_estimated_time(item: dict) -> float:
    raw = item.get("estimated_time_sec") or item.get("estimated_seconds") or DEFAULT_ESTIMATED_TIME
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_ESTIMATED_TIME
    return value if value > 0 else DEFAULT_ESTIMATED_TIME


class InformationGainDiagnosisService:
    """Chooses the next diagnostic item and decides when to stop."""

    def __init__(
        self,
        learner_model: LearnerModelService,
        domain_id: Optional[str] = None,
    ):
        self.learner_model = learner_model
        self.domain_id = domain_id or learner_model.domain_id
        self._bank: Optional[list[dict]] = None
        self._concept_index: Optional[dict[str, dict]] = None
        self._median_time: Optional[float] = None

    # ---------------------------------------------------------------- domain

    @property
    def bank(self) -> list[dict]:
        if self._bank is None:
            self._bank = load_assessment_bank(self.domain_id)
        return self._bank

    @property
    def concept_index(self) -> dict[str, dict]:
        if self._concept_index is None:
            self._concept_index = {node["id"]: node for node in load_concept_nodes(self.domain_id)}
        return self._concept_index

    @property
    def median_time(self) -> float:
        if self._median_time is None:
            times = [item_estimated_time(item) for item in self.bank]
            self._median_time = median(times) if times else DEFAULT_ESTIMATED_TIME
        return self._median_time

    # ------------------------------------------------------------ candidates

    def get_candidate_items(
        self,
        context: SessionContext,
        skill_ids: Optional[Sequence[str]] = None,
    ) -> list[dict]:
        """Unanswered items, restricted to the target skill when one is set.

        If the target skill's own items run out *before* the session has met
        MIN_QUESTIONS, the scope widens one step to its transitive prerequisites
        — a learner who cannot do tf2 is plausibly blocked on ros2_node, so
        those items are still diagnostic, and a 3-question session is worth
        less than a slightly off-target 5-question one.

        Past that floor the scope never widens, for two reasons: a session the
        learner asked to be about tf2 should not quietly become a general
        survey, and every newly admitted concept enters at uncertainty 1.0,
        which would keep the confidence stop rule permanently out of reach.
        Once the focused items are gone the caller sees an empty list and ends
        the session with ``item_bank_exhausted``.
        """
        answered = set(context.answered_item_ids)
        available = [item for item in self.bank if item.get("id") not in answered]
        if not available:
            return []

        allowed: Optional[set[str]] = None
        if skill_ids:
            allowed = set(skill_ids)
        elif context.target_skill_id:
            allowed = {context.target_skill_id}
        if allowed is None:
            return available

        focused = [item for item in available if item.get("skill_id") in allowed]
        if focused or context.question_count >= MIN_QUESTIONS:
            return focused

        widened = allowed | self.prerequisite_skills(allowed)
        return [item for item in available if item.get("skill_id") in widened]

    def prerequisite_skills(self, skill_ids: Sequence[str] | set[str]) -> set[str]:
        """Transitive prerequisites of the given skills (excluding themselves)."""
        parents: dict[str, list[str]] = {}
        for edge in load_skill_edges(self.domain_id):
            if edge.get("relation") != "prerequisite":
                continue
            parents.setdefault(str(edge.get("to")), []).append(str(edge.get("from")))

        seen: set[str] = set()
        queue = [skill for skill in skill_ids]
        while queue:
            for parent in parents.get(queue.pop(), []):
                if parent not in seen:
                    seen.add(parent)
                    queue.append(parent)
        return seen - set(skill_ids)

    # -------------------------------------------------------------- the four terms

    def calculate_information_gain(
        self,
        item: dict,
        concept_states: dict[str, ConceptState],
    ) -> float:
        """Expected posterior-variance reduction from asking this item.

        For each concept, the outcome is marginalised over the learner's own
        predicted probability of answering correctly:

            E[Var_post] = p * Var(alpha+w, beta) + (1-p) * Var(alpha, beta+w)
            gain        = Var(alpha, beta) - E[Var_post]

        Averaging (rather than summing) over concepts keeps a broad item from
        outscoring a sharp one purely by touching more concepts.

        The result is expressed in units of the Beta(1,1) prior variance, so a
        gain of 1.0 means "this item would collapse a completely unknown
        concept". Without that normalisation the raw variance would live in
        [0, 1/12] and the objective's coverage/time/fatigue weights — which all
        assume roughly unit-scale terms — would swamp it by an order of
        magnitude.
        """
        concept_ids = item_concept_ids(item, self.concept_index)
        if not concept_ids:
            return 0.0

        difficulty = int(item.get("difficulty") or 3)
        total_gain = 0.0
        for concept_id in concept_ids:
            state = concept_states.get(concept_id)
            if state is None:
                continue
            alpha, beta = state.alpha, state.beta
            prior_variance = beta_variance(alpha, beta)

            # Expected weight of the evidence this answer would carry.
            weight_correct = difficulty_weight(difficulty, True) / len(concept_ids) ** 0.5
            weight_wrong = difficulty_weight(difficulty, False) / len(concept_ids) ** 0.5

            p_correct = self._predicted_correct(state, difficulty)
            expected_posterior = (
                p_correct * beta_variance(alpha + weight_correct, beta)
                + (1.0 - p_correct) * beta_variance(alpha, beta + weight_wrong)
            )
            total_gain += max(0.0, prior_variance - expected_posterior)

        return total_gain / len(concept_ids) / PRIOR_VARIANCE

    @staticmethod
    def _predicted_correct(state: ConceptState, difficulty: int) -> float:
        """Probability of a correct answer, tilted by item difficulty.

        A 2-parameter-logistic-style adjustment around the posterior mean: hard
        items pull the prediction down, easy items pull it up, without ever
        saturating at 0 or 1.
        """
        base = state.mastery_probability
        offset = (int(difficulty) - 3) * 0.08
        return min(0.97, max(0.03, base - offset))

    def calculate_coverage_gain(
        self,
        item: dict,
        context: SessionContext,
        concept_states: dict[str, ConceptState],
    ) -> float:
        """Fraction of the item's concepts not yet probed in this session.

        Core concepts and concepts with no prior evidence at all count for more,
        which is what pushes a fresh learner through the breadth of the skill
        before the session starts drilling.
        """
        concept_ids = item_concept_ids(item, self.concept_index)
        if not concept_ids:
            return 0.0
        tested = set(context.tested_concept_ids)

        total = 0.0
        for concept_id in concept_ids:
            if concept_id in tested:
                continue
            node = self.concept_index.get(concept_id, {})
            weight = 1.0 if node.get("importance") == "core" else 0.7
            state = concept_states.get(concept_id)
            if state is not None and state.attempt_count == 0:
                weight *= 1.3  # never seen in any session, not just this one
            total += weight
        return total / len(concept_ids)

    def calculate_time_cost(self, item: dict) -> float:
        """Expected answering time relative to the bank median, capped at 3x."""
        return min(3.0, item_estimated_time(item) / self.median_time)

    def calculate_fatigue(self, item: dict, context: SessionContext) -> float:
        """Penalty for pushing a tired learner, in [0, ~2].

        Three additive sources: session length past a free allowance, a run of
        consecutive hard items, and wall-clock time spent.
        """
        length_fatigue = max(0, context.question_count - FATIGUE_FREE_QUESTIONS) / float(MAX_QUESTIONS)

        difficulty = int(item.get("difficulty") or 3)
        streak_fatigue = 0.0
        if difficulty >= HARD_DIFFICULTY:
            streak_fatigue = 0.25 * (context.consecutive_hard + 1)

        time_fatigue = min(1.0, context.elapsed_seconds / float(MAX_SESSION_SECONDS))
        return length_fatigue + streak_fatigue + time_fatigue

    # ------------------------------------------------------------- selection

    async def score_candidates(
        self,
        learner_id: str,
        context: SessionContext,
        skill_ids: Optional[Sequence[str]] = None,
    ) -> list[CandidateScore]:
        """Score every candidate, best first."""
        candidates = self.get_candidate_items(context, skill_ids)
        if not candidates:
            return []

        relevant_concepts = sorted({
            concept_id
            for item in candidates
            for concept_id in item_concept_ids(item, self.concept_index)
        })
        concept_states = await self.learner_model.get_concept_states(learner_id, relevant_concepts)

        scored: list[CandidateScore] = []
        for item in candidates:
            information_gain = self.calculate_information_gain(item, concept_states)
            coverage_gain = self.calculate_coverage_gain(item, context, concept_states)
            time_cost = self.calculate_time_cost(item)
            fatigue = self.calculate_fatigue(item, context)
            total = (
                information_gain
                + COVERAGE_WEIGHT * coverage_gain
                - TIME_WEIGHT * time_cost
                - FATIGUE_WEIGHT * fatigue
            )
            scored.append(CandidateScore(
                item_id=str(item.get("id")),
                skill_id=item.get("skill_id"),
                concept_ids=item_concept_ids(item, self.concept_index),
                difficulty=int(item.get("difficulty") or 3),
                estimated_time_sec=item_estimated_time(item),
                information_gain=information_gain,
                coverage_gain=coverage_gain,
                time_cost=time_cost,
                fatigue=fatigue,
                total_score=total,
                importance=int(item.get("importance") or 3),
            ))

        # Ties broken by importance then id so selection is fully reproducible.
        scored.sort(key=lambda row: (-row.total_score, -row.importance, row.item_id))
        return scored

    async def select_next_item(
        self,
        learner_id: str,
        context: SessionContext,
        skill_ids: Optional[Sequence[str]] = None,
    ) -> Optional[CandidateScore]:
        """Highest-scoring unanswered item, or None when the bank is exhausted."""
        scored = await self.score_candidates(learner_id, context, skill_ids)
        return scored[0] if scored else None

    def get_item(self, item_id: str) -> Optional[dict]:
        for item in self.bank:
            if item.get("id") == item_id:
                return item
        return None

    # ------------------------------------------------------------- stop rule

    async def should_stop(
        self,
        learner_id: str,
        context: SessionContext,
        next_candidate: Optional[CandidateScore] = None,
        skill_ids: Optional[Sequence[str]] = None,
    ) -> tuple[bool, str]:
        """Decide whether the session has learned enough.

        Returns ``(stop, reason)``. Reasons are stable identifiers so the client
        and the report can explain the stop without re-deriving it.
        """
        if context.question_count >= MAX_QUESTIONS:
            return True, "max_questions_reached"

        if next_candidate is None:
            candidate = await self.select_next_item(learner_id, context, skill_ids)
            if candidate is None:
                return True, "item_bank_exhausted"
            next_candidate = candidate

        if context.question_count < MIN_QUESTIONS:
            return False, "min_questions_not_reached"

        tested = list(context.tested_concept_ids)
        if tested:
            states = await self.learner_model.get_concept_states(learner_id, tested)
            worst = max((state.uncertainty for state in states.values()), default=1.0)
            if worst <= CONFIDENT_UNCERTAINTY:
                return True, "posterior_confident"

        if next_candidate.information_gain < MIN_GAIN_TO_CONTINUE:
            return True, "information_gain_exhausted"

        if context.elapsed_seconds >= MAX_SESSION_SECONDS:
            return True, "time_budget_exhausted"

        return False, "continue"


def initial_uncertainty() -> float:
    """Uncertainty of an untouched concept — exported for report baselines."""
    return normalized_uncertainty(1.0, 1.0)
