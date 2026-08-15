"""Learner profile and domain-aware report endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.learner import (
    LearnerCreate,
    LearnerUpdate,
    LearnerResponse,
    LearnerDetail,
    LearnerReport,
)
from app.schemas.learner_model import (
    AbilityProfile,
    LearnerMasteryResponse,
    WeakConceptResponse,
)
from app.models.learner import LearnerProfile
from app.models.assessment import AssessmentSession, MasteryState
from app.models.feedback import FeedbackRecord
from app.models.resource import GeneratedResource
from app.models.workflow import WorkflowSession
from app.models.skill_graph import SkillNode
from app.services.domain_package_service import topological_path
from app.services.learner_model_service import WEAK_MASTERY_THRESHOLD, LearnerModelService

router = APIRouter(prefix="/api/v1/learners", tags=["learners"])


@router.post("", response_model=LearnerResponse, status_code=201)
async def create_learner(data: LearnerCreate, db: AsyncSession = Depends(get_db)):
    profile = LearnerProfile(
        education=data.education,
        major=data.major,
        target_role=data.target_role,
        weekly_hours=data.weekly_hours,
        preference_json=data.preferences,
        context=data.context,
    )
    db.add(profile)
    await db.flush()
    return LearnerResponse(learner_id=profile.id)


def _learner_detail(profile: LearnerProfile) -> LearnerDetail:
    return LearnerDetail(
        learner_id=profile.id,
        education=profile.education,
        major=profile.major,
        target_role=profile.target_role,
        weekly_hours=profile.weekly_hours,
        preferences=profile.preference_json or {},
        context=profile.context or {},
        ability_profile=profile.ability_profile,
        uncertainty=profile.uncertainty,
        misconceptions=list(profile.misconceptions or []),
        last_diagnosed_at=profile.last_diagnosed_at,
    )


@router.get("/{learner_id}", response_model=LearnerDetail)
async def get_learner(learner_id: str, db: AsyncSession = Depends(get_db)):
    profile = await db.get(LearnerProfile, learner_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    return _learner_detail(profile)


@router.put("/{learner_id}", response_model=LearnerDetail)
async def update_learner(
    learner_id: str,
    data: LearnerUpdate,
    db: AsyncSession = Depends(get_db),
):
    profile = await db.get(LearnerProfile, learner_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    field_map = {
        "education": "education",
        "major": "major",
        "target_role": "target_role",
        "weekly_hours": "weekly_hours",
        "preferences": "preference_json",
        "context": "context",
    }
    for source, target in field_map.items():
        if source in updates:
            setattr(profile, target, updates[source])
    await db.flush()
    return _learner_detail(profile)


# ------------------------------------------------------- Beta-Bernoulli views
#
# These three read the per-concept posterior maintained by LearnerModelService.
# They are deliberately separate from /report, which still speaks the legacy
# 0-100 MasteryState language the existing dashboard renders.


async def _learner_model(
    db: AsyncSession,
    learner_id: str,
    domain_id: str,
) -> LearnerModelService:
    if await db.get(LearnerProfile, learner_id) is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    return LearnerModelService(db, domain_id=domain_id)


@router.get("/{learner_id}/mastery", response_model=LearnerMasteryResponse)
async def get_learner_mastery(
    learner_id: str,
    domain_id: str = Query(default="ros2_robotics"),
    skill_id: str | None = Query(default=None),
    tested_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """Per-concept and per-skill posteriors, optionally scoped to one skill."""
    service = await _learner_model(db, learner_id, domain_id)
    profile = await service.get_ability_profile(learner_id)

    skill_states = profile["skill_states"]
    if skill_id is not None:
        skill_states = [state for state in skill_states if state["skill_id"] == skill_id]
        if not skill_states:
            raise HTTPException(status_code=404, detail="Skill not found in domain")

    concept_states = [
        concept
        for state in skill_states
        for concept in state["concepts"]
        if not tested_only or concept["attempt_count"] > 0
    ]
    return LearnerMasteryResponse(
        learner_id=learner_id,
        domain_id=domain_id,
        overall_mastery=profile["overall_mastery"],
        overall_uncertainty=profile["overall_uncertainty"],
        skill_states=skill_states,
        concept_states=concept_states,
    )


@router.get("/{learner_id}/weak-concepts", response_model=WeakConceptResponse)
async def get_learner_weak_concepts(
    learner_id: str,
    domain_id: str = Query(default="ros2_robotics"),
    skill_id: str | None = Query(default=None),
    threshold: float = Query(default=WEAK_MASTERY_THRESHOLD, ge=0.0, le=1.0),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Concepts with evidence of weakness, weakest first.

    Only concepts the learner has actually attempted are returned: an untouched
    concept sits at the 0.5 prior, which means *unknown*, not *weak*.
    """
    service = await _learner_model(db, learner_id, domain_id)
    weak = await service.get_weak_concepts(
        learner_id, threshold=threshold, skill_id=skill_id, limit=limit
    )
    return WeakConceptResponse(
        learner_id=learner_id,
        domain_id=domain_id,
        threshold=threshold,
        weak_concepts=[state.to_dict() for state in weak],
    )


@router.get("/{learner_id}/ability-profile", response_model=AbilityProfile)
async def get_learner_ability_profile(
    learner_id: str,
    domain_id: str = Query(default="ros2_robotics"),
    db: AsyncSession = Depends(get_db),
):
    """Whole-domain ability picture: the planner's primary input."""
    service = await _learner_model(db, learner_id, domain_id)
    return AbilityProfile(**await service.get_ability_profile(learner_id))


async def _resolve_report_domain(
    db: AsyncSession,
    learner_id: str,
    requested_domain: str | None,
) -> str:
    if requested_domain:
        exists = (await db.execute(
            select(SkillNode.id).where(SkillNode.domain_id == requested_domain).limit(1)
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail="Domain not found")
        return requested_domain

    latest_assessment = (await db.execute(
        select(AssessmentSession)
        .where(
            AssessmentSession.learner_id == learner_id,
            AssessmentSession.status == "completed",
        )
        .order_by(AssessmentSession.completed_at.desc(), AssessmentSession.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if latest_assessment is not None:
        return latest_assessment.domain_id

    latest_mastery_domain = (await db.execute(
        select(SkillNode.domain_id)
        .join(MasteryState, MasteryState.skill_id == SkillNode.id)
        .where(MasteryState.learner_id == learner_id)
        .order_by(MasteryState.last_updated.desc())
        .limit(1)
    )).scalar_one_or_none()
    return latest_mastery_domain or "ros2_robotics"


@router.get("/{learner_id}/report", response_model=LearnerReport)
async def get_learner_report(
    learner_id: str,
    domain_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    learner = await db.get(LearnerProfile, learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    selected_domain = await _resolve_report_domain(db, learner_id, domain_id)
    rows = (await db.execute(
        select(MasteryState, SkillNode)
        .join(SkillNode, MasteryState.skill_id == SkillNode.id)
        .where(
            MasteryState.learner_id == learner_id,
            SkillNode.domain_id == selected_domain,
        )
        .order_by(SkillNode.difficulty, SkillNode.name)
    )).all()

    mastery = [
        {
            "skill_id": node.id,
            "name": node.name,
            "score": round(state.mastery_score, 1),
            "confidence": round(state.confidence or 0, 2),
            "difficulty": node.difficulty,
        }
        for state, node in rows
    ]
    score_map = {item["skill_id"]: item["score"] for item in mastery}
    overall = round(sum(score_map.values()) / len(score_map), 1) if score_map else 0.0
    gaps = [item["name"] for item in mastery if item["score"] < 60]
    strengths = [item["name"] for item in mastery if item["score"] >= 75]

    path = [
        {
            "order": order,
            "skill_id": node["id"],
            "name": node["name"],
            "estimated_minutes": node.get("estimated_minutes", 60),
            "mastery": score_map.get(node["id"], 0),
        }
        for order, node in enumerate(topological_path(selected_domain), start=1)
    ]

    difficulty_groups = {"基础": [], "应用": [], "进阶": []}
    for item in mastery:
        difficulty = int(item.get("difficulty") or 1)
        label = "基础" if difficulty <= 1 else ("应用" if difficulty == 2 else "进阶")
        difficulty_groups[label].append(float(item["score"]))
    difficulty_curve = [
        {
            "label": label,
            "score": round(sum(values) / len(values), 1) if values else 0.0,
            "skill_count": len(values),
        }
        for label, values in difficulty_groups.items()
    ]

    history_events: list[dict] = []
    assessments = list((await db.execute(
        select(AssessmentSession)
        .where(
            AssessmentSession.learner_id == learner_id,
            AssessmentSession.domain_id == selected_domain,
            AssessmentSession.status == "completed",
        )
        .order_by(AssessmentSession.completed_at)
    )).scalars().all())
    for assessment in assessments:
        result = assessment.result_json or {}
        values = [float(row.get("score", 0)) for row in (result.get("mastery") or {}).values()]
        if not values or assessment.completed_at is None:
            continue
        history_events.append({
            "_time": assessment.completed_at,
            "timestamp": assessment.completed_at.isoformat(),
            "event_type": "assessment",
            "label": "诊断测评",
            "score": round(sum(values) / len(values), 1),
        })

    feedback_rows = list((await db.execute(
        select(FeedbackRecord, GeneratedResource)
        .join(GeneratedResource, FeedbackRecord.resource_id == GeneratedResource.id)
        .join(WorkflowSession, GeneratedResource.workflow_id == WorkflowSession.id)
        .where(
            FeedbackRecord.learner_id == learner_id,
            WorkflowSession.domain_id == selected_domain,
        )
        .order_by(FeedbackRecord.feedback_time)
    )).all())
    skill_names = {item["skill_id"]: item["name"] for item in mastery}
    for feedback, resource in feedback_rows:
        theory = float(feedback.correct_rate or 0)
        practice = float(feedback.practice_score or 0)
        history_events.append({
            "_time": feedback.feedback_time,
            "timestamp": feedback.feedback_time.isoformat(),
            "event_type": "resource_feedback",
            "label": f"完成{skill_names.get(resource.skill_id, resource.skill_id)}",
            "skill_id": resource.skill_id,
            "score": round(100.0 * (0.5 * theory + 0.5 * practice), 1),
        })
    history_events.sort(key=lambda item: item["_time"])
    progress_history = [
        {key: value for key, value in item.items() if key != "_time"}
        for item in history_events[-20:]
    ]

    return LearnerReport(
        learner_id=learner_id,
        overall_mastery=overall,
        domain=selected_domain,
        skill_mastery=mastery,
        knowledge_gaps=gaps,
        strengths=strengths,
        difficulty_curve=difficulty_curve,
        learning_path=path,
        progress_history=progress_history,
        recommended_resources=[item["skill_id"] for item in path if item["mastery"] < 60],
    )
