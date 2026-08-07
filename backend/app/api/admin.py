"""Knowledge-base administration endpoints for the competition demo.

Routes are protected by X-Admin-Key when ADMIN_API_KEY is configured.
"""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from typing import Iterable

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.domain_package_service import load_skill_nodes

async def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Require X-Admin-Key only when ADMIN_API_KEY is configured."""
    expected = settings.admin_api_key
    if not expected:
        if settings.debug:
            return
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY must be configured in production")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)
UPLOAD_ROOT = Path(settings.storage_path).resolve() / "uploads"
ALLOWED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}


def _split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> Iterable[str]:
    """Split cleaned text into deterministic overlapping chunks."""
    clean = "\n".join(line.strip() for line in text.replace("\r\n", "\n").split("\n"))
    clean = "\n".join(line for line in clean.split("\n") if line)
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        if end < len(clean):
            boundary = max(clean.rfind("。", start, end), clean.rfind("\n", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = clean[start:end].strip()
        if chunk:
            yield chunk
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)


def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise HTTPException(status_code=501, detail="PDF解析依赖未安装，请执行 pip install pypdf") from exc
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(encoding="utf-8")


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    domain_id: str = Form(default="ros2_robotics"),
    version: str = Form(default="humble"),
    db: AsyncSession = Depends(get_db),
):
    """Store an uploaded PDF/Markdown/text document in pending state."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="仅支持 PDF、Markdown 和 TXT 文件")

    try:
        load_skill_nodes(domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="未知领域包") from exc

    payload = await file.read(settings.max_upload_bytes + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {settings.max_upload_bytes // (1024 * 1024)} MB")

    digest = hashlib.sha256(payload).hexdigest()
    existing = (await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.file_hash == digest)
    )).scalar_one_or_none()
    if existing:
        return {
            "status": "duplicate",
            "document_id": existing.id,
            "verification_status": existing.verification_status,
        }

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = f"{digest[:16]}{suffix}"
    target = UPLOAD_ROOT / safe_name
    target.write_bytes(payload)

    document = KnowledgeDocument(
        title=(title or Path(file.filename or safe_name).stem).strip(),
        source_url=target.as_uri(),
        source_type="local",
        domain_id=domain_id,
        version=version,
        file_hash=digest,
        verification_status="pending",
    )
    db.add(document)
    await db.flush()
    return {
        "status": "uploaded",
        "document_id": document.id,
        "verification_status": document.verification_status,
    }


@router.post("/documents/{doc_id}/parse")
async def parse_document(
    doc_id: str,
    skill_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Extract text and create pending chunks; parsing never auto-verifies content."""
    document = await db.get(KnowledgeDocument, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    if not document.source_url or not document.source_url.startswith("file://"):
        raise HTTPException(status_code=422, detail="当前仅支持解析本地上传文档")

    path = Path(document.source_url.removeprefix("file://"))
    if not path.exists():
        raise HTTPException(status_code=404, detail="源文件已丢失")

    try:
        text = _extract_text(path)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="文本文件必须使用 UTF-8 编码") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="未能从文档提取到正文")

    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
    chunks = list(_split_text(text))
    for index, content in enumerate(chunks, start=1):
        db.add(KnowledgeChunk(
            document_id=doc_id,
            skill_id=skill_id,
            content=content,
            section=f"chunk-{index}",
            version=document.version,
            verification_status="pending",
        ))
    await db.flush()
    return {"status": "parsed", "document_id": doc_id, "chunks": len(chunks)}


@router.post("/documents/{doc_id}/verify")
async def verify_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Promote a parsed document and all of its chunks to verified state."""
    document = await db.get(KnowledgeDocument, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    chunk_rows = (await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)
    )).scalars().all()
    if not chunk_rows:
        raise HTTPException(status_code=409, detail="文档尚未切片，不能审核通过")
    document.verification_status = "verified"
    for chunk in chunk_rows:
        chunk.verification_status = "verified"
    return {"status": "verified", "document_id": doc_id, "chunks": len(chunk_rows)}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Delete document metadata, chunks, and the local source file when present."""
    document = await db.get(KnowledgeDocument, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    if document.source_url and document.source_url.startswith("file://"):
        Path(document.source_url.removeprefix("file://")).unlink(missing_ok=True)
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
    await db.delete(document)
    return {"status": "deleted", "document_id": doc_id}


@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(min_length=1),
    domain_id: str = Query(default="ros2_robotics"),
    verified_only: bool = Query(default=True),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Keyword fallback search used by admins to inspect indexed chunks."""
    statement = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(
            KnowledgeDocument.domain_id == domain_id,
            or_(KnowledgeChunk.content.ilike(f"%{q}%"), KnowledgeDocument.title.ilike(f"%{q}%")),
        )
        .limit(limit)
    )
    if verified_only:
        statement = statement.where(
            KnowledgeDocument.verification_status.in_(("verified", "trusted_source")),
            KnowledgeChunk.verification_status.in_(("verified", "trusted_source")),
        )
    rows = (await db.execute(statement)).all()
    return {
        "query": q,
        "results": [
            {
                "evidence_id": chunk.id,
                "document_id": document.id,
                "title": document.title,
                "source_url": document.source_url,
                "version": chunk.version,
                "content": chunk.content,
                "verification_status": chunk.verification_status,
            }
            for chunk, document in rows
        ],
    }
