"""Workflow and agent run database models."""

import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from app.core.database import Base


from app.core.time import utc_now
class WorkflowSession(Base):
    __tablename__ = "workflow_sessions"

    id = Column(String, primary_key=True, default=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    domain_id = Column(String(100), nullable=False)
    target_goal = Column(String(500), nullable=True)
    current_state = Column(String(50), nullable=False, default="CREATED")
    revision_count = Column(Integer, nullable=False, default=0)
    state_data = Column(JSON, nullable=True)  # Full workflow state snapshot
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=lambda: f"run_{uuid.uuid4().hex[:8]}")
    workflow_id = Column(String(100), ForeignKey("workflow_sessions.id"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)
    input_json = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending / running / success / failed
    confidence = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
