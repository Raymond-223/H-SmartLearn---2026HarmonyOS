"""Resource and review database models."""

import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from app.core.database import Base


from app.core.time import utc_now
class GeneratedResource(Base):
    __tablename__ = "generated_resources"

    id = Column(String, primary_key=True, default=lambda: f"res_{uuid.uuid4().hex[:8]}")
    workflow_id = Column(String(100), ForeignKey("workflow_sessions.id"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)  # lecture / practice_guide / graded_test
    skill_id = Column(String(100), ForeignKey("skill_nodes.id"), nullable=True)
    difficulty = Column(String(20), nullable=False, default="basic")  # basic / intermediate / advanced
    content_json = Column(JSON, nullable=False)
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="draft")  # draft / published / archived
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ResourceCitation(Base):
    __tablename__ = "resource_citations"

    id = Column(String, primary_key=True, default=lambda: f"cite_{uuid.uuid4().hex[:8]}")
    resource_id = Column(String(100), ForeignKey("generated_resources.id"), nullable=False, index=True)
    evidence_id = Column(String(100), nullable=False)
    claim_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id = Column(String, primary_key=True, default=lambda: f"review_{uuid.uuid4().hex[:8]}")
    resource_id = Column(String(100), ForeignKey("generated_resources.id"), nullable=False, index=True)
    review_round = Column(Integer, nullable=False, default=1)
    factuality_score = Column(Float, nullable=True)
    coverage_score = Column(Float, nullable=True)
    difficulty_score = Column(Float, nullable=True)
    actionability_score = Column(Float, nullable=True)
    decision = Column(String(50), nullable=False)  # approve / revise / reject
    issues_json = Column(JSON, nullable=True)
    revision_instructions = Column(JSON, nullable=True)
    reviewed_at = Column(DateTime, default=utc_now, nullable=False)
