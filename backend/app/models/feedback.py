"""Feedback database model."""

import uuid
from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey, UniqueConstraint
from app.core.database import Base


from app.core.time import utc_now
class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id = Column(String, primary_key=True, default=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    resource_id = Column(String(100), ForeignKey("generated_resources.id"), nullable=False)
    correct_rate = Column(Float, nullable=True)       # 0–1
    practice_score = Column(Float, nullable=True)     # 0–1
    subjective_difficulty = Column(String(20), nullable=True)  # too_easy / appropriate / too_hard
    error_tags = Column(JSON, nullable=True)
    feedback_time = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("learner_id", "resource_id", name="uq_feedback_learner_resource"),
    )
