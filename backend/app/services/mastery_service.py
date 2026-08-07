"""Race-safe mastery updates shared by assessment and resource feedback flows."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.assessment import MasteryState


async def upsert_mastery(
    db: AsyncSession,
    *,
    learner_id: str,
    skill_id: str,
    mastery_score: float,
    confidence: float,
    evidence_count: int,
) -> None:
    """Insert or atomically replace one learner-skill mastery snapshot."""
    values = {
        "id": f"mastery_{uuid.uuid4().hex[:8]}",
        "learner_id": learner_id,
        "skill_id": skill_id,
        "mastery_score": round(max(0.0, min(100.0, mastery_score)), 1),
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "evidence_count": max(1, evidence_count),
        "last_updated": utc_now(),
    }
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "sqlite":
        statement = sqlite_insert(MasteryState).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[MasteryState.learner_id, MasteryState.skill_id],
            set_={
                "mastery_score": statement.excluded.mastery_score,
                "confidence": statement.excluded.confidence,
                "evidence_count": statement.excluded.evidence_count,
                "last_updated": statement.excluded.last_updated,
            },
        )
        await db.execute(statement)
        return
    if dialect == "postgresql":
        statement = postgresql_insert(MasteryState).values(**values)
        statement = statement.on_conflict_do_update(
            constraint="uq_learner_skill",
            set_={
                "mastery_score": statement.excluded.mastery_score,
                "confidence": statement.excluded.confidence,
                "evidence_count": statement.excluded.evidence_count,
                "last_updated": statement.excluded.last_updated,
            },
        )
        await db.execute(statement)
        return

    previous = (await db.execute(
        select(MasteryState).where(
            MasteryState.learner_id == learner_id,
            MasteryState.skill_id == skill_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if previous is None:
        db.add(MasteryState(**values))
    else:
        previous.mastery_score = values["mastery_score"]
        previous.confidence = values["confidence"]
        previous.evidence_count = values["evidence_count"]
        previous.last_updated = values["last_updated"]
