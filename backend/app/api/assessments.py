"""Diagnostic assessment endpoints with auditable, race-safe scoring."""
import uuid

from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.time import utc_now
from app.schemas.assessment import (
    AssessmentCreate, AssessmentResponse, AssessmentPublicItem,
    AssessmentSubmit, AssessmentSubmitResponse,
)
from app.models.learner import LearnerProfile
from app.models.skill_graph import SkillNode
from app.models.assessment import AssessmentSession, AssessmentItem, AssessmentAttempt, MasteryState
from app.services.mastery_service import upsert_mastery

router = APIRouter(prefix="/api/v1/assessments", tags=["assessments"])


@router.post("", response_model=AssessmentResponse, status_code=201)
async def create_assessment(data: AssessmentCreate, db: AsyncSession = Depends(get_db)):
    learner = await db.get(LearnerProfile, data.learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    query = (
        select(AssessmentItem)
        .join(SkillNode, AssessmentItem.skill_id == SkillNode.id)
        .where(SkillNode.domain_id == data.domain_id)
        .order_by(AssessmentItem.difficulty, AssessmentItem.id)
        .limit(10)
    )
    items = list((await db.execute(query)).scalars().all())
    if not items:
        raise HTTPException(status_code=404, detail="Assessment bank is empty")

    session = AssessmentSession(
        learner_id=data.learner_id,
        domain_id=data.domain_id,
        target_goal=data.target_goal,
        status="created",
        result_json={"assigned_item_ids": [item.id for item in items]},
    )
    db.add(session)
    await db.flush()

    return AssessmentResponse(
        assessment_id=session.id,
        items=[
            AssessmentPublicItem(
                item_id=item.id,
                skill_id=item.skill_id,
                type=item.question_type,
                difficulty=item.difficulty,
                stem=(item.content_json or {}).get("stem", ""),
                options=(item.content_json or {}).get("options", []),
            )
            for item in items
        ],
    )


@router.post("/{assessment_id}/submit", response_model=AssessmentSubmitResponse)
async def submit_assessment(
    assessment_id: str,
    data: AssessmentSubmit,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(AssessmentSession, assessment_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if session.status == "completed" and session.result_json:
        return AssessmentSubmitResponse(status="completed", **session.result_json)

    if data.practice_results:
        raise HTTPException(
            status_code=422,
            detail="Initial diagnosis does not accept client-reported practice scores; complete resource practice instead",
        )

    answer_ids = [answer.item_id for answer in data.answers]
    if not answer_ids:
        raise HTTPException(status_code=422, detail="At least one answer is required")
    if len(answer_ids) != len(set(answer_ids)):
        raise HTTPException(status_code=422, detail="Duplicate assessment item")
    assigned_ids = set((session.result_json or {}).get("assigned_item_ids", []))
    if not assigned_ids:
        assigned_ids = set((await db.execute(
            select(AssessmentItem.id)
            .join(SkillNode, AssessmentItem.skill_id == SkillNode.id)
            .where(SkillNode.domain_id == session.domain_id)
            .order_by(AssessmentItem.difficulty, AssessmentItem.id)
            .limit(10)
        )).scalars().all())
    if set(answer_ids) != assigned_ids:
        raise HTTPException(status_code=422, detail="All assigned assessment items must be answered exactly once")

    item_rows = list((await db.execute(
        select(AssessmentItem, SkillNode)
        .join(SkillNode, AssessmentItem.skill_id == SkillNode.id)
        .where(
            AssessmentItem.id.in_(answer_ids),
            SkillNode.domain_id == session.domain_id,
        )
    )).all())
    item_map = {item.id: (item, skill) for item, skill in item_rows}

    per_skill_correct: dict[str, list[float]] = defaultdict(list)
    per_skill_time: dict[str, list[float]] = defaultdict(list)
    error_tags: set[str] = set()
    item_results: list[dict] = []

    for answer in data.answers:
        row = item_map.get(answer.item_id)
        if row is None:
            raise HTTPException(status_code=422, detail=f"Unknown item for domain: {answer.item_id}")
        item, _skill = row
        normalized_answer = answer.answer.strip().upper()
        option_keys = {
            str(option.get("key", "")).strip().upper()
            for option in (item.content_json or {}).get("options", [])
        }
        if normalized_answer not in option_keys:
            raise HTTPException(status_code=422, detail=f"Invalid option for item {answer.item_id}")
        is_correct = normalized_answer == item.correct_answer.strip().upper()
        duration = max(0, answer.duration_seconds or 0)
        time_score = max(0.0, min(1.0, 1.0 - duration / 120.0))
        per_skill_correct[item.skill_id].append(1.0 if is_correct else 0.0)
        per_skill_time[item.skill_id].append(time_score)
        item_error_tags = [] if is_correct else (item.error_tags or [])
        if not is_correct:
            error_tags.update(item_error_tags)

        db.add(AssessmentAttempt(
            assessment_id=session.id,
            learner_id=session.learner_id,
            item_id=item.id,
            user_answer=normalized_answer,
            is_correct=is_correct,
            duration_seconds=duration,
            score=1.0 if is_correct else 0.0,
            error_tags=item_error_tags,
        ))
        item_results.append({
            "item_id": item.id,
            "skill_id": item.skill_id,
            "stem": (item.content_json or {}).get("stem", ""),
            "user_answer": normalized_answer,
            "correct_answer": item.correct_answer,
            "is_correct": is_correct,
            "explanation": (item.content_json or {}).get("explanation", ""),
            "error_tags": item_error_tags,
        })

    skill_ids = set(per_skill_correct)
    previous_rows = list((await db.execute(
        select(MasteryState).where(
            MasteryState.learner_id == session.learner_id,
            MasteryState.skill_id.in_(skill_ids),
        )
    )).scalars().all())
    previous_map = {row.skill_id: row for row in previous_rows}

    mastery_result: dict[str, dict] = {}
    for skill_id in skill_ids:
        previous = previous_map.get(skill_id)
        history = (previous.mastery_score / 100.0) if previous else 0.0
        accuracy = sum(per_skill_correct[skill_id]) / len(per_skill_correct[skill_id])
        time_performance = sum(per_skill_time[skill_id]) / len(per_skill_time[skill_id])
        mastery_score = round(100.0 * (
            0.65 * accuracy + 0.15 * time_performance + 0.20 * history
        ), 1)
        evidence_count = len(per_skill_correct[skill_id])
        confidence = round(min(0.95, 0.55 + 0.05 * evidence_count), 2)
        await upsert_mastery(
            db,
            learner_id=session.learner_id,
            skill_id=skill_id,
            mastery_score=mastery_score,
            confidence=confidence,
            evidence_count=evidence_count,
        )
        mastery_result[skill_id] = {"score": mastery_score, "confidence": confidence}

    name_rows = list((await db.execute(
        select(SkillNode).where(SkillNode.id.in_(skill_ids))
    )).scalars().all())
    name_map = {row.id: row.name for row in name_rows}
    knowledge_gaps = [
        name_map.get(skill_id, skill_id)
        for skill_id, value in mastery_result.items()
        if value["score"] < 60
    ]
    avg_score = sum(value["score"] for value in mastery_result.values()) / max(1, len(mastery_result))
    recommended_level = "basic" if avg_score < 60 else ("intermediate" if avg_score < 80 else "advanced")
    diagnosis_id = f"diag_{uuid.uuid4().hex[:8]}"

    result_json = {
        "diagnosis_id": diagnosis_id,
        "mastery": mastery_result,
        "knowledge_gaps": knowledge_gaps,
        "recommended_level": recommended_level,
        "error_tags": sorted(error_tags),
        "item_results": item_results,
    }
    session.status = "completed"
    session.completed_at = utc_now()
    session.result_json = result_json
    await db.flush()

    return AssessmentSubmitResponse(status="completed", **result_json)
