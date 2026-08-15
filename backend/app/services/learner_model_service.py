"""Beta-Bernoulli learner model.

The learner is represented as one Beta posterior per concept:

    p(concept mastered) ~ Beta(alpha, beta)

``alpha`` accumulates evidence of success, ``beta`` evidence of failure. Both
start at a weak prior so an unseen concept sits at mastery 0.5 with maximum
uncertainty, which is exactly what makes it attractive to the information-gain
item selector.

Two refinements over a textbook Beta update keep the model honest on real
assessment data:

* **Difficulty weighting.** Answering a hard item correctly is stronger evidence
  than answering an easy one correctly, and failing an easy item is stronger
  evidence of a gap than failing a hard one.
* **Response-time discounting.** An answer produced far faster than the item's
  expected time is likely a guess, so its evidence weight is reduced. This is a
  deliberately conservative heuristic, not a claim of guess detection.

Everything here is deterministic and unit-testable: no LLM is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.learner_concept_mastery import LearnerConceptMastery
from app.services.domain_package_service import load_concept_nodes, load_skill_nodes


# Weak, symmetric prior: unseen concept => mastery 0.5, uncertainty 1.0.
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0

# Beta(1,1) has variance 1/12; uncertainty is normalised against it so a fresh
# concept reads as 1.0 and a well-evidenced one tends to 0.
PRIOR_VARIANCE = 1.0 / 12.0

WEAK_MASTERY_THRESHOLD = 0.6
UNCERTAIN_THRESHOLD = 0.35

# Difficulty runs 1..5 in the domain packages.
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


@dataclass
class ConceptState:
    """Snapshot of one concept posterior."""

    concept_id: str
    skill_id: Optional[str] = None
    name: Optional[str] = None
    alpha: float = PRIOR_ALPHA
    beta: float = PRIOR_BETA
    mastery_probability: float = 0.5
    uncertainty: float = 1.0
    attempt_count: int = 0
    correct_count: int = 0
    last_response_time: Optional[float] = None
    last_difficulty: Optional[int] = None

    @property
    def evidence_strength(self) -> float:
        """Total pseudo-observations behind this posterior."""
        return (self.alpha - PRIOR_ALPHA) + (self.beta - PRIOR_BETA)

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "skill_id": self.skill_id,
            "name": self.name,
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "mastery_probability": round(self.mastery_probability, 4),
            "uncertainty": round(self.uncertainty, 4),
            "attempt_count": self.attempt_count,
            "correct_count": self.correct_count,
            "last_response_time": self.last_response_time,
            "last_difficulty": self.last_difficulty,
        }


@dataclass
class SkillState:
    """Concept posteriors rolled up to one skill."""

    skill_id: str
    name: Optional[str] = None
    mastery_probability: float = 0.5
    uncertainty: float = 1.0
    concept_count: int = 0
    tested_concept_count: int = 0
    attempt_count: int = 0
    weak_concept_ids: list[str] = field(default_factory=list)
    concepts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "mastery_probability": round(self.mastery_probability, 4),
            "uncertainty": round(self.uncertainty, 4),
            "concept_count": self.concept_count,
            "tested_concept_count": self.tested_concept_count,
            "attempt_count": self.attempt_count,
            "weak_concept_ids": list(self.weak_concept_ids),
            "concepts": list(self.concepts),
        }


def beta_mean(alpha: float, beta: float) -> float:
    """Posterior mean = expected probability of a correct response."""
    return alpha / (alpha + beta)


def beta_variance(alpha: float, beta: float) -> float:
    total = alpha + beta
    return (alpha * beta) / (total * total * (total + 1.0))


def normalized_uncertainty(alpha: float, beta: float) -> float:
    """Variance rescaled so the Beta(1,1) prior reads exactly 1.0."""
    return min(1.0, beta_variance(alpha, beta) / PRIOR_VARIANCE)


def difficulty_weight(difficulty: Optional[int], is_correct: bool) -> float:
    """Evidence weight of one answer given item difficulty.

    A correct answer on a difficulty-5 item carries 1.5x weight; on a
    difficulty-1 item, 0.7x. An incorrect answer is weighted inversely, because
    failing an easy item is the stronger signal.
    """
    level = int(difficulty) if difficulty is not None else 3
    level = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, level))
    normalized = (level - MIN_DIFFICULTY) / (MAX_DIFFICULTY - MIN_DIFFICULTY)  # 0..1
    if is_correct:
        return 0.7 + 0.8 * normalized
    return 1.5 - 0.8 * normalized


def response_time_weight(
    response_time: Optional[float],
    expected_time: Optional[float],
    is_correct: bool,
) -> float:
    """Discount suspiciously fast correct answers.

    Below 25% of the expected time a correct answer is treated as half-evidence,
    ramping back to full weight at 60%. Incorrect answers are never discounted:
    a fast wrong answer is still a wrong answer.
    """
    if not is_correct or response_time is None or not expected_time or expected_time <= 0:
        return 1.0
    ratio = max(0.0, float(response_time)) / float(expected_time)
    if ratio >= 0.6:
        return 1.0
    if ratio <= 0.25:
        return 0.5
    return 0.5 + 0.5 * (ratio - 0.25) / (0.6 - 0.25)


class LearnerModelService:
    """Reads and updates per-concept Beta posteriors for one learner."""

    def __init__(self, db: AsyncSession, domain_id: str = "ros2_robotics"):
        self.db = db
        self.domain_id = domain_id

    # ---------------------------------------------------------------- domain

    def _concept_nodes(self) -> list[dict]:
        return load_concept_nodes(self.domain_id)

    def _concept_index(self) -> dict[str, dict]:
        return {node["id"]: node for node in self._concept_nodes()}

    def _skill_name_map(self) -> dict[str, str]:
        return {node["id"]: node.get("name", node["id"]) for node in load_skill_nodes(self.domain_id)}

    # ----------------------------------------------------------- persistence

    async def _load_rows(
        self,
        learner_id: str,
        concept_ids: Optional[Sequence[str]] = None,
    ) -> dict[str, LearnerConceptMastery]:
        query = select(LearnerConceptMastery).where(LearnerConceptMastery.learner_id == learner_id)
        if concept_ids is not None:
            concept_ids = list(concept_ids)
            if not concept_ids:
                return {}
            query = query.where(LearnerConceptMastery.concept_id.in_(concept_ids))
        rows = list((await self.db.execute(query)).scalars().all())
        return {row.concept_id: row for row in rows}

    @staticmethod
    def _row_to_state(row: LearnerConceptMastery, node: Optional[dict]) -> ConceptState:
        return ConceptState(
            concept_id=row.concept_id,
            skill_id=row.skill_id or (node or {}).get("skill_id"),
            name=(node or {}).get("name"),
            alpha=float(row.alpha),
            beta=float(row.beta),
            mastery_probability=float(row.mastery_probability),
            uncertainty=float(row.uncertainty),
            attempt_count=int(row.attempt_count),
            correct_count=int(row.correct_count),
            last_response_time=row.last_response_time,
            last_difficulty=row.last_difficulty,
        )

    @staticmethod
    def _prior_state(concept_id: str, node: Optional[dict]) -> ConceptState:
        return ConceptState(
            concept_id=concept_id,
            skill_id=(node or {}).get("skill_id"),
            name=(node or {}).get("name"),
            alpha=PRIOR_ALPHA,
            beta=PRIOR_BETA,
            mastery_probability=beta_mean(PRIOR_ALPHA, PRIOR_BETA),
            uncertainty=normalized_uncertainty(PRIOR_ALPHA, PRIOR_BETA),
        )

    # ------------------------------------------------------------ public API

    async def initialize_learner(
        self,
        learner_id: str,
        concept_ids: Optional[Iterable[str]] = None,
    ) -> list[ConceptState]:
        """Materialise Beta(1,1) rows for every concept the learner may be asked.

        Idempotent: concepts that already have a posterior are left untouched, so
        re-running a diagnosis never resets prior evidence.
        """
        index = self._concept_index()
        targets = list(concept_ids) if concept_ids is not None else list(index.keys())
        targets = [cid for cid in targets if cid in index]
        existing = await self._load_rows(learner_id, targets)

        for concept_id in targets:
            if concept_id in existing:
                continue
            node = index[concept_id]
            row = LearnerConceptMastery(
                learner_id=learner_id,
                concept_id=concept_id,
                skill_id=node.get("skill_id"),
                alpha=PRIOR_ALPHA,
                beta=PRIOR_BETA,
                mastery_probability=beta_mean(PRIOR_ALPHA, PRIOR_BETA),
                uncertainty=normalized_uncertainty(PRIOR_ALPHA, PRIOR_BETA),
                attempt_count=0,
                correct_count=0,
            )
            self.db.add(row)
            existing[concept_id] = row
        await self.db.flush()
        return [self._row_to_state(existing[cid], index.get(cid)) for cid in targets]

    async def get_concept_state(self, learner_id: str, concept_id: str) -> ConceptState:
        """Posterior for one concept, falling back to the prior when unseen."""
        index = self._concept_index()
        rows = await self._load_rows(learner_id, [concept_id])
        row = rows.get(concept_id)
        if row is None:
            return self._prior_state(concept_id, index.get(concept_id))
        return self._row_to_state(row, index.get(concept_id))

    async def get_concept_states(
        self,
        learner_id: str,
        concept_ids: Optional[Sequence[str]] = None,
    ) -> dict[str, ConceptState]:
        """Batch form of :meth:`get_concept_state` — one query for many concepts."""
        index = self._concept_index()
        targets = list(concept_ids) if concept_ids is not None else list(index.keys())
        rows = await self._load_rows(learner_id, targets)
        return {
            concept_id: (
                self._row_to_state(rows[concept_id], index.get(concept_id))
                if concept_id in rows
                else self._prior_state(concept_id, index.get(concept_id))
            )
            for concept_id in targets
        }

    async def update_from_answer(
        self,
        learner_id: str,
        concept_ids: Sequence[str],
        is_correct: bool,
        difficulty: Optional[int] = None,
        response_time: Optional[float] = None,
        expected_time: Optional[float] = None,
    ) -> list[ConceptState]:
        """Apply one answer to every concept the item touches.

        The evidence weight is shared across concepts: an item covering three
        concepts must not count as three independent observations.
        """
        index = self._concept_index()
        targets = [cid for cid in dict.fromkeys(concept_ids) if cid in index]
        if not targets:
            return []

        weight = (
            difficulty_weight(difficulty, is_correct)
            * response_time_weight(response_time, expected_time, is_correct)
        )
        weight /= len(targets) ** 0.5  # shared-credit damping for multi-concept items

        rows = await self._load_rows(learner_id, targets)
        updated: list[ConceptState] = []
        for concept_id in targets:
            node = index[concept_id]
            row = rows.get(concept_id)
            if row is None:
                row = LearnerConceptMastery(
                    learner_id=learner_id,
                    concept_id=concept_id,
                    skill_id=node.get("skill_id"),
                    alpha=PRIOR_ALPHA,
                    beta=PRIOR_BETA,
                    attempt_count=0,
                    correct_count=0,
                )
                self.db.add(row)

            if is_correct:
                row.alpha = float(row.alpha) + weight
            else:
                row.beta = float(row.beta) + weight

            row.skill_id = row.skill_id or node.get("skill_id")
            row.attempt_count = int(row.attempt_count) + 1
            row.correct_count = int(row.correct_count) + (1 if is_correct else 0)
            row.mastery_probability = beta_mean(row.alpha, row.beta)
            row.uncertainty = normalized_uncertainty(row.alpha, row.beta)
            if response_time is not None:
                row.last_response_time = float(response_time)
            if difficulty is not None:
                row.last_difficulty = int(difficulty)
            row.updated_at = utc_now()
            updated.append(self._row_to_state(row, node))

        await self.db.flush()
        return updated

    async def get_skill_state(self, learner_id: str, skill_id: str) -> SkillState:
        """Roll concept posteriors up to a skill.

        The rollup is evidence-weighted: concepts the learner has actually been
        tested on dominate, and core concepts count double, so a skill is not
        declared mastered on the strength of its peripheral concepts alone.
        """
        nodes = [node for node in self._concept_nodes() if node.get("skill_id") == skill_id]
        states = await self.get_concept_states(learner_id, [node["id"] for node in nodes])
        skill_name = self._skill_name_map().get(skill_id, skill_id)
        if not nodes:
            return SkillState(skill_id=skill_id, name=skill_name, concept_count=0)

        total_weight = 0.0
        mastery_acc = 0.0
        uncertainty_acc = 0.0
        attempts = 0
        tested = 0
        weak: list[str] = []
        concept_dicts: list[dict] = []

        for node in nodes:
            state = states[node["id"]]
            importance_weight = 2.0 if node.get("importance") == "core" else 1.0
            weight = importance_weight * (1.0 + state.evidence_strength)
            mastery_acc += weight * state.mastery_probability
            uncertainty_acc += weight * state.uncertainty
            total_weight += weight
            attempts += state.attempt_count
            if state.attempt_count > 0:
                tested += 1
            if state.mastery_probability < WEAK_MASTERY_THRESHOLD:
                weak.append(state.concept_id)
            concept_dicts.append(state.to_dict())

        return SkillState(
            skill_id=skill_id,
            name=skill_name,
            mastery_probability=mastery_acc / total_weight,
            uncertainty=uncertainty_acc / total_weight,
            concept_count=len(nodes),
            tested_concept_count=tested,
            attempt_count=attempts,
            weak_concept_ids=weak,
            concepts=concept_dicts,
        )

    async def get_weak_concepts(
        self,
        learner_id: str,
        threshold: float = WEAK_MASTERY_THRESHOLD,
        skill_id: Optional[str] = None,
        limit: Optional[int] = None,
        tested_only: bool = True,
    ) -> list[ConceptState]:
        """Concepts whose posterior mean sits below ``threshold``.

        By default only concepts with at least one observation are returned —
        an untouched concept sits at the 0.5 prior and is *unknown*, not *weak*.
        """
        index = self._concept_index()
        targets = [
            cid for cid, node in index.items()
            if skill_id is None or node.get("skill_id") == skill_id
        ]
        states = await self.get_concept_states(learner_id, targets)
        weak = [
            state for state in states.values()
            if state.mastery_probability < threshold and (not tested_only or state.attempt_count > 0)
        ]
        weak.sort(key=lambda state: (state.mastery_probability, -state.evidence_strength))
        return weak[:limit] if limit else weak

    async def get_uncertain_concepts(
        self,
        learner_id: str,
        threshold: float = UNCERTAIN_THRESHOLD,
        skill_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[ConceptState]:
        """Concepts the model is least confident about, most uncertain first."""
        index = self._concept_index()
        targets = [
            cid for cid, node in index.items()
            if skill_id is None or node.get("skill_id") == skill_id
        ]
        states = await self.get_concept_states(learner_id, targets)
        uncertain = [state for state in states.values() if state.uncertainty > threshold]
        uncertain.sort(key=lambda state: -state.uncertainty)
        return uncertain[:limit] if limit else uncertain

    async def get_ability_profile(self, learner_id: str) -> dict:
        """Whole-domain picture used by the planner and the report endpoints."""
        index = self._concept_index()
        states = await self.get_concept_states(learner_id, list(index.keys()))
        skill_ids = [node["id"] for node in load_skill_nodes(self.domain_id)]
        skill_states = [await self.get_skill_state(learner_id, skill_id) for skill_id in skill_ids]

        tested = [state for state in states.values() if state.attempt_count > 0]
        overall = (
            sum(state.mastery_probability for state in tested) / len(tested)
            if tested else beta_mean(PRIOR_ALPHA, PRIOR_BETA)
        )
        overall_uncertainty = (
            sum(state.uncertainty for state in states.values()) / len(states)
            if states else 1.0
        )
        weak = await self.get_weak_concepts(learner_id, limit=10)
        uncertain = await self.get_uncertain_concepts(learner_id, limit=10)

        strongest = sorted(tested, key=lambda state: -state.mastery_probability)[:5]
        coverage = len(tested) / len(states) if states else 0.0

        if overall < 0.5:
            level = "basic"
        elif overall < 0.75:
            level = "intermediate"
        else:
            level = "advanced"

        return {
            "learner_id": learner_id,
            "domain_id": self.domain_id,
            "overall_mastery": round(overall, 4),
            "overall_uncertainty": round(overall_uncertainty, 4),
            "recommended_level": level,
            "concept_coverage": round(coverage, 4),
            "tested_concept_count": len(tested),
            "total_concept_count": len(states),
            "total_attempts": sum(state.attempt_count for state in states.values()),
            "skill_states": [state.to_dict() for state in skill_states],
            "weak_concepts": [state.to_dict() for state in weak],
            "uncertain_concepts": [state.to_dict() for state in uncertain],
            "strong_concepts": [state.to_dict() for state in strongest],
            "updated_at": utc_now().isoformat(),
        }
