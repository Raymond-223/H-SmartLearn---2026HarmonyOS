"""Atomic, idempotent resource-feedback persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.feedback import FeedbackRecord


async def create_feedback_once(
    db: AsyncSession,
    *,
    learner_id: str,
    resource_id: str,
    correct_rate: float,
    practice_score: float,
    subjective_difficulty: str,
    error_tags: list[str],
) -> bool:
    """Insert one feedback record and return False when it already exists."""
    values = {
        "id": f"fb_{uuid.uuid4().hex[:8]}",
        "learner_id": learner_id,
        "resource_id": resource_id,
        "correct_rate": max(0.0, min(1.0, correct_rate)),
        "practice_score": max(0.0, min(1.0, practice_score)),
        "subjective_difficulty": subjective_difficulty,
        "error_tags": error_tags,
        "feedback_time": utc_now(),
    }
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "sqlite":
        statement = sqlite_insert(FeedbackRecord).values(**values).on_conflict_do_nothing(
            index_elements=[FeedbackRecord.learner_id, FeedbackRecord.resource_id]
        )
        result = await db.execute(statement)
        return bool(result.rowcount)
    if dialect == "postgresql":
        statement = postgresql_insert(FeedbackRecord).values(**values).on_conflict_do_nothing(
            constraint="uq_feedback_learner_resource"
        )
        result = await db.execute(statement)
        return bool(result.rowcount)

    existing = (await db.execute(
        select(FeedbackRecord).where(
            FeedbackRecord.learner_id == learner_id,
            FeedbackRecord.resource_id == resource_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if existing is not None:
        return False
    db.add(FeedbackRecord(**values))
    await db.flush()
    return True
