"""Diagnostic assessment endpoints with auditable, race-safe scoring."""
import uuid

from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.time import utc_now
from app.services.learner_model_service import LearnerModelService
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
    per_skill_observations: dict[str, list[tuple[bool, int]]] = defaultdict(list)
    error_tags: set[str] = set()
    item_results: list[dict] = []
    skills_with_concepts: set[str] = set()
    learner_model = LearnerModelService(db, domain_id=session.domain_id)

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
        per_skill_observations[item.skill_id].append((is_correct, item.difficulty))
        item_error_tags = [] if is_correct else (item.error_tags or [])
        if not is_correct:
            error_tags.update(item_error_tags)

        concept_ids = [str(cid) for cid in (item.content_json or {}).get("concept_ids", []) if cid]
        if concept_ids:
            skills_with_concepts.add(item.skill_id)
            await learner_model.update_from_answer(
                learner_id=session.learner_id,
                concept_ids=concept_ids,
                is_correct=is_correct,
                difficulty=item.difficulty,
                response_time=float(duration) if duration else None,
                expected_time=(item.content_json or {}).get("estimated_seconds"),
            )

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
            "difficulty": item.difficulty,
            "concept_ids": concept_ids,
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

    # Fixed assessments share the same Bayesian semantics as the adaptive path.
    # This keeps the legacy assessment API useful while the richer concept-level
    # LearnerModelService remains the source of truth for adaptive diagnosis.
    from app.services.bkt_service import (
        bkt_sequence, bkt_confidence, bkt_prior_from_existing,
    )

    mastery_result: dict[str, dict] = {}
    for skill_id in skill_ids:
        if skill_id in skills_with_concepts:
            continue
        previous = previous_map.get(skill_id)
        prior = bkt_prior_from_existing(previous.mastery_score if previous else None)
        observations = per_skill_observations.get(skill_id, [])
        if observations:
            p_know = bkt_sequence(observations, prior=prior)
            evidence_count = len(observations)
        else:
            # Defensive fallback for malformed/legacy item rows.
            accuracy = sum(per_skill_correct[skill_id]) / len(per_skill_correct[skill_id])
            time_performance = sum(per_skill_time[skill_id]) / len(per_skill_time[skill_id])
            history = (previous.mastery_score / 100.0) if previous else 0.0
            p_know = 0.65 * accuracy + 0.15 * time_performance + 0.20 * history
            evidence_count = len(per_skill_correct[skill_id])

        mastery_score = round(100.0 * p_know, 1)
        confidence = bkt_confidence(p_know, evidence_count)
        await upsert_mastery(
            db,
            learner_id=session.learner_id,
            skill_id=skill_id,
            mastery_score=mastery_score,
            confidence=confidence,
            evidence_count=evidence_count,
        )
        mastery_result[skill_id] = {
            "score": mastery_score,
            "confidence": confidence,
            "evidence_count": evidence_count,
        }

    # One source of truth: if fixed-assessment items carry concept_ids, roll the
    # persistent concept posteriors back up to the legacy skill dashboard. BKT
    # remains only as compatibility fallback for legacy items without concepts.
    for skill_id in skill_ids:
        skill_state = await learner_model.get_skill_state(session.learner_id, skill_id)
        if skill_state.tested_concept_count > 0:
            mastery_result[skill_id] = {
                "score": round(100.0 * skill_state.mastery_probability, 1),
                "confidence": round(1.0 - skill_state.uncertainty, 3),
                "evidence_count": skill_state.attempt_count,
                "tested_concept_count": skill_state.tested_concept_count,
            }
            await upsert_mastery(
                db,
                learner_id=session.learner_id,
                skill_id=skill_id,
                mastery_score=mastery_result[skill_id]["score"],
                confidence=mastery_result[skill_id]["confidence"],
                evidence_count=mastery_result[skill_id]["evidence_count"],
            )

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

    misconception_counts: dict[str, int] = {}
    for result in item_results:
        if not result["is_correct"]:
            for tag in result.get("error_tags", []):
                misconception_counts[tag] = misconception_counts.get(tag, 0) + 1
    misconceptions = sorted(
        [{"tag": tag, "count": count} for tag, count in misconception_counts.items()],
        key=lambda item: item["count"],
        reverse=True,
    )

    result_json = {
        "diagnosis_id": diagnosis_id,
        "mastery": mastery_result,
        "knowledge_gaps": knowledge_gaps,
        "recommended_level": recommended_level,
        "error_tags": sorted(error_tags),
        "misconceptions": misconceptions,
        "item_results": item_results,
    }
    session.status = "completed"
    session.completed_at = utc_now()
    session.result_json = result_json
    await db.flush()

    return AssessmentSubmitResponse(status="completed", **result_json)
