"""Unified state shared by the orchestrator and all agents."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkflowState:
    workflow_id: str
    learner_id: str
    domain_id: str
    target_goal: Optional[str] = None

    learner_profile: Optional[dict] = None
    assessment_result: Optional[dict] = None
    mastery_state: Optional[dict] = None
    target_skills: list[str] = field(default_factory=list)
    learning_path: list[dict] = field(default_factory=list)

    # Beta-Bernoulli learner model. `mastery_state` above is the legacy 0-100
    # per-skill view kept for the existing dashboard; these carry the per-concept
    # posterior — probability *and* uncertainty — that the planner reads.
    learner_state: Optional[dict] = None
    diagnosis_mode: str = "auto"
    diagnosis_session_id: Optional[str] = None
    mastery_summary: Optional[dict] = None
    weak_concepts: list[dict] = field(default_factory=list)
    uncertain_concepts: list[dict] = field(default_factory=list)

    search_query: Optional[str] = None
    evidence_list: list[dict] = field(default_factory=list)

    generated_resources: Optional[dict] = None
    review_result: Optional[dict] = None
    revision_count: int = 0
    resource_id: Optional[str] = None

    final_decision: Optional[str] = None
    feedback: Optional[dict] = None
    source_resource_id: Optional[str] = None
    source_skill_id: Optional[str] = None
    requested_difficulty: Optional[str] = None
    version_filter: Optional[str] = None
    insert_skills: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    agent_trace: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        allowed = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in allowed})
