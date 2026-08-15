"""Published resources, server-scored tests, and the learning feedback loop."""

from copy import deepcopy

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.resource import (
    ResourceResponse,
    ResourceTestSubmit,
    ResourceTestResult,
    FeedbackCreate,
    FeedbackResponse,
)
from app.models.resource import GeneratedResource
from app.models.feedback import FeedbackRecord
from app.models.workflow import WorkflowSession
from app.models.assessment import MasteryState
from app.agents.feedback_agent import FeedbackAgent
from app.workflow.orchestrator import Orchestrator
from app.api.workflows import run_workflow_task
from app.services.domain_package_service import topological_path
from app.services.mastery_service import upsert_mastery
from app.services.feedback_service import create_feedback_once
from app.services.learner_model_service import LearnerModelService

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


def _public_citations(bundle: dict) -> list[dict]:
    """Hide server-local file paths while preserving audited evidence metadata."""
    citations = deepcopy(bundle.get("citations", []))
    for citation in citations:
        source_url = str(citation.get("source_url", ""))
        source_type = str(citation.get("source_type", "local"))
        if source_type != "web" or not source_url.startswith(("http://", "https://")):
            citation["source_url"] = ""
            citation["source_type"] = "local"
    return citations


def _public_resource_sections(bundle: dict) -> dict:
    """Return learner-visible content without leaking grading keys before submit."""
    resources = deepcopy(bundle.get("resources", {}))
    for item in resources.get("graded_test", {}).get("items", []):
        item.pop("correct_answer", None)
        item.pop("explanation", None)
    return resources


async def _find_followup_workflow(
    db: AsyncSession,
    *,
    learner_id: str,
    resource_id: str,
) -> WorkflowSession | None:
    sessions = list((await db.execute(
        select(WorkflowSession)
        .where(WorkflowSession.learner_id == learner_id)
        .order_by(WorkflowSession.created_at.desc())
    )).scalars().all())
    for session in sessions:
        state = session.state_data or {}
        if state.get("source_resource_id") == resource_id:
            return session
    return None


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(resource_id: str, db: AsyncSession = Depends(get_db)):
    resource = await db.get(GeneratedResource, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=404, detail="Resource not found")
    bundle = resource.content_json or {}
    resources = _public_resource_sections(bundle)
    workflow = await db.get(WorkflowSession, resource.workflow_id)
    feedback = None
    followup = None
    if workflow is not None:
        feedback = (await db.execute(
            select(FeedbackRecord).where(
                FeedbackRecord.learner_id == workflow.learner_id,
                FeedbackRecord.resource_id == resource_id,
            )
        )).scalar_one_or_none()
        if feedback is not None:
            followup = await _find_followup_workflow(
                db, learner_id=workflow.learner_id, resource_id=resource_id)
    followup_state = (followup.state_data or {}) if followup is not None else {}
    feedback_output = followup_state.get("feedback", {}) if isinstance(followup_state, dict) else {}
    feedback_recorded = feedback is not None
    feedback_decision = None
    feedback_reason = None
    if feedback_recorded:
        feedback_decision = str(feedback_output.get("action") or ("recorded" if followup else "complete"))
        feedback_reason = str(feedback_output.get("reason") or (
            "反馈已记录，可继续后续学习" if followup else "当前领域学习路径已完成"
        ))
    return ResourceResponse(
        resource_id=resource.id,
        workflow_id=resource.workflow_id,
        difficulty=resource.difficulty,
        target_skill=resource.skill_id,
        lecture=resources.get("lecture"),
        practice_guide=resources.get("practice_guide"),
        graded_test=resources.get("graded_test"),
        citations=_public_citations(bundle),
        review=bundle.get("review"),
        metadata=bundle.get("metadata"),
        feedback_recorded=feedback_recorded,
        feedback_decision=feedback_decision,
        feedback_reason=feedback_reason,
        next_workflow_id=followup.id if followup is not None else None,
    )


@router.post("/{resource_id}/test", response_model=ResourceTestResult)
async def submit_resource_test(
    resource_id: str,
    data: ResourceTestSubmit,
    db: AsyncSession = Depends(get_db),
):
    resource = await db.get(GeneratedResource, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=404, detail="Resource not found")
    items = ((resource.content_json or {}).get("resources", {}).get("graded_test", {}).get("items", []))
    item_map = {str(item.get("id")): item for item in items}
    if not item_map:
        raise HTTPException(status_code=409, detail="Resource has no graded test")
    answer_ids = [answer.item_id for answer in data.answers]
    if len(answer_ids) != len(set(answer_ids)):
        raise HTTPException(status_code=422, detail="Duplicate test answer")
    if set(answer_ids) != set(item_map):
        raise HTTPException(status_code=422, detail="All resource test items must be answered exactly once")

    results: list[dict] = []
    error_tags: list[str] = []
    correct_count = 0
    for answer in data.answers:
        item = item_map[answer.item_id]
        normalized = answer.answer.strip().upper()
        option_keys = {str(option.get("key", "")).strip().upper() for option in item.get("options", [])}
        if normalized not in option_keys:
            raise HTTPException(status_code=422, detail=f"Invalid option for item {answer.item_id}")
        expected = str(item.get("correct_answer", "")).strip().upper()
        is_correct = normalized == expected
        skill_id = str(item.get("skill_id") or resource.skill_id)
        if is_correct:
            correct_count += 1
        elif skill_id not in error_tags:
            error_tags.append(skill_id)
        results.append({
            "item_id": answer.item_id,
            "skill_id": skill_id,
            "user_answer": normalized,
            "correct_answer": expected,
            "is_correct": is_correct,
            "explanation": str(item.get("explanation", "")),
            "concept_ids": [str(cid) for cid in item.get("concept_ids", []) if cid],
            "difficulty": str(item.get("difficulty", "")) or None,
        })
    total_count = len(items)
    result = ResourceTestResult(
        score=correct_count / total_count,
        correct_count=correct_count,
        total_count=total_count,
        error_tags=error_tags,
        item_results=results,
    )

    # A generated resource belongs to one learner workflow, so its latest scored
    # attempt is the authoritative theory result used by the feedback endpoint.
    bundle = dict(resource.content_json or {})
    bundle["latest_test_result"] = result.model_dump()
    resource.content_json = bundle
    await db.flush()
    return result


@router.post("/{resource_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    resource_id: str,
    data: FeedbackCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    resource = await db.get(GeneratedResource, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=404, detail="Resource not found")
    workflow = await db.get(WorkflowSession, resource.workflow_id)
    if workflow is None:
        raise HTTPException(status_code=409, detail="Workflow missing")

    existing = (await db.execute(
        select(FeedbackRecord).where(
            FeedbackRecord.learner_id == workflow.learner_id,
            FeedbackRecord.resource_id == resource_id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        followup = await _find_followup_workflow(
            db, learner_id=workflow.learner_id, resource_id=resource_id)
        return FeedbackResponse(
            decision="recorded" if followup else "complete",
            reason="该资源反馈已处理，不会重复更新掌握度或创建学习任务",
            next_workflow_id=followup.id if followup else None,
        )

    bundle = resource.content_json or {}
    latest_test = bundle.get("latest_test_result")
    if not isinstance(latest_test, dict):
        raise HTTPException(status_code=409, detail="Complete and submit the resource test before feedback")
    theory_score = float(latest_test.get("score", 0.0))

    steps = bundle.get("resources", {}).get("practice_guide", {}).get("steps", [])
    expected_orders = {int(step.get("order")) for step in steps if step.get("order") is not None}
    submitted_orders = [item.order for item in data.practice_results]
    if len(submitted_orders) != len(set(submitted_orders)):
        raise HTTPException(status_code=422, detail="Duplicate practice step result")
    if not expected_orders or set(submitted_orders) != expected_orders:
        raise HTTPException(status_code=422, detail="All practice steps must be evaluated exactly once")
    successful_steps = sum(1 for item in data.practice_results if item.success)
    practice_score = successful_steps / len(expected_orders)

    inserted = await create_feedback_once(
        db,
        learner_id=workflow.learner_id,
        resource_id=resource_id,
        correct_rate=theory_score,
        practice_score=practice_score,
        subjective_difficulty=data.subjective_difficulty,
        error_tags=data.error_tags,
    )
    if not inserted:
        followup = await _find_followup_workflow(
            db, learner_id=workflow.learner_id, resource_id=resource_id)
        return FeedbackResponse(
            decision="recorded" if followup else "complete",
            reason="该资源反馈已处理，不会重复更新掌握度或创建学习任务",
            next_workflow_id=followup.id if followup else None,
        )

    learner_model = LearnerModelService(db, domain_id=workflow.domain_id)
    difficulty_map = {"basic": 1, "intermediate": 2, "advanced": 3}
    for item_result in latest_test.get("item_results", []):
        concept_ids = [str(cid) for cid in item_result.get("concept_ids", []) if cid]
        if not concept_ids:
            continue
        await learner_model.update_from_answer(
            learner_id=workflow.learner_id,
            concept_ids=concept_ids,
            is_correct=bool(item_result.get("is_correct")),
            difficulty=difficulty_map.get(str(item_result.get("difficulty", "basic")), 1),
        )

    previous = (await db.execute(
        select(MasteryState).where(
            MasteryState.learner_id == workflow.learner_id,
            MasteryState.skill_id == resource.skill_id,
        )
    )).scalar_one_or_none()
    history = previous.mastery_score / 100.0 if previous is not None else 0.0
    skill_state = await learner_model.get_skill_state(workflow.learner_id, resource.skill_id)
    if skill_state.tested_concept_count > 0:
        # Concept posterior is the knowledge source of truth; verified practice is
        # retained as a smaller skill-level performance signal.
        mastery_score = 100.0 * (0.80 * skill_state.mastery_probability + 0.20 * practice_score)
        evidence_count = max(skill_state.attempt_count, (previous.evidence_count if previous is not None else 0) + 1)
        confidence = min(0.98, max(0.0, 1.0 - skill_state.uncertainty))
    else:
        evidence_count = (previous.evidence_count if previous is not None else 0) + 2
        mastery_score = 100.0 * (0.50 * theory_score + 0.35 * practice_score + 0.15 * history)
        confidence = min(0.98, 0.60 + 0.04 * evidence_count)
    await upsert_mastery(
        db,
        learner_id=workflow.learner_id,
        skill_id=resource.skill_id,
        mastery_score=mastery_score,
        confidence=confidence,
        evidence_count=evidence_count,
    )

    authoritative_input = data.model_dump()
    authoritative_input["correct_rate"] = theory_score
    authoritative_input["practice_score"] = practice_score
    orchestrator = Orchestrator(db)
    result = await orchestrator.run_agent(
        workflow,
        "feedback_agent",
        FeedbackAgent().run,
        authoritative_input,
    )
    output = result.get("output", {})

    action = output.get("action", "advance")
    ordered_skills = [node["id"] for node in topological_path(workflow.domain_id)]
    current_skill = resource.skill_id
    target_skill = current_skill
    if action == "advance" and current_skill in ordered_skills:
        current_index = ordered_skills.index(current_skill)
        if current_index + 1 < len(ordered_skills):
            target_skill = ordered_skills[current_index + 1]
        else:
            await db.commit()
            return FeedbackResponse(
                decision="complete",
                reason="当前领域的全部技能节点已完成，可在学情报告中复习薄弱项",
                next_workflow_id=None,
            )
    elif action == "lower_difficulty" and output.get("insert_skills"):
        target_skill = output["insert_skills"][0]

    next_workflow = await orchestrator.create_workflow(
        learner_id=workflow.learner_id,
        domain_id=workflow.domain_id,
        target_goal=workflow.target_goal,
        assessment_id=None,
        target_skill_id=target_skill,
    )
    state = dict(next_workflow.state_data or {})
    state["feedback"] = output
    state["source_resource_id"] = resource_id
    state["source_skill_id"] = target_skill
    state["previous_skill_id"] = resource.skill_id
    state["requested_difficulty"] = output.get("next_resource_level", "basic")
    state["insert_skills"] = output.get("insert_skills", [])
    next_workflow.state_data = state
    next_workflow_id = next_workflow.id
    await db.commit()
    background_tasks.add_task(run_workflow_task, next_workflow_id)

    return FeedbackResponse(
        decision=output.get("action", "advance"),
        reason=output.get("reason", ""),
        next_workflow_id=next_workflow_id,
    )
