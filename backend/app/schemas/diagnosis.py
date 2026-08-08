"""API schemas for adaptive, item-by-item diagnosis."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.learner_model import AbilityProfile, ConceptMasteryState, SkillMasteryState


class DiagnosisOption(BaseModel):
    key: str
    text: str


class DiagnosisStartRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=100)
    domain_id: str = Field(default="ros2_robotics", min_length=1, max_length=100)
    target_skill_id: Optional[str] = Field(default=None, max_length=100)
    workflow_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Workflow paused at DIAGNOSIS_QUESTIONING; it resumes when this session finishes.",
    )


class DiagnosisNextItem(BaseModel):
    """One item plus the selection evidence that justified asking it."""

    item_id: str
    skill_id: Optional[str] = None
    concept_ids: list[str] = Field(default_factory=list)
    question_type: str = "single_choice"
    difficulty: int = 1
    stem: str = ""
    options: list[DiagnosisOption] = Field(default_factory=list)
    estimated_time_sec: float = 45.0
    importance: int = 3
    question_index: int = 1
    information_gain: float = 0.0
    coverage_gain: float = 0.0
    time_cost: float = 0.0
    fatigue: float = 0.0
    selection_score: float = 0.0
    # The correct answer is never sent to the client while the item is open.


class DiagnosisConceptDelta(BaseModel):
    """How one answer moved one concept posterior."""

    concept_id: str
    name: Optional[str] = None
    mastery_before: float = 0.5
    mastery_after: float = 0.5
    uncertainty_before: float = 1.0
    uncertainty_after: float = 1.0


class DiagnosisAnswerRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=500)
    response_time_sec: Optional[float] = Field(default=None, ge=0, le=3600)


class DiagnosisAnswerResponse(BaseModel):
    """Result of one answer: grading, model delta, and the next item in one round trip."""

    session_id: str
    item_id: str
    is_correct: bool
    correct_answer: str
    explanation: str = ""
    error_tags: list[str] = Field(default_factory=list)
    misconception_tags: list[str] = Field(default_factory=list)
    concept_deltas: list[DiagnosisConceptDelta] = Field(default_factory=list)
    question_count: int = 0
    finished: bool = False
    stop_reason: Optional[str] = None
    next_item: Optional[DiagnosisNextItem] = None
    result: Optional["DiagnosisResult"] = None


class DiagnosisStartResponse(BaseModel):
    session_id: str
    learner_id: str
    domain_id: str
    target_skill_id: Optional[str] = None
    workflow_id: Optional[str] = None
    status: str = "in_progress"
    question_count: int = 0
    next_item: Optional[DiagnosisNextItem] = None
    started_at: Optional[datetime] = None


class DiagnosisSessionState(BaseModel):
    session_id: str
    learner_id: str
    domain_id: str
    target_skill_id: Optional[str] = None
    workflow_id: Optional[str] = None
    status: str = "in_progress"
    question_count: int = 0
    answered_item_ids: list[str] = Field(default_factory=list)
    tested_concept_ids: list[str] = Field(default_factory=list)
    fatigue_state: dict = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class DiagnosisNextResponse(BaseModel):
    session_id: str
    finished: bool = False
    stop_reason: Optional[str] = None
    question_count: int = 0
    next_item: Optional[DiagnosisNextItem] = None


class DiagnosisResult(BaseModel):
    """Terminal report for one adaptive diagnosis run."""

    session_id: str
    learner_id: str
    domain_id: str = "ros2_robotics"
    target_skill_id: Optional[str] = None
    status: str = "completed"
    question_count: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    total_time_sec: float = 0.0
    stop_reason: Optional[str] = None
    overall_mastery: float = 0.5
    overall_uncertainty: float = 1.0
    recommended_level: str = "basic"
    tested_concept_ids: list[str] = Field(default_factory=list)
    weak_concepts: list[ConceptMasteryState] = Field(default_factory=list)
    uncertain_concepts: list[ConceptMasteryState] = Field(default_factory=list)
    skill_states: list[SkillMasteryState] = Field(default_factory=list)
    ability_profile: Optional[AbilityProfile] = None
    misconceptions: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    item_results: list[dict] = Field(default_factory=list)
    summary: str = ""


DiagnosisAnswerResponse.model_rebuild()
