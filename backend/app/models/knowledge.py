"""Knowledge base database models."""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from app.core.database import Base


from app.core.time import utc_now
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String, primary_key=True, default=lambda: f"doc_{uuid.uuid4().hex[:8]}")
    title = Column(String(500), nullable=False)
    source_url = Column(String(1000), nullable=True)
    source_type = Column(String(50), nullable=False, default="local")  # local / web
    domain_id = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=True)
    file_hash = Column(String(64), nullable=True)
    verification_status = Column(String(50), nullable=False, default="pending")  # pending / verified / rejected
    created_at = Column(DateTime, default=utc_now, nullable=False)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String, primary_key=True, default=lambda: f"chunk_{uuid.uuid4().hex[:8]}")
    document_id = Column(String(100), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    skill_id = Column(String(100), ForeignKey("skill_nodes.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    section = Column(String(200), nullable=True)
    page_number = Column(Integer, nullable=True)
    version = Column(String(50), nullable=True)
    verification_status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=utc_now, nullable=False)
