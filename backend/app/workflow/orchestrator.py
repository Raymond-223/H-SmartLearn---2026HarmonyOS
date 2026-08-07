"""Central, auditable controller for the multi-agent state machine."""

import logging
from typing import Optional, Callable, Awaitable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult
from app.workflow.state import WorkflowState
from app.workflow.transitions import WorkflowStatus, validate_transition
from app.workflow.event_bus import publish_workflow_event
from app.models.workflow import WorkflowSession, AgentRun
from app.models.learner import LearnerProfile
from app.models.assessment import AssessmentSession, MasteryState
from app.services.domain_package_service import load_skill_nodes

from app.core.time import utc_now
logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_workflow(
        self,
        learner_id: str,
        domain_id: str,
        target_goal: Optional[str] = None,
        assessment_id: Optional[str] = None,
        target_skill_id: Optional[str] = None,
        version_filter: Optional[str] = None,
    ) -> WorkflowSession:
        learner = await self.db.get(LearnerProfile, learner_id)
        if learner is None:
            raise ValueError("learner not found")
        valid_skills = {str(item.get("id")) for item in load_skill_nodes(domain_id)}
        if target_skill_id is not None and target_skill_id not in valid_skills:
            raise ValueError(f"target skill does not belong to domain: {domain_id}/{target_skill_id}")

        assessment_result = None
        if assessment_id:
            assessment = await self.db.get(AssessmentSession, assessment_id)
            if assessment is None or assessment.learner_id != learner_id:
                raise ValueError("assessment not found for learner")
            if assessment.status != "completed":
                raise ValueError("assessment is not completed")
            assessment_result = assessment.result_json or {}

        mastery_rows = list((await self.db.execute(
            select(MasteryState).where(MasteryState.learner_id == learner_id)
        )).scalars().all())
        mastery = {
            row.skill_id: {"score": row.mastery_score, "confidence": row.confidence or 0}
            for row in mastery_rows
        }

        session = WorkflowSession(
            learner_id=learner_id,
            domain_id=domain_id,
            target_goal=target_goal,
            current_state=WorkflowStatus.CREATED.value,
        )
        self.db.add(session)
        await self.db.flush()

        state = WorkflowState(
            workflow_id=session.id,
            learner_id=learner_id,
            domain_id=domain_id,
            target_goal=target_goal,
            learner_profile={
                "education": learner.education,
                "major": learner.major,
                "target_role": learner.target_role,
                "weekly_hours": learner.weekly_hours,
                "preferences": learner.preference_json or {},
            },
            assessment_result=assessment_result,
            mastery_state=mastery,
            source_skill_id=target_skill_id,
            version_filter=version_filter,
        )
        session.state_data = state.to_dict()
        await self.transition_to(session, WorkflowStatus.PROFILE_READY)
        await self.transition_to(session, WorkflowStatus.ASSESSMENT_COMPLETED)
        logger.info("Workflow created: %s", session.id)
        return session

    async def transition_to(self, session: WorkflowSession, next_state: WorkflowStatus) -> None:
        current = WorkflowStatus(session.current_state)
        if not validate_transition(current, next_state):
            raise ValueError(f"invalid transition: {current.value} -> {next_state.value}")
        session.current_state = next_state.value
        session.updated_at = utc_now()
        # Publish only after commit so SSE readers cannot observe a stale state.
        await self.db.commit()
        await publish_workflow_event(session.id)

    async def run_agent(
        self,
        session: WorkflowSession,
        agent_type: str,
        agent_func: Callable[[WorkflowState, dict], Awaitable[AgentResult]],
        agent_input: dict,
    ) -> dict:
        run = AgentRun(
            workflow_id=session.id,
            agent_type=agent_type,
            input_json=agent_input,
            status="running",
            started_at=utc_now(),
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.commit()

        try:
            await self.db.refresh(session)
            state = WorkflowState.from_dict(session.state_data or {})
            agent_result = await agent_func(state, agent_input)
            result = agent_result.model_dump()

            run.output_json = result
            run.status = result.get("status", "success")
            run.confidence = result.get("confidence")
            run.finished_at = utc_now()

            self._merge_agent_output(state, agent_type, result.get("output") or {})
            state.agent_trace.append({
                "agent": agent_type,
                "status": run.status,
                "confidence": run.confidence,
                "summary": result.get("summary", ""),
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat(),
            })
            session.state_data = state.to_dict()
            session.updated_at = utc_now()
            # Commit the state and trace atomically before notifying SSE subscribers.
            await self.db.commit()
            await publish_workflow_event(session.id)
            return result
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = utc_now()
            session.current_state = WorkflowStatus.FAILED.value
            state = WorkflowState.from_dict(session.state_data or {})
            state.error_message = str(exc)
            session.state_data = state.to_dict()
            session.updated_at = utc_now()
            await self.db.commit()
            await publish_workflow_event(session.id)
            logger.exception("Agent %s failed", agent_type)
            raise

    @staticmethod
    def _merge_agent_output(state: WorkflowState, agent_type: str, output: dict) -> None:
        if agent_type == "diagnosis_agent":
            state.mastery_state = output.get("mastery", state.mastery_state)
            state.target_skills = list((state.mastery_state or {}).keys())
        elif agent_type == "planner_agent":
            state.learning_path = output.get("learning_path", [])
            state.target_skills = output.get("target_skills", state.target_skills)
        elif agent_type == "retrieval_agent":
            state.evidence_list = output.get("evidence_list", [])
        elif agent_type == "generation_agent":
            state.generated_resources = output.get("resources")
        elif agent_type == "review_agent":
            state.review_result = output
        elif agent_type == "feedback_agent":
            state.feedback = output

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowSession]:
        return (await self.db.execute(
            select(WorkflowSession).where(WorkflowSession.id == workflow_id)
        )).scalar_one_or_none()

    async def get_agent_trace(self, workflow_id: str) -> list[dict]:
        runs = list((await self.db.execute(
            select(AgentRun)
            .where(AgentRun.workflow_id == workflow_id)
            .order_by(AgentRun.started_at)
        )).scalars().all())
        return [{
            "agent": run.agent_type,
            "status": run.status,
            "summary": (run.output_json or {}).get("summary", ""),
            "confidence": run.confidence,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        } for run in runs]
