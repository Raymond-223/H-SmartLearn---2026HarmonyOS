"""Workflow API schemas."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.learner_model import ConceptMasteryState, LearnerState


class WorkflowCreate(BaseModel):
    learner_id: str = Field(min_length=1, max_length=100)
    domain_id: str = Field(min_length=1, max_length=100)
    assessment_id: Optional[str] = Field(default=None, max_length=100)
    target_goal: Optional[str] = Field(default=None, max_length=500)
    target_skill_id: Optional[str] = Field(default=None, max_length=100)
    version_filter: Optional[str] = Field(default=None, max_length=50, description="ROS/knowledge version constraint, e.g. humble")
    diagnosis_mode: Literal["auto", "adaptive"] = Field(
        default="auto",
        description=(
            "auto: diagnose from existing evidence and run straight through. "
            "adaptive: pause at DIAGNOSIS_QUESTIONING and wait for an interactive "
            "/diagnosis session; the workflow resumes once that session ends."
        ),
    )


class WorkflowCreateResponse(BaseModel):
    workflow_id: str
    status: str = "queued"


class WorkflowStatus(BaseModel):
    workflow_id: str
    status: str
    current_agent: Optional[str] = None
    progress: int = 0
    resource_id: Optional[str] = None
    error_message: Optional[str] = None


class AgentTraceItem(BaseModel):
    agent: str
    status: str
    summary: Optional[str] = None
    confidence: Optional[float] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WorkflowTrace(BaseModel):
    runs: list[AgentTraceItem] = Field(default_factory=list)


class MasterySummary(BaseModel):
    """Compact roll-up of the Beta posterior, safe to embed in workflow state."""

    overall_mastery: float = 0.5
    overall_uncertainty: float = 1.0
    recommended_level: str = "basic"
    concept_coverage: float = 0.0
    tested_concept_count: int = 0
    total_concept_count: int = 0
    skill_mastery: dict[str, float] = Field(default_factory=dict)
    skill_uncertainty: dict[str, float] = Field(default_factory=dict)


class WorkflowLearnerState(BaseModel):
    """The learner-model slice of WorkflowState, as seen over the API."""

    learner_state: Optional[LearnerState] = None
    diagnosis_session_id: Optional[str] = None
    mastery_summary: Optional[MasterySummary] = None
    weak_concepts: list[ConceptMasteryState] = Field(default_factory=list)
    uncertain_concepts: list[ConceptMasteryState] = Field(default_factory=list)


class WorkflowSnapshot(BaseModel):
    status: WorkflowStatus
    trace: WorkflowTrace
    learner: Optional[WorkflowLearnerState] = None
