"""Workflow API schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    learner_id: str = Field(min_length=1, max_length=100)
    domain_id: str = Field(min_length=1, max_length=100)
    assessment_id: Optional[str] = Field(default=None, max_length=100)
    target_goal: Optional[str] = Field(default=None, max_length=500)
    target_skill_id: Optional[str] = Field(default=None, max_length=100)
    version_filter: Optional[str] = Field(default=None, max_length=50, description="ROS/knowledge version constraint, e.g. humble")


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


class WorkflowSnapshot(BaseModel):
    status: WorkflowStatus
    trace: WorkflowTrace
