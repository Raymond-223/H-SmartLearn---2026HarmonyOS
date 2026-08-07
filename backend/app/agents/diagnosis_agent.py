"""Diagnosis agent: explains deterministic mastery results."""

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState


class DiagnosisAgent(BaseAgent):
    agent_type = "diagnosis_agent"

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
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
