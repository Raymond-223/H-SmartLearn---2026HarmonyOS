"""Learner-related database models."""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, JSON
from app.core.database import Base


from app.core.time import utc_now
class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    id = Column(String, primary_key=True, default=lambda: f"learner_{uuid.uuid4().hex[:8]}")
    education = Column(String(100), nullable=True)
    major = Column(String(100), nullable=True)
    target_role = Column(String(200), nullable=True)
    weekly_hours = Column(Integer, nullable=True)
    preference_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
