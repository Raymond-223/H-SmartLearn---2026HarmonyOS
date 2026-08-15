"""Deterministic ProofGraph builder/validator."""

from app.agents.base import BaseAgent, AgentResult
from app.services.claim_graph_service import ClaimGraphService
from app.workflow.state import WorkflowState


class ProofGraphAgent(BaseAgent):
    agent_type = "proofgraph_service"

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        graph = ClaimGraphService(context.domain_id).build(context)
        summary = graph["summary"]
        blocking = bool(summary["unresolved_high_risk_claim_ids"] or summary["rejected_claim_count"])
        return AgentResult(
            output={"claim_graph": graph, "blocking": blocking},
            confidence=1.0,
            next_action="review",
            summary=(
                f"ProofGraph构建{summary['claim_count']}个声明；"
                f"高风险未决{len(summary['unresolved_high_risk_claim_ids'])}个"
            ),
        )
