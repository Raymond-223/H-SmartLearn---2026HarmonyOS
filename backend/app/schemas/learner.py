"""Learner API schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class LearnerCreate(BaseModel):
    education: str = Field(min_length=1, max_length=100)
    major: Optional[str] = Field(default=None, max_length=200)
    target_role: str = Field(min_length=1, max_length=200)
    weekly_hours: int = Field(default=6, ge=1, le=80)
    preferences: dict = Field(default_factory=dict)
    context: dict = Field(
        default_factory=dict,
        description="Learning context (device, ROS distro, hardware, language) that shapes generation.",
    )


class LearnerUpdate(BaseModel):
    """All profile fields are optional so the endpoint supports partial updates."""

    education: Optional[str] = Field(default=None, min_length=1, max_length=100)
    major: Optional[str] = Field(default=None, min_length=1, max_length=200)
    target_role: Optional[str] = Field(default=None, min_length=1, max_length=200)
    weekly_hours: Optional[int] = Field(default=None, ge=1, le=80)
    preferences: Optional[dict] = None
    context: Optional[dict] = None


class LearnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    learner_id: str


class LearnerDetail(BaseModel):
    learner_id: str
    education: Optional[str] = None
    major: Optional[str] = None
    target_role: Optional[str] = None
    weekly_hours: Optional[int] = None
    preferences: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    # Snapshot of the last completed diagnosis; empty until one runs.
    ability_profile: Optional[dict] = None
    uncertainty: Optional[float] = None
    misconceptions: list[str] = Field(default_factory=list)
    last_diagnosed_at: Optional[datetime] = None


class LearnerReport(BaseModel):
    learner_id: str
    overall_mastery: float = 0
    domain: str = "ros2_robotics"
    skill_mastery: list[dict] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    difficulty_curve: list[dict] = Field(default_factory=list)
    learning_path: list[dict] = Field(default_factory=list)
    progress_history: list[dict] = Field(default_factory=list)
    recommended_resources: list[str] = Field(default_factory=list)
