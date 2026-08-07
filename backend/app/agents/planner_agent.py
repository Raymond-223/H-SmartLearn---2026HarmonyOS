"""Prerequisite-aware planner with feedback-driven path adjustment."""

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState
from app.services.domain_package_service import topological_path


class PlannerAgent(BaseAgent):
    agent_type = "planner_agent"

    @staticmethod
    def _default_target(domain_id: str) -> str | None:
        if domain_id == "ros2_robotics":
            return "ros2_topic"
        if domain_id == "c_programming":
            return "c_pointer"
        return None

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        mastery = context.mastery_state or {}
        feedback = context.feedback or {}
        target_skill = context.source_skill_id or self._default_target(context.domain_id)

        nodes = topological_path(context.domain_id, target_skill)
        node_by_id = {node["id"]: node for node in nodes}
        ordered_ids = [node["id"] for node in nodes]

        # FeedbackAgent can explicitly reinsert prerequisite skills. Keep the graph order
        # and ignore unknown IDs rather than generating an invalid path.
        requested = [skill for skill in context.insert_skills if skill in node_by_id]
        if requested:
            requested_set = set(requested)
            ordered_ids = [skill for skill in ordered_ids if skill in requested_set or skill == target_skill]
            for skill in requested:
                if skill not in ordered_ids:
                    ordered_ids.insert(0, skill)

        path = []
        for order, skill_id in enumerate(ordered_ids, start=1):
            node = node_by_id[skill_id]
            score = (mastery.get(skill_id) or {}).get("score", 0)
            if skill_id in requested:
                reason = "反馈识别出的待补前置技能"
            elif skill_id == target_skill:
                reason = "当前主题核心技能"
            else:
                reason = "目标技能的前置依赖"
            path.append({
                "skill_id": skill_id,
                "name": node["name"],
                "order": order,
                "reason": reason,
                "estimated_minutes": node.get("estimated_minutes", 60),
                "mastery": score,
            })

        action = feedback.get("action", "initial")
        return AgentResult(
            output={
                "learning_path": path,
                "target_skills": [item["skill_id"] for item in path],
                "requested_difficulty": context.requested_difficulty,
                "feedback_action": action,
            },
            confidence=0.96,
            next_action="retrieve",
            summary=f"按技能依赖和反馈生成{len(path)}步合法学习路径",
        )
