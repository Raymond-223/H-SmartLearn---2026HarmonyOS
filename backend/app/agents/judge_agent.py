"""Deterministic fusion Judge; an LLM is not called unless a future policy needs it."""

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState


class JudgeAgent(BaseAgent):
    agent_type = "judge_agent"

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        review = context.review_result or {}
        critic = context.critic_result or {}
        graph_summary = (context.claim_graph or {}).get("summary", {})
        review_decision = str(review.get("decision", "reject"))
        critic_decision = str(critic.get("decision", "approve"))

        if graph_summary.get("rejected_claim_count", 0) or "reject" in {review_decision, critic_decision}:
            decision = "reject"
        elif graph_summary.get("unresolved_high_risk_claim_ids") or "revise" in {review_decision, critic_decision}:
            decision = "revise"
        else:
            decision = "approve"
        return AgentResult(
            output={
                "decision": decision,
                "review_decision": review_decision,
                "critic_decision": critic_decision,
                "high_risk_unresolved": len(graph_summary.get("unresolved_high_risk_claim_ids", [])),
            },
            confidence=0.98,
            next_action=decision,
            summary=f"Judge融合裁决：{decision}",
        )
