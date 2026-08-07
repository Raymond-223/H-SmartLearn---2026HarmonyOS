"""Assessment API schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class AssessmentCreate(BaseModel):
    learner_id: str = Field(min_length=1, max_length=100)
    domain_id: str = Field(min_length=1, max_length=100)
    target_goal: Optional[str] = Field(default=None, max_length=500)


class AssessmentOption(BaseModel):
    key: str
    text: str


class AssessmentPublicItem(BaseModel):
    item_id: str
    skill_id: str
    type: str
    difficulty: int
    stem: str
    options: list[AssessmentOption] = Field(default_factory=list)


class AssessmentResponse(BaseModel):
    assessment_id: str
    items: list[AssessmentPublicItem] = Field(default_factory=list)


class AnswerSubmission(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=32)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=3600)


class PracticeResult(BaseModel):
    task_id: str
    score: float = Field(ge=0.0, le=1.0)
    log: Optional[str] = None


class AssessmentSubmit(BaseModel):
    answers: list[AnswerSubmission] = Field(default_factory=list, max_length=100)
    practice_results: list[PracticeResult] = Field(default_factory=list)


class AssessmentItemResult(BaseModel):
    item_id: str
    skill_id: str
    stem: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str = ""
    error_tags: list[str] = Field(default_factory=list)


class AssessmentSubmitResponse(BaseModel):
    status: str
    diagnosis_id: str
    mastery: dict = Field(default_factory=dict)
    knowledge_gaps: list[str] = Field(default_factory=list)
    recommended_level: str = "basic"
    item_results: list[AssessmentItemResult] = Field(default_factory=list)
