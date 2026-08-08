"""Per-concept Beta-Bernoulli mastery state.

One row is the learner's posterior belief about a single concept. The Beta
parameters are the durable state; ``mastery_probability`` and ``uncertainty``
are derived snapshots kept denormalised so read endpoints never recompute the
whole posterior.
"""

import uuid

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, UniqueConstraint, Index

from app.core.database import Base
from app.core.time import utc_now


class LearnerConceptMastery(Base):
    __tablename__ = "learner_concept_mastery"

    id = Column(String, primary_key=True, default=lambda: f"lcm_{uuid.uuid4().hex[:8]}")
    learner_id = Column(String(100), ForeignKey("learner_profiles.id"), nullable=False, index=True)
    concept_id = Column(String(100), nullable=False, index=True)
    skill_id = Column(String(100), nullable=True, index=True)

    # Beta(alpha, beta) posterior over "probability this learner answers a
    # question about this concept correctly".
    alpha = Column(Float, nullable=False, default=1.0)
    beta = Column(Float, nullable=False, default=1.0)

    mastery_probability = Column(Float, nullable=False, default=0.5)
    uncertainty = Column(Float, nullable=False, default=1.0)

    attempt_count = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    last_response_time = Column(Float, nullable=True)
    last_difficulty = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("learner_id", "concept_id", name="uq_learner_concept"),
        Index("ix_learner_concept_mastery_lookup", "learner_id", "skill_id"),
    )
