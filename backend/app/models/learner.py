"""Learner-related database models."""

import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
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

    # ------------------------------------------------------- learner model cache
    #
    # The authoritative per-concept posterior lives in `learner_concept_mastery`,
    # one row per concept, and is rewritten on every answer. These columns are a
    # denormalised snapshot of the last completed diagnosis so the profile screen
    # and the planner can render an ability picture in a single read instead of
    # re-aggregating 50 concept rows.
    ability_profile = Column(JSON, nullable=True)
    # {domain_id: {concept_id: {"mastery_probability": float, "uncertainty": float}}}
    concept_mastery = Column(JSON, nullable=True)
    # Mean normalised uncertainty of the last snapshot; high means "diagnose more".
    uncertainty = Column(Float, nullable=True)
    # Recurring error tags harvested from wrong answers, most frequent first.
    misconceptions = Column(JSON, nullable=True)
    # Learning context that shapes generation but is not evidence: device, ROS
    # distro, available hardware, preferred language, time of day, and so on.
    context = Column(JSON, nullable=True)
    last_diagnosed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
