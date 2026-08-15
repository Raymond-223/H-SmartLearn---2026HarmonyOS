"""Resource, assessment attempt, and feedback API schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class ResourceResponse(BaseModel):
    resource_id: str
    workflow_id: Optional[str] = None
    difficulty: str
    target_skill: Optional[str] = None
    lecture: Optional[dict] = None
    practice_guide: Optional[dict] = None
    graded_test: Optional[dict] = None
    citations: list[dict] = Field(default_factory=list)
    review: Optional[dict] = None
    metadata: Optional[dict] = None
    feedback_recorded: bool = False
    feedback_decision: Optional[str] = None
    feedback_reason: Optional[str] = None
    next_workflow_id: Optional[str] = None


class ResourceTestAnswer(BaseModel):
    item_id: str
    answer: str = Field(min_length=1, max_length=32)


class ResourceTestSubmit(BaseModel):
    answers: list[ResourceTestAnswer] = Field(min_length=1, max_length=100)


class ResourceTestItemResult(BaseModel):
    item_id: str
    skill_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    difficulty: Optional[str] = None


class ResourceTestResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    correct_count: int
    total_count: int
    error_tags: list[str] = Field(default_factory=list, max_length=50)
    item_results: list[ResourceTestItemResult] = Field(default_factory=list)


class PracticeStepResult(BaseModel):
    order: int = Field(ge=1)
    success: bool


class FeedbackCreate(BaseModel):
    # correct_rate / practice_score are retained for old queued payloads, but the
    # server derives authoritative values from the saved test attempt and the
    # complete per-step practice result list.
    correct_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    practice_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    practice_results: list[PracticeStepResult] = Field(min_length=1)
    subjective_difficulty: str = Field(default="appropriate", pattern="^(too_easy|appropriate|too_hard)$")
    error_tags: list[str] = Field(default_factory=list, max_length=50)


class FeedbackResponse(BaseModel):
    decision: str
    reason: Optional[str] = None
    next_workflow_id: Optional[str] = None
