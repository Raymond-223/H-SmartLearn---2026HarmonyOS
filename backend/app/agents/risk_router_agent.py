"""Thin traceable wrapper around the deterministic risk router service."""

from app.agents.base import BaseAgent, AgentResult
from app.services.risk_router_service import RiskRouterService
from app.workflow.state import WorkflowState


class RiskRouterAgent(BaseAgent):
    agent_type = "risk_router_service"

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        route = RiskRouterService().assess(context).to_dict()
        return AgentResult(
            output={"risk_route": route},
            confidence=1.0,
            next_action="generate",
            summary=f"风险路由={route['route']}，PreRisk={route['pre_risk']}，模型预算≤{route['model_call_budget']}",
        )
