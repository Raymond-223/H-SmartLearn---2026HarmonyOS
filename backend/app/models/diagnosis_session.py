"""One adaptive diagnosis run.

Unlike :class:`~app.models.assessment.AssessmentSession`, which hands out a
fixed 10-item paper, a diagnosis session is item-by-item: every answer updates
the learner model and the next item is chosen from the posterior.
"""

import uuid

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey

from app.core.database import Base
from app.core.time import utc_now


class DiagnosisSession(Base):
    __tablename__ = "diagnosis_sessions"

    id = Column(String, primary_key=True, default=lambda: f"diagsess_{uuid.uuid4().hex[:8]}")
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    domain_id = Column(String(100), nullable=False, index=True)
    target_skill_id = Column(String(100), nullable=True)
    # Set when the run is driving a workflow that paused for adaptive diagnosis;
    # the workflow resumes at PATH_PLANNING once this session completes.
    workflow_id = Column(String(100), ForeignKey("workflow_sessions.id"), nullable=True, index=True)

    answered_item_ids = Column(JSON, nullable=False, default=list)
    tested_concept_ids = Column(JSON, nullable=False, default=list)
    question_count = Column(Integer, nullable=False, default=0)
    # {"consecutive_hard": int, "elapsed_seconds": float, "level": float}
    fatigue_state = Column(JSON, nullable=False, default=dict)

    status = Column(String(30), nullable=False, default="in_progress")
    result_json = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    finished_at = Column(DateTime, nullable=True)


class DiagnosisResponse(Base):
    """Item-level audit trail: what was asked, why, and what it changed."""

    __tablename__ = "diagnosis_responses"

    id = Column(String, primary_key=True, default=lambda: f"diagresp_{uuid.uuid4().hex[:8]}")
    session_id = Column(String(100), ForeignKey("diagnosis_sessions.id"), nullable=False, index=True)
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    item_id = Column(String(100), nullable=False)
    skill_id = Column(String(100), nullable=True)
    concept_ids = Column(JSON, nullable=False, default=list)
    user_answer = Column(String(500), nullable=True)
    is_correct = Column(Boolean, nullable=False, default=False)
    response_time_sec = Column(Float, nullable=True)
    difficulty = Column(Integer, nullable=True)
    selection_score_json = Column(JSON, nullable=True)
    answered_at = Column(DateTime, default=utc_now, nullable=False)
