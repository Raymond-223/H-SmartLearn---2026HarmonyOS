"""Adaptive diagnosis endpoints.

The flow is deliberately answer-driven: ``POST /answer`` grades the response,
updates the Beta posteriors, re-runs item selection, and returns either the next
item or the final result in the same round trip. ``GET /next`` exists for
recovery (app restart, lost response) and is idempotent — it re-derives the
pending item from persisted state rather than reserving anything.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workflows import resume_workflow_task
from app.core.database import get_db
from app.core.time import utc_now
from app.models.diagnosis_session import DiagnosisSession, DiagnosisResponse
from app.models.learner import LearnerProfile
from app.models.workflow import WorkflowSession
from app.schemas.diagnosis import (
    DiagnosisAnswerRequest,
    DiagnosisAnswerResponse,
    DiagnosisConceptDelta,
    DiagnosisNextItem,
    DiagnosisNextResponse,
    DiagnosisOption,
    DiagnosisResult,
    DiagnosisSessionState,
    DiagnosisStartRequest,
    DiagnosisStartResponse,
)
from app.services.domain_package_service import load_concept_nodes, load_skill_nodes, skill_name_map
from app.services.information_gain_diagnosis_service import (
    CandidateScore,
    InformationGainDiagnosisService,
    SessionContext,
    item_concept_ids,
    item_estimated_time,
)
from app.services.learner_model_service import UNCERTAIN_THRESHOLD, LearnerModelService
from app.services.mastery_service import upsert_mastery
from app.workflow.event_bus import publish_workflow_event
from app.workflow.transitions import WorkflowStatus, validate_transition

router = APIRouter(prefix="/api/v1/diagnosis", tags=["diagnosis"])


# --------------------------------------------------------------------- helpers


def _services(db: AsyncSession, domain_id: str) -> tuple[LearnerModelService, InformationGainDiagnosisService]:
    learner_model = LearnerModelService(db, domain_id=domain_id)
    return learner_model, InformationGainDiagnosisService(learner_model)


def _to_next_item(
    item: dict,
    score: CandidateScore,
    question_index: int,
) -> DiagnosisNextItem:
    return DiagnosisNextItem(
        item_id=str(item.get("id")),
        skill_id=item.get("skill_id"),
        concept_ids=list(score.concept_ids),
        question_type=str(item.get("question_type") or item.get("type") or "single_choice"),
        difficulty=int(item.get("difficulty") or 1),
        stem=str(item.get("stem") or ""),
        options=[
            DiagnosisOption(key=str(option.get("key", "")), text=str(option.get("text", "")))
            for option in (item.get("options") or [])
        ],
        estimated_time_sec=item_estimated_time(item),
        importance=int(item.get("importance") or 3),
        question_index=question_index,
        information_gain=round(score.information_gain, 6),
        coverage_gain=round(score.coverage_gain, 6),
        time_cost=round(score.time_cost, 6),
        fatigue=round(score.fatigue, 6),
        selection_score=round(score.total_score, 6),
    )


def _target_skill_ids(target_skill_id: str | None) -> list[str] | None:
    """Selection scope: one skill when the session is focused, else the domain."""
    return None if target_skill_id is None else [target_skill_id]


async def _advance_workflow(
    db: AsyncSession,
    workflow_id: str | None,
    next_state: WorkflowStatus,
) -> bool:
    """Move a linked workflow through the adaptive-diagnosis sub-states.

    A diagnosis session may run standalone, and a linked workflow may have moved
    on for other reasons, so an illegal transition is a no-op rather than an
    error: diagnosis must never fail because a workflow is elsewhere.
    """
    if not workflow_id:
        return False
    workflow = await db.get(WorkflowSession, workflow_id)
    if workflow is None:
        return False
    current = WorkflowStatus(workflow.current_state)
    if current == next_state:
        return True
    if not validate_transition(current, next_state):
        return False
    workflow.current_state = next_state.value
    workflow.updated_at = utc_now()
    return True


async def _publish_workflow_state(
    db: AsyncSession,
    session: DiagnosisSession,
    learner_model: LearnerModelService,
) -> None:
    """Write the finished session's posterior into the workflow's state blob."""
    workflow = await db.get(WorkflowSession, session.workflow_id)
    if workflow is None:
        return
    profile = await learner_model.get_ability_profile(session.learner_id)
    state = dict(workflow.state_data or {})
    state["diagnosis_session_id"] = session.id
    state["learner_state"] = {
        "learner_id": session.learner_id,
        "domain_id": session.domain_id,
        "ability_profile": profile,
        "skill_states": profile["skill_states"],
    }
    state["mastery_summary"] = {
        "overall_mastery": profile["overall_mastery"],
        "overall_uncertainty": profile["overall_uncertainty"],
        "recommended_level": profile["recommended_level"],
        "concept_coverage": profile["concept_coverage"],
        "tested_concept_count": profile["tested_concept_count"],
        "total_concept_count": profile["total_concept_count"],
        "skill_mastery": {
            item["skill_id"]: item["mastery_probability"] for item in profile["skill_states"]
        },
        "skill_uncertainty": {
            item["skill_id"]: item["uncertainty"] for item in profile["skill_states"]
        },
    }
    state["weak_concepts"] = profile["weak_concepts"]
    state["uncertain_concepts"] = profile["uncertain_concepts"]
    workflow.state_data = state
    workflow.updated_at = utc_now()


async def _commit_before_handoff(db: AsyncSession) -> None:
    """Commit now, before handing the workflow to a background task.

    FastAPI closes the ``get_db`` dependency's exit stack *after* the response —
    and therefore after background tasks have already run. Relying on that
    implicit commit means ``resume_workflow_task`` opens its own session, still
    sees the workflow in its previous state, and silently no-ops; SSE
    subscribers would likewise be notified about a state that is not yet
    readable. Committing here makes the finished diagnosis durable before anyone
    is told about it. The dependency's later commit becomes a no-op.
    """
    await db.commit()


async def _get_session(db: AsyncSession, session_id: str) -> DiagnosisSession:
    session = await db.get(DiagnosisSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Diagnosis session not found")
    return session


async def _pick_next(
    session: DiagnosisSession,
    diagnosis_service: InformationGainDiagnosisService,
) -> tuple[CandidateScore | None, bool, str]:
    """Select the next item and evaluate the stop rule.

    Returns ``(candidate, finished, stop_reason)``. When ``finished`` is True the
    candidate is discarded — the session ends rather than asking one more.
    """
    context = SessionContext.from_session(session)
    skill_ids = _target_skill_ids(session.target_skill_id)
    candidate = await diagnosis_service.select_next_item(session.learner_id, context, skill_ids)
    if candidate is None:
        return None, True, "item_bank_exhausted"
    stop, reason = await diagnosis_service.should_stop(
        session.learner_id, context, next_candidate=candidate, skill_ids=skill_ids
    )
    if stop:
        return None, True, reason
    return candidate, False, reason


async def _sync_skill_mastery(
    db: AsyncSession,
    learner_model: LearnerModelService,
    learner_id: str,
    skill_ids: list[str],
) -> None:
    """Mirror concept posteriors into the legacy 0-100 MasteryState rows.

    The planner, report endpoint and HarmonyOS report page all read
    ``mastery_states``. Writing through keeps them consistent with the Beta
    model instead of leaving two competing sources of truth.
    """
    for skill_id in skill_ids:
        state = await learner_model.get_skill_state(learner_id, skill_id)
        if state.attempt_count == 0:
            continue
        await upsert_mastery(
            db,
            learner_id=learner_id,
            skill_id=skill_id,
            mastery_score=100.0 * state.mastery_probability,
            confidence=1.0 - state.uncertainty,
            evidence_count=state.attempt_count,
        )


async def _snapshot_profile(
    db: AsyncSession,
    learner_id: str,
    domain_id: str,
    profile: dict,
    concept_states: dict,
    misconceptions: list[str],
    finished_at=None,
) -> None:
    """Cache the diagnosis outcome on the learner profile.

    ``learner_concept_mastery`` remains the source of truth; this snapshot exists
    so the profile screen and the planner can read an ability picture without
    re-aggregating every concept row.
    """
    learner = await db.get(LearnerProfile, learner_id)
    if learner is None:
        return

    counts: dict[str, int] = {}
    for tag in misconceptions:
        counts[tag] = counts.get(tag, 0) + 1

    by_domain = dict(learner.concept_mastery or {})
    by_domain[domain_id] = {
        state.concept_id: {
            "mastery_probability": round(state.mastery_probability, 4),
            "uncertainty": round(state.uncertainty, 4),
            "attempt_count": state.attempt_count,
        }
        for state in concept_states.values()
    }

    learner.ability_profile = profile
    learner.concept_mastery = by_domain
    learner.uncertainty = profile["overall_uncertainty"]
    learner.misconceptions = [tag for tag, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    learner.last_diagnosed_at = finished_at or utc_now()


async def _build_result(
    db: AsyncSession,
    session: DiagnosisSession,
    learner_model: LearnerModelService,
) -> DiagnosisResult:
    responses = list((await db.execute(
        select(DiagnosisResponse)
        .where(DiagnosisResponse.session_id == session.id)
        .order_by(DiagnosisResponse.answered_at, DiagnosisResponse.id)
    )).scalars().all())

    correct_count = sum(1 for row in responses if row.is_correct)
    total_time = sum(float(row.response_time_sec or 0.0) for row in responses)
    question_count = len(responses)

    profile = await learner_model.get_ability_profile(session.learner_id)
    tested_concepts = list(session.tested_concept_ids or [])
    weak = await learner_model.get_weak_concepts(session.learner_id, limit=10)

    # Headline numbers describe what *this session* measured, not the learner's
    # whole-domain state: after a focused tf2 run the profile's overall
    # uncertainty is still ~0.94 (45 untouched concepts sit at 1.0), which would
    # read as "the session learned nothing". The unscoped view is still
    # available to the planner via `ability_profile` below.
    session_states = await learner_model.get_concept_states(session.learner_id, tested_concepts)
    measured = list(session_states.values())
    overall_mastery = (
        round(sum(state.mastery_probability for state in measured) / len(measured), 4)
        if measured else profile["overall_mastery"]
    )
    overall_uncertainty = (
        round(sum(state.uncertainty for state in measured) / len(measured), 4)
        if measured else profile["overall_uncertainty"]
    )
    uncertain = sorted(
        (state for state in measured if state.uncertainty > UNCERTAIN_THRESHOLD),
        key=lambda state: -state.uncertainty,
    )[:10]

    touched_skills = sorted({str(row.skill_id) for row in responses if row.skill_id})
    skill_states = [
        await learner_model.get_skill_state(session.learner_id, skill_id)
        for skill_id in touched_skills
    ]
    names = skill_name_map(session.domain_id)
    knowledge_gaps = [
        names.get(state.skill_id, state.skill_id)
        for state in skill_states
        if state.mastery_probability < 0.6
    ]

    misconceptions: list[str] = []
    item_results: list[dict] = []
    diagnosis_service = InformationGainDiagnosisService(learner_model)
    for row in responses:
        item = diagnosis_service.get_item(str(row.item_id)) or {}
        if not row.is_correct:
            misconceptions.extend(item.get("misconception_tags") or item.get("error_tags") or [])
        item_results.append({
            "item_id": row.item_id,
            "skill_id": row.skill_id,
            "concept_ids": list(row.concept_ids or []),
            "difficulty": row.difficulty,
            "stem": item.get("stem", ""),
            "user_answer": row.user_answer,
            "correct_answer": item.get("correct_answer", ""),
            "is_correct": bool(row.is_correct),
            "explanation": item.get("explanation", ""),
            "response_time_sec": row.response_time_sec,
            "error_tags": [] if row.is_correct else list(item.get("error_tags") or []),
        })

    await _snapshot_profile(
        db,
        learner_id=session.learner_id,
        domain_id=session.domain_id,
        profile=profile,
        concept_states=session_states,
        misconceptions=misconceptions,
        finished_at=session.finished_at,
    )

    accuracy = correct_count / question_count if question_count else 0.0
    weak_names = [state.name or state.concept_id for state in weak[:3]]
    summary = (
        f"自适应诊断完成：{question_count}题，正确率{accuracy:.0%}，"
        f"整体掌握度{overall_mastery:.0%}。"
        + (f"优先补强：{'、'.join(weak_names)}。" if weak_names else "暂无明显薄弱概念。")
    )

    return DiagnosisResult(
        session_id=session.id,
        learner_id=session.learner_id,
        domain_id=session.domain_id,
        target_skill_id=session.target_skill_id,
        status=session.status,
        question_count=question_count,
        correct_count=correct_count,
        accuracy=round(accuracy, 4),
        total_time_sec=round(total_time, 2),
        stop_reason=(session.result_json or {}).get("stop_reason"),
        overall_mastery=overall_mastery,
        overall_uncertainty=overall_uncertainty,
        recommended_level=profile["recommended_level"],
        tested_concept_ids=tested_concepts,
        weak_concepts=[state.to_dict() for state in weak],
        uncertain_concepts=[state.to_dict() for state in uncertain],
        skill_states=[state.to_dict() for state in skill_states],
        ability_profile=profile,
        misconceptions=sorted(set(misconceptions)),
        knowledge_gaps=knowledge_gaps,
        item_results=item_results,
        summary=summary,
    )


# ------------------------------------------------------------------ endpoints


@router.post("/start", response_model=DiagnosisStartResponse, status_code=201)
async def start_diagnosis(data: DiagnosisStartRequest, db: AsyncSession = Depends(get_db)):
    learner = await db.get(LearnerProfile, data.learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    try:
        skills = {node["id"] for node in load_skill_nodes(data.domain_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Domain not found")
    if data.target_skill_id is not None and data.target_skill_id not in skills:
        raise HTTPException(status_code=422, detail="target skill does not belong to domain")

    if data.workflow_id is not None:
        workflow = await db.get(WorkflowSession, data.workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        if workflow.learner_id != data.learner_id:
            raise HTTPException(status_code=422, detail="Workflow belongs to another learner")

    learner_model, diagnosis_service = _services(db, data.domain_id)
    if not diagnosis_service.bank:
        raise HTTPException(status_code=404, detail="Assessment bank is empty")

    concept_ids = [
        node["id"] for node in load_concept_nodes(data.domain_id)
        if data.target_skill_id is None or node.get("skill_id") == data.target_skill_id
    ]
    await learner_model.initialize_learner(data.learner_id, concept_ids)

    session = DiagnosisSession(
        learner_id=data.learner_id,
        domain_id=data.domain_id,
        target_skill_id=data.target_skill_id,
        workflow_id=data.workflow_id,
        answered_item_ids=[],
        tested_concept_ids=[],
        question_count=0,
        fatigue_state={"consecutive_hard": 0, "elapsed_seconds": 0.0, "level": 0.0},
        status="in_progress",
    )
    db.add(session)
    await db.flush()

    # 开始诊断 -> 动态出题
    await _advance_workflow(db, session.workflow_id, WorkflowStatus.DIAGNOSIS_QUESTIONING)

    context = SessionContext.from_session(session)
    candidate = await diagnosis_service.select_next_item(
        data.learner_id, context, _target_skill_ids(data.target_skill_id)
    )
    next_item = None
    if candidate is not None:
        item = diagnosis_service.get_item(candidate.item_id)
        if item is not None:
            next_item = _to_next_item(item, candidate, question_index=1)

    return DiagnosisStartResponse(
        session_id=session.id,
        learner_id=session.learner_id,
        domain_id=session.domain_id,
        target_skill_id=session.target_skill_id,
        workflow_id=session.workflow_id,
        status=session.status,
        question_count=0,
        next_item=next_item,
        started_at=session.started_at,
    )


@router.post("/{session_id}/answer", response_model=DiagnosisAnswerResponse)
async def submit_diagnosis_answer(
    session_id: str,
    data: DiagnosisAnswerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session(db, session_id)
    if session.status != "in_progress":
        raise HTTPException(status_code=409, detail="Diagnosis session is already finished")

    learner_model, diagnosis_service = _services(db, session.domain_id)
    item = diagnosis_service.get_item(data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")

    answered = list(session.answered_item_ids or [])
    if data.item_id in answered:
        raise HTTPException(status_code=409, detail="Item already answered in this session")

    normalized = data.answer.strip().upper()
    option_keys = {str(option.get("key", "")).strip().upper() for option in (item.get("options") or [])}
    if option_keys and normalized not in option_keys:
        raise HTTPException(status_code=422, detail=f"Invalid option for item {data.item_id}")
    is_correct = normalized == str(item.get("correct_answer", "")).strip().upper()

    concept_ids = item_concept_ids(item, diagnosis_service.concept_index)
    before = await learner_model.get_concept_states(session.learner_id, concept_ids)
    after_states = await learner_model.update_from_answer(
        learner_id=session.learner_id,
        concept_ids=concept_ids,
        is_correct=is_correct,
        difficulty=int(item.get("difficulty") or 3),
        response_time=data.response_time_sec,
        expected_time=item_estimated_time(item),
    )
    deltas = [
        DiagnosisConceptDelta(
            concept_id=state.concept_id,
            name=state.name,
            mastery_before=round(before[state.concept_id].mastery_probability, 4),
            mastery_after=round(state.mastery_probability, 4),
            uncertainty_before=round(before[state.concept_id].uncertainty, 4),
            uncertainty_after=round(state.uncertainty, 4),
        )
        for state in after_states
        if state.concept_id in before
    ]

    difficulty = int(item.get("difficulty") or 3)
    response_time = float(data.response_time_sec or 0.0)
    db.add(DiagnosisResponse(
        session_id=session.id,
        learner_id=session.learner_id,
        item_id=data.item_id,
        skill_id=item.get("skill_id"),
        concept_ids=concept_ids,
        user_answer=normalized,
        is_correct=is_correct,
        response_time_sec=response_time,
        difficulty=difficulty,
    ))

    fatigue = dict(session.fatigue_state or {})
    consecutive_hard = int(fatigue.get("consecutive_hard", 0))
    consecutive_hard = consecutive_hard + 1 if difficulty >= 4 else 0
    elapsed = float(fatigue.get("elapsed_seconds", 0.0)) + response_time

    session.answered_item_ids = answered + [data.item_id]
    session.tested_concept_ids = sorted(set(list(session.tested_concept_ids or []) + concept_ids))
    session.question_count = int(session.question_count or 0) + 1
    session.fatigue_state = {
        "consecutive_hard": consecutive_hard,
        "elapsed_seconds": elapsed,
        "level": round(min(2.0, consecutive_hard * 0.25 + elapsed / (20 * 60)), 4),
    }
    await db.flush()

    answered_skill_id = item.get("skill_id")
    if answered_skill_id:
        await _sync_skill_mastery(db, learner_model, session.learner_id, [str(answered_skill_id)])

    # 动态出题 -> 更新学习者模型
    await _advance_workflow(db, session.workflow_id, WorkflowStatus.LEARNER_MODEL_UPDATING)

    candidate, finished, stop_reason = await _pick_next(session, diagnosis_service)
    next_item = None
    result = None
    if finished:
        session.status = "completed"
        session.finished_at = utc_now()
        session.result_json = {"stop_reason": stop_reason}
        await db.flush()
        result = await _build_result(db, session, learner_model)
        # 更新学习者模型 -> 诊断完成，随后交回工作流继续规划
        if await _advance_workflow(db, session.workflow_id, WorkflowStatus.DIAGNOSIS_COMPLETED):
            await _publish_workflow_state(db, session, learner_model)
            await _commit_before_handoff(db)
            background_tasks.add_task(publish_workflow_event, session.workflow_id)
            background_tasks.add_task(resume_workflow_task, session.workflow_id)
    elif candidate is not None:
        # 更新学习者模型 -> 动态出题（自适应循环）
        await _advance_workflow(db, session.workflow_id, WorkflowStatus.DIAGNOSIS_QUESTIONING)
        next_raw = diagnosis_service.get_item(candidate.item_id)
        if next_raw is not None:
            next_item = _to_next_item(next_raw, candidate, question_index=session.question_count + 1)

    return DiagnosisAnswerResponse(
        session_id=session.id,
        item_id=data.item_id,
        is_correct=is_correct,
        correct_answer=str(item.get("correct_answer", "")),
        explanation=str(item.get("explanation", "")),
        error_tags=[] if is_correct else list(item.get("error_tags") or []),
        misconception_tags=[] if is_correct else list(item.get("misconception_tags") or []),
        concept_deltas=deltas,
        question_count=session.question_count,
        finished=finished,
        stop_reason=stop_reason if finished else None,
        next_item=next_item,
        result=result,
    )


@router.get("/{session_id}/next", response_model=DiagnosisNextResponse)
async def get_next_item(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session(db, session_id)
    learner_model, diagnosis_service = _services(db, session.domain_id)

    if session.status != "in_progress":
        return DiagnosisNextResponse(
            session_id=session.id,
            finished=True,
            stop_reason=(session.result_json or {}).get("stop_reason"),
            question_count=int(session.question_count or 0),
        )

    candidate, finished, stop_reason = await _pick_next(session, diagnosis_service)
    if finished:
        session.status = "completed"
        session.finished_at = utc_now()
        session.result_json = {"stop_reason": stop_reason}
        await db.flush()
        if await _advance_workflow(db, session.workflow_id, WorkflowStatus.DIAGNOSIS_COMPLETED):
            await _publish_workflow_state(db, session, learner_model)
            await _commit_before_handoff(db)
            background_tasks.add_task(publish_workflow_event, session.workflow_id)
            background_tasks.add_task(resume_workflow_task, session.workflow_id)
        return DiagnosisNextResponse(
            session_id=session.id,
            finished=True,
            stop_reason=stop_reason,
            question_count=int(session.question_count or 0),
        )

    next_item = None
    if candidate is not None:
        item = diagnosis_service.get_item(candidate.item_id)
        if item is not None:
            next_item = _to_next_item(item, candidate, question_index=int(session.question_count or 0) + 1)
    return DiagnosisNextResponse(
        session_id=session.id,
        finished=False,
        stop_reason=None,
        question_count=int(session.question_count or 0),
        next_item=next_item,
    )


@router.get("/{session_id}/result", response_model=DiagnosisResult)
async def get_diagnosis_result(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id)
    learner_model, _ = _services(db, session.domain_id)
    return await _build_result(db, session, learner_model)


@router.get("/{session_id}", response_model=DiagnosisSessionState)
async def get_diagnosis_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id)
    return DiagnosisSessionState(
        session_id=session.id,
        learner_id=session.learner_id,
        domain_id=session.domain_id,
        target_skill_id=session.target_skill_id,
        workflow_id=session.workflow_id,
        status=session.status,
        question_count=int(session.question_count or 0),
        answered_item_ids=list(session.answered_item_ids or []),
        tested_concept_ids=list(session.tested_concept_ids or []),
        fatigue_state=dict(session.fatigue_state or {}),
        started_at=session.started_at,
        finished_at=session.finished_at,
    )
