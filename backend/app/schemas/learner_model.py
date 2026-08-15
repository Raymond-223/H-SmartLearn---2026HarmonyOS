"""API schemas for the Beta-Bernoulli learner model."""

from typing import Optional

from pydantic import BaseModel, Field


class ConceptMasteryState(BaseModel):
    concept_id: str
    skill_id: Optional[str] = None
    name: Optional[str] = None
    alpha: float = 1.0
    beta: float = 1.0
    mastery_probability: float = 0.5
    uncertainty: float = 1.0
    attempt_count: int = 0
    correct_count: int = 0
    last_response_time: Optional[float] = None
    last_difficulty: Optional[int] = None


class SkillMasteryState(BaseModel):
    skill_id: str
    name: Optional[str] = None
    mastery_probability: float = 0.5
    uncertainty: float = 1.0
    concept_count: int = 0
    tested_concept_count: int = 0
    attempt_count: int = 0
    weak_concept_ids: list[str] = Field(default_factory=list)
    concepts: list[ConceptMasteryState] = Field(default_factory=list)


class AbilityProfile(BaseModel):
    learner_id: str
    domain_id: str = "ros2_robotics"
    overall_mastery: float = 0.5
    overall_uncertainty: float = 1.0
    recommended_level: str = "basic"
    concept_coverage: float = 0.0
    tested_concept_count: int = 0
    total_concept_count: int = 0
    total_attempts: int = 0
    skill_states: list[SkillMasteryState] = Field(default_factory=list)
    weak_concepts: list[ConceptMasteryState] = Field(default_factory=list)
    uncertain_concepts: list[ConceptMasteryState] = Field(default_factory=list)
    strong_concepts: list[ConceptMasteryState] = Field(default_factory=list)
    updated_at: Optional[str] = None


class LearnerState(BaseModel):
    """Everything downstream agents need to know about a learner.

    This replaces the single ``score`` / ``difficulty`` pair the planner used to
    read: mastery is per concept, uncertainty is explicit, and misconceptions
    and context travel with it.
    """

    learner_id: str
    domain_id: str = "ros2_robotics"
    ability_profile: Optional[AbilityProfile] = None
    concept_states: list[ConceptMasteryState] = Field(default_factory=list)
    skill_states: list[SkillMasteryState] = Field(default_factory=list)
    weak_concept_ids: list[str] = Field(default_factory=list)
    uncertain_concept_ids: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)


class WeakConceptResponse(BaseModel):
    learner_id: str
    domain_id: str = "ros2_robotics"
    threshold: float = 0.6
    weak_concepts: list[ConceptMasteryState] = Field(default_factory=list)


class LearnerMasteryResponse(BaseModel):
    learner_id: str
    domain_id: str = "ros2_robotics"
    overall_mastery: float = 0.5
    overall_uncertainty: float = 1.0
    skill_states: list[SkillMasteryState] = Field(default_factory=list)
    concept_states: list[ConceptMasteryState] = Field(default_factory=list)
