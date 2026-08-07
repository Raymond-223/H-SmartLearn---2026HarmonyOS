"""Skill graph database models (nodes + edges)."""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from app.core.database import Base


from app.core.time import utc_now
class SkillNode(Base):
    __tablename__ = "skill_nodes"

    id = Column(String, primary_key=True, default=lambda: f"skill_{uuid.uuid4().hex[:8]}")
    domain_id = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    difficulty = Column(Integer, nullable=False, default=1)  # 1–5
    estimated_minutes = Column(Integer, nullable=True)
    objectives_json = Column(JSON, nullable=True)
    criteria_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class SkillEdge(Base):
    __tablename__ = "skill_edges"

    id = Column(String, primary_key=True, default=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    from_skill_id = Column(String(100), ForeignKey("skill_nodes.id"), nullable=False, index=True)
    to_skill_id = Column(String(100), ForeignKey("skill_nodes.id"), nullable=False, index=True)
    relation_type = Column(String(50), nullable=False, default="prerequisite")  # prerequisite / related
    created_at = Column(DateTime, default=utc_now, nullable=False)
