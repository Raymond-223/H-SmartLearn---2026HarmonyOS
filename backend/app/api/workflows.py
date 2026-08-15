"""Workflow creation, progress, SSE events, and trace endpoints."""

import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, async_session_factory
from app.schemas.workflow import (
    WorkflowCreate, WorkflowCreateResponse, WorkflowStatus as WorkflowStatusSchema,
    WorkflowTrace, AgentTraceItem, WorkflowSnapshot, WorkflowLearnerState,
)
from app.workflow.orchestrator import Orchestrator
from app.workflow.transitions import WorkflowStatus
from app.workflow.event_bus import subscribe, unsubscribe
from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.generation_agent import GenerationAgent
from app.agents.review_agent import ReviewAgent
from app.agents.risk_router_agent import RiskRouterAgent
from app.agents.proofgraph_agent import ProofGraphAgent
from app.agents.critic_agent import CriticAgent
from app.agents.judge_agent import JudgeAgent
from app.models.workflow import WorkflowSession, AgentRun
from app.models.resource import GeneratedResource, ReviewRecord
from app.services.learner_model_service import LearnerModelService
from app.workflow.state import WorkflowState

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

STATE_AGENT = {
    WorkflowStatus.DIAGNOSING.value: "diagnosis_agent",
    WorkflowStatus.DIAGNOSIS_QUESTIONING.value: "diagnosis_agent",
    WorkflowStatus.LEARNER_MODEL_UPDATING.value: "diagnosis_agent",
    WorkflowStatus.DIAGNOSIS_COMPLETED.value: "diagnosis_agent",
    WorkflowStatus.PATH_PLANNING.value: "planner_agent",
    WorkflowStatus.RETRIEVING.value: "retrieval_agent",
    WorkflowStatus.GENERATING.value: "generation_agent",
    WorkflowStatus.REVIEWING.value: "review_agent",
    WorkflowStatus.REVISING.value: "generation_agent",
}

BASE_PROGRESS = {
    WorkflowStatus.CREATED.value: 0,
    WorkflowStatus.PROFILE_READY.value: 5,
    WorkflowStatus.ASSESSMENT_COMPLETED.value: 10,
    WorkflowStatus.DIAGNOSING.value: 20,
    # The questioning/updating pair loops; progress stays flat across the loop so
    # it never runs backwards when the learner answers another item.
    WorkflowStatus.DIAGNOSIS_QUESTIONING.value: 24,
    WorkflowStatus.LEARNER_MODEL_UPDATING.value: 27,
    WorkflowStatus.DIAGNOSIS_COMPLETED.value: 30,
    WorkflowStatus.PATH_PLANNING.value: 35,
    WorkflowStatus.RETRIEVING.value: 52,
    WorkflowStatus.GENERATING.value: 70,
    WorkflowStatus.REVIEWING.value: 84,
    WorkflowStatus.REVISING.value: 88,
    WorkflowStatus.PUBLISHED.value: 100,
    WorkflowStatus.FAILED.value: 100,
}

TERMINAL_STATES = {
    WorkflowStatus.PUBLISHED.value,
    WorkflowStatus.FAILED.value,
}


def _progress(session: WorkflowSession) -> int:
    """Keep progress monotonic across review/revision rounds."""
    if session.current_state == WorkflowStatus.REVIEWING.value and session.revision_count > 0:
        return min(95, 90 + session.revision_count * 2)
    return BASE_PROGRESS.get(session.current_state, 0)


def _status_schema(session: WorkflowSession) -> WorkflowStatusSchema:
    state = session.state_data or {}
    return WorkflowStatusSchema(
        workflow_id=session.id,
        status=session.current_state,
        current_agent=STATE_AGENT.get(session.current_state),
        progress=_progress(session),
        resource_id=state.get("resource_id"),
        error_message=state.get("error_message"),
    )


def _learner_schema(session: WorkflowSession) -> WorkflowLearnerState | None:
    """Expose the Beta-Bernoulli slice of workflow state, when diagnosis produced one."""
    state = session.state_data or {}
    if not any(state.get(key) for key in ("learner_state", "mastery_summary", "diagnosis_session_id")):
        return None
    return WorkflowLearnerState(
        learner_state=state.get("learner_state"),
        diagnosis_session_id=state.get("diagnosis_session_id"),
        mastery_summary=state.get("mastery_summary"),
        weak_concepts=state.get("weak_concepts") or [],
        uncertain_concepts=state.get("uncertain_concepts") or [],
    )


@router.post("", response_model=WorkflowCreateResponse, status_code=202)
async def create_workflow(
    data: WorkflowCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = Orchestrator(db)
    try:
        session = await orchestrator.create_workflow(
            learner_id=data.learner_id,
            domain_id=data.domain_id,
            target_goal=data.target_goal,
            assessment_id=data.assessment_id,
            target_skill_id=data.target_skill_id,
            version_filter=data.version_filter,
            diagnosis_mode=data.diagnosis_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    background_tasks.add_task(run_workflow_task, session.id)
    return WorkflowCreateResponse(workflow_id=session.id, status="queued")




@router.post("/{workflow_id}/retry", response_model=WorkflowCreateResponse, status_code=202)
async def retry_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a clean workflow using the failed/manual-review session context."""
    previous = await db.get(WorkflowSession, workflow_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if previous.current_state != WorkflowStatus.FAILED.value:
        raise HTTPException(status_code=409, detail="Only failed workflows can be retried")

    previous_state = previous.state_data or {}
    orchestrator = Orchestrator(db)
    try:
        session = await orchestrator.create_workflow(
            learner_id=previous.learner_id,
            domain_id=previous.domain_id,
            target_goal=previous.target_goal,
            assessment_id=None,
            target_skill_id=previous_state.get("source_skill_id"),
            version_filter=previous_state.get("version_filter"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    state = dict(session.state_data or {})
    for key in (
        "feedback",
        "source_resource_id",
        "source_skill_id",
        "requested_difficulty",
        "insert_skills",
        "version_filter",
    ):
        if key in previous_state:
            state[key] = previous_state[key]
    state["retry_of_workflow_id"] = workflow_id
    session.state_data = state
    await db.commit()
    background_tasks.add_task(run_workflow_task, session.id)
    return WorkflowCreateResponse(workflow_id=session.id, status="queued")


@router.get("/{workflow_id}", response_model=WorkflowStatusSchema)
async def get_workflow_status(workflow_id: str, db: AsyncSession = Depends(get_db)):
    session = await Orchestrator(db).get_workflow(workflow_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _status_schema(session)


@router.get("/{workflow_id}/trace", response_model=WorkflowTrace)
async def get_workflow_trace(workflow_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(WorkflowSession, workflow_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = await Orchestrator(db).get_agent_trace(workflow_id)
    return WorkflowTrace(runs=[AgentTraceItem(**item) for item in runs])


@router.get("/{workflow_id}/snapshot", response_model=WorkflowSnapshot)
async def get_workflow_snapshot(workflow_id: str, db: AsyncSession = Depends(get_db)):
    """Return status and trace in one request to avoid overlapping client polling."""
    session = await db.get(WorkflowSession, workflow_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = await Orchestrator(db).get_agent_trace(workflow_id)
    return WorkflowSnapshot(
        status=_status_schema(session),
        trace=WorkflowTrace(runs=[AgentTraceItem(**item) for item in runs]),
        learner=_learner_schema(session),
    )


@router.get("/{workflow_id}/events")
async def workflow_events(workflow_id: str, request: Request):
    """Push workflow changes without fixed-interval database polling."""
    queue = await subscribe(workflow_id)

    async def read_payload() -> tuple[str, bool]:
        async with async_session_factory() as db:
            session = await db.get(WorkflowSession, workflow_id)
            if session is None:
                return json.dumps({"error": "not_found"}), True
            payload = _status_schema(session).model_dump()
            return json.dumps(payload, ensure_ascii=False), session.current_state in TERMINAL_STATES

    async def event_stream():
        last_payload = ""
        try:
            while True:
                if await request.is_disconnected():
                    return
                payload, terminal = await read_payload()
                if payload != last_payload:
                    data = json.loads(payload)
                    status = data.get("status")
                    event_name = "workflow_completed" if status == "PUBLISHED" else (
                        "workflow_failed" if status == "FAILED" else "workflow_progress"
                    )
                    yield f"event: {event_name}\ndata: {payload}\n\n"
                    last_payload = payload
                if terminal:
                    return
                try:
                    await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await unsubscribe(workflow_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


async def _pause() -> None:
    await asyncio.sleep(max(0.0, settings.workflow_step_delay_seconds))


async def run_workflow_task(workflow_id: str) -> None:
    async with async_session_factory() as db:
        orchestrator = Orchestrator(db)
        session = await orchestrator.get_workflow(workflow_id)
        if session is None:
            return
        # Background task delivery can be retried by the runtime. Only an untouched
        # workflow may enter the pipeline; terminal or in-progress sessions are idempotent no-ops.
        if session.current_state != WorkflowStatus.ASSESSMENT_COMPLETED.value:
            return
        try:
            await orchestrator.transition_to(session, WorkflowStatus.DIAGNOSING)
            await db.commit()
            await _pause()

            if (session.state_data or {}).get("diagnosis_mode") == "adaptive":
                # Hand control to the learner: the pipeline cannot invent answers,
                # so it parks here and `resume_workflow_task` picks it up once the
                # interactive /diagnosis session has finished.
                await orchestrator.transition_to(session, WorkflowStatus.DIAGNOSIS_QUESTIONING)
                await db.commit()
                return

            await _run_diagnosis_agent(db, orchestrator, session)
            await _run_generation_pipeline(db, orchestrator, session)
        except Exception as exc:
            await _fail_workflow(db, workflow_id, exc)


async def resume_workflow_task(workflow_id: str) -> None:
    """Continue an adaptive workflow once its diagnosis session has completed."""
    async with async_session_factory() as db:
        orchestrator = Orchestrator(db)
        session = await orchestrator.get_workflow(workflow_id)
        if session is None or session.current_state != WorkflowStatus.DIAGNOSIS_COMPLETED.value:
            return
        try:
            await _run_diagnosis_agent(db, orchestrator, session)
            await _run_generation_pipeline(db, orchestrator, session)
        except Exception as exc:
            await _fail_workflow(db, workflow_id, exc)


async def _run_diagnosis_agent(
    db: AsyncSession,
    orchestrator: Orchestrator,
    session: WorkflowSession,
) -> None:
    """Turn the learner model into workflow state and a human-readable summary."""
    agent = DiagnosisAgent(LearnerModelService(db, domain_id=session.domain_id))
    await orchestrator.run_agent(session, "diagnosis_agent", agent.run, {})
    await db.commit()
    await _pause()


async def _fail_workflow(db: AsyncSession, workflow_id: str, exc: Exception) -> None:
    await db.rollback()
    session = await db.get(WorkflowSession, workflow_id)
    if session is None:
        return
    session.current_state = WorkflowStatus.FAILED.value
    state = dict(session.state_data or {})
    state["error_message"] = str(exc)
    session.state_data = state
    await db.commit()


async def _run_generation_pipeline(
    db: AsyncSession,
    orchestrator: Orchestrator,
    session: WorkflowSession,
) -> None:
    """Everything after diagnosis with risk-adaptive ProofGraph routing."""
    workflow_id = session.id

    # 1) Plan and retrieve first; the router needs learner uncertainty and
    # retrieval weakness but still makes no LLM call itself.
    for next_state, agent_name, agent in (
        (WorkflowStatus.PATH_PLANNING, "planner_agent", PlannerAgent()),
        (WorkflowStatus.RETRIEVING, "retrieval_agent", RetrievalAgent()),
    ):
        await orchestrator.transition_to(session, next_state)
        await _pause()
        await orchestrator.run_agent(session, agent_name, agent.run, {})
        await _pause()

    risk_result = await orchestrator.run_agent(
        session, "risk_router_service", RiskRouterAgent().run, {}
    )
    risk_route = risk_result.get("output", {}).get("risk_route", {})

    # 2) Generate once, then build the claim/evidence/validator graph before
    # review. ProofGraph is deterministic and therefore does not consume the
    # model-call budget.
    await orchestrator.transition_to(session, WorkflowStatus.GENERATING)
    await _pause()
    await orchestrator.run_agent(session, "generation_agent", GenerationAgent().run, {})
    await orchestrator.run_agent(session, "proofgraph_service", ProofGraphAgent().run, {})
    await _pause()

    await orchestrator.transition_to(session, WorkflowStatus.REVIEWING)
    review_result = await orchestrator.run_agent(session, "review_agent", ReviewAgent().run, {})
    await _pause()

    async def route_decision(current_review: dict) -> tuple[str, dict | None, dict | None]:
        await db.refresh(session)
        current_state = WorkflowState.from_dict(session.state_data or {})
        route = current_state.risk_route or risk_route
        critic_result: dict | None = None
        judge_result: dict | None = None

        if route.get("requires_critic"):
            critic_result = await orchestrator.run_agent(session, "critic_agent", CriticAgent().run, {})

        review_decision = current_review.get("output", {}).get("decision", "reject")
        critic_decision = (critic_result or {}).get("output", {}).get("decision", "approve")

        if route.get("requires_judge"):
            judge_result = await orchestrator.run_agent(session, "judge_agent", JudgeAgent().run, {})
            decision = judge_result.get("output", {}).get("decision", "reject")
        elif "reject" in {review_decision, critic_decision}:
            decision = "reject"
        elif "revise" in {review_decision, critic_decision}:
            decision = "revise"
        else:
            decision = "approve"
        return decision, critic_result, judge_result

    decision, critic_result, judge_result = await route_decision(review_result)

    # 3) Revision is bounded. Every revision rebuilds ProofGraph before review so
    # stale validation cannot leak into the published resource.
    while decision == "revise" and session.revision_count < settings.max_revision_count:
        revision_instructions = list((review_result or {}).get("output", {}).get("revision_instructions", []))
        for finding in (critic_result or {}).get("output", {}).get("findings", []):
            revision_instructions.append({
                "location": finding.get("path", "claim_graph"),
                "action": "modify",
                "reason": finding.get("reason", "争议声明需要补证据或降低风险"),
                "severity": "high",
            })

        await orchestrator.transition_to(session, WorkflowStatus.REVISING)
        state = dict(session.state_data or {})
        session.revision_count += 1
        state["revision_count"] = session.revision_count
        session.state_data = state
        await db.commit()

        await orchestrator.run_agent(
            session,
            "generation_agent",
            GenerationAgent().run,
            {"revision_instructions": revision_instructions},
        )
        await orchestrator.run_agent(session, "proofgraph_service", ProofGraphAgent().run, {})
        await _pause()

        await orchestrator.transition_to(session, WorkflowStatus.REVIEWING)
        review_result = await orchestrator.run_agent(session, "review_agent", ReviewAgent().run, {})
        decision, critic_result, judge_result = await route_decision(review_result)

    if decision != "approve":
        state = dict(session.state_data or {})
        issues = (review_result or {}).get("output", {}).get("issues", [])
        graph_summary = (state.get("claim_graph") or {}).get("summary", {})
        state["error_message"] = "自动审核未通过：" + (
            "；".join(str(item.get("description", item)) if isinstance(item, dict) else str(item) for item in issues)
            if issues else "资源未达到发布标准"
        )
        state["final_decision"] = "retry_required"
        state["proof_graph_summary"] = graph_summary
        session.state_data = state
        await orchestrator.transition_to(session, WorkflowStatus.FAILED)
        return

    # 4) Publish the auditable artifact: citations + review + risk route + graph.
    state = dict(session.state_data or {})
    generated = state.get("generated_resources") or {}
    review = state.get("review_result") or {}
    generation_run = (await db.execute(
        select(AgentRun)
        .where(AgentRun.workflow_id == workflow_id, AgentRun.agent_type == "generation_agent")
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    generation_output = (generation_run.output_json or {}).get("output", {}) if generation_run else {}
    citations = []
    evidence_map = {item.get("evidence_id"): item for item in state.get("evidence_list", [])}
    for evidence_id in generation_output.get("citations", []):
        evidence = evidence_map.get(evidence_id, {})
        citations.append({
            "evidence_id": evidence_id,
            "title": evidence.get("title", ""),
            "source_url": evidence.get("source_url", ""),
            "source_type": evidence.get("source_type", "local"),
            "verification_status": evidence.get("verification_status", "pending"),
        })

    metadata = dict(generation_output.get("metadata", {}))
    metadata["risk_route"] = state.get("risk_route") or {}
    metadata["proof_graph_summary"] = (state.get("claim_graph") or {}).get("summary", {})
    metadata["critic_result"] = state.get("critic_result") or {}
    metadata["judge_result"] = state.get("judge_result") or {}
    resource = GeneratedResource(
        workflow_id=workflow_id,
        resource_type="bundle",
        skill_id=generation_output.get("target_skill", "ros2_topic"),
        difficulty=generation_output.get("difficulty", "basic"),
        content_json={
            "resources": generated,
            "citations": citations,
            "review": review,
            "claim_graph": state.get("claim_graph") or {},
            "metadata": metadata,
        },
        model_name=metadata.get("model_version", "deterministic-template-v2"),
        prompt_version=metadata.get("prompt_version", "resource-generation-2.0"),
        status="published",
    )
    db.add(resource)
    await db.flush()
    scores = review.get("scores", {})
    db.add(ReviewRecord(
        resource_id=resource.id,
        review_round=max(1, session.revision_count + 1),
        factuality_score=scores.get("factuality"),
        coverage_score=scores.get("evidence_coverage"),
        difficulty_score=scores.get("difficulty_match"),
        actionability_score=scores.get("actionability"),
        decision="approve",
        issues_json=review.get("issues", []),
        revision_instructions=review.get("revision_instructions", []),
    ))
    state["resource_id"] = resource.id
    state["final_decision"] = "published"
    session.state_data = state
    await orchestrator.transition_to(session, WorkflowStatus.PUBLISHED)
    await db.commit()
