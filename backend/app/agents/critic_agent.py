"""Targeted critic for disputed/high-risk ProofGraph claims.

The critic is deterministic by default. It only inspects claims already marked
unsupported, conflicting, rejected or needing confirmation; it never rewrites
an otherwise-valid full response.
"""

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState


class CriticAgent(BaseAgent):
    agent_type = "critic_agent"

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        graph = context.claim_graph or {}
        claims = graph.get("claims", []) if isinstance(graph, dict) else []
        findings: list[dict] = []
        for claim in claims:
            disposition = str(claim.get("final_disposition", "PASS"))
            risk = str(claim.get("risk_level", "low"))
            if disposition in {"REJECT", "NEED_CONFIRMATION"} or (
                risk in {"medium", "high", "critical"} and claim.get("evidence_status") != "supported"
            ):
                findings.append({
                    "claim_id": claim.get("claim_id"),
                    "path": claim.get("path"),
                    "risk_level": risk,
                    "disposition": disposition,
                    "reason": "关键声明未满足证据/验证发布门",
                })

        if any(item["disposition"] == "REJECT" for item in findings):
            decision = "reject"
        elif findings:
            decision = "revise"
        else:
            decision = "approve"
        return AgentResult(
            output={
                "decision": decision,
                "findings": findings,
                "reviewed_claim_count": len(findings),
            },
            confidence=0.96,
            next_action=decision,
            summary="定向Critic未发现新增阻断问题" if not findings else f"定向Critic复查{len(findings)}个争议声明",
        )
