"""Diagnosis agent: organises the diagnosis step and narrates its result.

The agent owns no inference. Deciding *what to ask* belongs to
InformationGainDiagnosisService, and deciding *what an answer means* belongs to
LearnerModelService; this class only sequences those two and turns their output
into something a human reads.

Agents stay database-free (see ``app.agents.base``), so the services are
injected by whoever has a session — the workflow driver in ``api/workflows.py``.
When they are absent the agent degrades to the legacy fixed-assessment summary
so an already-scored workflow still completes.
"""

from typing import Optional

from app.agents.base import BaseAgent, AgentResult
from app.services.information_gain_diagnosis_service import (
    InformationGainDiagnosisService,
    SessionContext,
)
from app.services.learner_model_service import LearnerModelService
from app.workflow.state import WorkflowState


class DiagnosisAgent(BaseAgent):
    agent_type = "diagnosis_agent"

    def __init__(
        self,
        learner_model: Optional[LearnerModelService] = None,
        diagnosis_service: Optional[InformationGainDiagnosisService] = None,
    ) -> None:
        self.learner_model = learner_model
        if diagnosis_service is not None:
            self.diagnosis_service = diagnosis_service
        elif learner_model is not None:
            self.diagnosis_service = InformationGainDiagnosisService(learner_model)
        else:
            self.diagnosis_service = None

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        if self.learner_model is None or self.diagnosis_service is None:
            return self._from_legacy_assessment(context)
        return await self._from_learner_model(context)

    # ------------------------------------------------------------ model-backed

    async def _from_learner_model(self, context: WorkflowState) -> AgentResult:
        learner_id = context.learner_id
        profile = await self.learner_model.get_ability_profile(learner_id)
        weak = await self.learner_model.get_weak_concepts(learner_id, limit=10)
        uncertain = await self.learner_model.get_uncertain_concepts(learner_id, limit=10)

        skill_states = profile["skill_states"]
        mastery_summary = {
            "overall_mastery": profile["overall_mastery"],
            "overall_uncertainty": profile["overall_uncertainty"],
            "recommended_level": profile["recommended_level"],
            "concept_coverage": profile["concept_coverage"],
            "tested_concept_count": profile["tested_concept_count"],
            "total_concept_count": profile["total_concept_count"],
            "skill_mastery": {
                state["skill_id"]: state["mastery_probability"] for state in skill_states
            },
            "skill_uncertainty": {
                state["skill_id"]: state["uncertainty"] for state in skill_states
            },
        }

        # The legacy 0-100 view the dashboard and PlannerAgent still read. Only
        # skills with evidence appear; an untested skill sits at the 0.5 prior,
        # which means *unknown* and would read as a score of 50.
        mastery = {
            state["skill_id"]: {
                "score": round(100.0 * state["mastery_probability"], 1),
                "confidence": round(1.0 - state["uncertainty"], 2),
            }
            for state in skill_states
            if state["tested_concept_count"] > 0
        }
        if not mastery:
            # No adaptive evidence yet: keep whatever a fixed assessment measured
            # rather than blanking the state the planner depends on.
            mastery = (context.assessment_result or {}).get("mastery") or context.mastery_state or {}

        # Is the posterior good enough to plan against, or is more evidence worth
        # gathering? The selector answers with the same rule the live session uses.
        session_context = SessionContext(
            tested_concept_ids=[
                concept["concept_id"]
                for state in skill_states
                for concept in state["concepts"]
                if concept["attempt_count"] > 0
            ],
            question_count=int(profile["total_attempts"]),
            target_skill_id=context.source_skill_id,
        )
        stop, stop_reason = await self.diagnosis_service.should_stop(learner_id, session_context)
        needs_more = not stop

        weak_names = [state.name or state.concept_id for state in weak[:3]]
        if not weak_names:
            weak_names = (context.assessment_result or {}).get("knowledge_gaps") or []
        if profile["tested_concept_count"] == 0:
            summary = "尚无自适应诊断证据，按既有测评结果规划，建议补做诊断以降低不确定性。"
        else:
            summary = (
                f"诊断完成：已测{profile['tested_concept_count']}/"
                f"{profile['total_concept_count']}个概念，"
                f"整体掌握度{profile['overall_mastery']:.0%}，"
                f"不确定度{profile['overall_uncertainty']:.2f}。"
                + (f"优先补强：{'、'.join(weak_names)}。" if weak_names else "暂无明显薄弱概念。")
            )

        return AgentResult(
            output={
                "mastery": mastery,
                "learner_state": {
                    "learner_id": learner_id,
                    "domain_id": profile["domain_id"],
                    "ability_profile": profile,
                    "skill_states": skill_states,
                    "weak_concept_ids": [state.concept_id for state in weak],
                    "uncertain_concept_ids": [state.concept_id for state in uncertain],
                },
                "mastery_summary": mastery_summary,
                "weak_concepts": [state.to_dict() for state in weak],
                "uncertain_concepts": [state.to_dict() for state in uncertain],
                "diagnosis_session_id": context.diagnosis_session_id,
                "knowledge_gaps": weak_names,
                "recommended_level": profile["recommended_level"],
                "needs_more_diagnosis": needs_more,
                "stop_reason": stop_reason,
            },
            # Confidence is the model's own certainty, not a hand-picked number.
            confidence=round(1.0 - profile["overall_uncertainty"], 2),
            next_action="diagnose" if needs_more else "plan",
            summary=summary,
        )

    # ----------------------------------------------------------------- fallback

    def _from_legacy_assessment(self, context: WorkflowState) -> AgentResult:
        """Summarise a fixed assessment when no learner model is wired in."""
        assessment = context.assessment_result or {}
        mastery = assessment.get("mastery") or context.mastery_state or {}
        gaps = assessment.get("knowledge_gaps", [])
        level = assessment.get("recommended_level", "basic")
        weakest = sorted(mastery.items(), key=lambda item: item[1].get("score", 0))[:2]
        weak_text = "、".join(skill_id for skill_id, _ in weakest) or "待完成诊断"
        return AgentResult(
            output={"mastery": mastery, "knowledge_gaps": gaps, "recommended_level": level},
            confidence=0.9 if mastery else 0.65,
            next_action="plan",
            summary=f"诊断完成，优先补强：{weak_text}",
        )
