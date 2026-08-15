"""Read-only observability HTTP endpoints.

The core workflow never calls these endpoints and never imports this package.
The only integration point is ``app.main`` mounting this router on the normal
backend port.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory

from .human_log import render_human_log
from .presenter import build_observability_view, recent_workflow_view
from .repository import list_recent_workflows, read_workflow_bundle


router = APIRouter(tags=["observability"])
_DASHBOARD = Path(__file__).with_name("dashboard.html")


async def get_read_db():
    """A deliberately rollback-only session for visualization reads."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@router.get("/observability", response_class=HTMLResponse, include_in_schema=False)
async def observability_dashboard() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD.read_text(encoding="utf-8"))


@router.get("/api/observability/workflows/recent")
async def recent_workflows(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
):
    sessions = await list_recent_workflows(db, limit=limit)
    return {
        "read_only": True,
        "items": [recent_workflow_view(session) for session in sessions],
    }


@router.get("/api/observability/workflows/{workflow_id}")
async def workflow_observability(
    workflow_id: str,
    db: AsyncSession = Depends(get_read_db),
):
    bundle = await read_workflow_bundle(db, workflow_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return build_observability_view(bundle)


@router.get("/api/observability/workflows/{workflow_id}/human-log", response_class=PlainTextResponse)
async def workflow_human_log(
    workflow_id: str,
    db: AsyncSession = Depends(get_read_db),
):
    bundle = await read_workflow_bundle(db, workflow_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return PlainTextResponse(render_human_log(build_observability_view(bundle)), media_type="text/plain; charset=utf-8")


@router.get("/api/observability/workflows/{workflow_id}/export")
async def workflow_export(
    workflow_id: str,
    db: AsyncSession = Depends(get_read_db),
):
    """Return both machine JSON and a human log without writing into core storage."""
    bundle = await read_workflow_bundle(db, workflow_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    view = build_observability_view(bundle)
    return {
        "workflow_id": workflow_id,
        "human_log": render_human_log(view),
        "trace_json": view,
        "trace_json_text": json.dumps(view, ensure_ascii=False, indent=2),
    }
