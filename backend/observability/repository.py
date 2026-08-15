"""Read-only data access for the observability console.

No mutation methods live here.  The router uses a session that is rolled back on
exit, even though only SELECT statements are issued.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis_session import DiagnosisResponse, DiagnosisSession
from app.models.resource import GeneratedResource
from app.models.workflow import AgentRun, WorkflowSession


@dataclass
class WorkflowBundle:
    session: WorkflowSession
    runs: list[AgentRun]
    diagnosis_session: DiagnosisSession | None
    diagnosis_responses: list[DiagnosisResponse]
    resource: GeneratedResource | None


async def list_recent_workflows(db: AsyncSession, limit: int = 20) -> list[WorkflowSession]:
    result = await db.execute(
        select(WorkflowSession)
        .order_by(WorkflowSession.updated_at.desc(), WorkflowSession.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().all())


async def read_workflow_bundle(db: AsyncSession, workflow_id: str) -> WorkflowBundle | None:
    session = await db.get(WorkflowSession, workflow_id)
    if session is None:
        return None

    runs = list((await db.execute(
        select(AgentRun)
        .where(AgentRun.workflow_id == workflow_id)
        .order_by(AgentRun.started_at.asc(), AgentRun.id.asc())
    )).scalars().all())

    diagnosis_session = (await db.execute(
        select(DiagnosisSession)
        .where(DiagnosisSession.workflow_id == workflow_id)
        .order_by(DiagnosisSession.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    diagnosis_responses: list[DiagnosisResponse] = []
    if diagnosis_session is not None:
        diagnosis_responses = list((await db.execute(
            select(DiagnosisResponse)
            .where(DiagnosisResponse.session_id == diagnosis_session.id)
            .order_by(DiagnosisResponse.answered_at.asc(), DiagnosisResponse.id.asc())
        )).scalars().all())

    resource = (await db.execute(
        select(GeneratedResource)
        .where(GeneratedResource.workflow_id == workflow_id)
        .order_by(GeneratedResource.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    return WorkflowBundle(
        session=session,
        runs=runs,
        diagnosis_session=diagnosis_session,
        diagnosis_responses=diagnosis_responses,
        resource=resource,
    )
