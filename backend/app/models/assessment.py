"""Assessment-related database models."""

import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Text, UniqueConstraint
from app.core.database import Base


from app.core.time import utc_now
class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id = Column(String, primary_key=True, default=lambda: f"assessment_{uuid.uuid4().hex[:8]}")
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    domain_id = Column(String(100), nullable=False, index=True)
    target_goal = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default="created")
    result_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class AssessmentItem(Base):
    __tablename__ = "assessment_items"

    id = Column(String, primary_key=True, default=lambda: f"q_{uuid.uuid4().hex[:8]}")
    skill_id = Column(String(100), ForeignKey("skill_nodes.id"), nullable=False, index=True)
    question_type = Column(String(50), nullable=False, default="single_choice")
    difficulty = Column(Integer, nullable=False, default=1)
    content_json = Column(JSON, nullable=False)
    correct_answer = Column(String(500), nullable=False)
    error_tags = Column(JSON, nullable=True)
    scoring_rules = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(String, primary_key=True, default=lambda: f"attempt_{uuid.uuid4().hex[:8]}")
    assessment_id = Column(String(100), ForeignKey("assessment_sessions.id"), nullable=True, index=True)
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    item_id = Column(String(100), ForeignKey("assessment_items.id"), nullable=False)
    user_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    error_tags = Column(JSON, nullable=True)
    attempted_at = Column(DateTime, default=utc_now, nullable=False)


class MasteryState(Base):
    __tablename__ = "mastery_states"

    id = Column(String, primary_key=True, default=lambda: f"mastery_{uuid.uuid4().hex[:8]}")
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    skill_id = Column(String(100), ForeignKey("skill_nodes.id"), nullable=False)
    mastery_score = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=True)
    evidence_count = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("learner_id", "skill_id", name="uq_learner_skill"),
    )
