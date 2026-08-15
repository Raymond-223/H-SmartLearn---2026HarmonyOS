"""Feedback Decision Agent.

The decision is domain-aware, uses server-derived scores, and never inserts a
skill from another domain.
"""

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState


class FeedbackAgent(BaseAgent):
    agent_type = "feedback_agent"

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        correct_rate = float(agent_input.get("correct_rate", 1.0) or 0.0)
        practice_score = float(agent_input.get("practice_score", 1.0) or 0.0)
        subjective = str(agent_input.get("subjective_difficulty", "appropriate"))
        error_tags = [str(item) for item in agent_input.get("error_tags", []) if str(item)]
        domain_id = context.domain_id
        prerequisite = "linux_environment" if domain_id == "ros2_robotics" else "c_basic"
        prerequisite_name = "Linux环境配置" if domain_id == "ros2_robotics" else "C语言基础"
        current_skill = context.source_skill_id or (context.target_skills[-1] if context.target_skills else prerequisite)

        if correct_rate < 0.6:
            suffix = f"；错题标签：{'、'.join(error_tags)}" if error_tags else ""
            return AgentResult(
                status="success",
                output={
                    "action": "lower_difficulty",
                    "reason": f"理论正确率低于60%，需要回补{prerequisite_name}{suffix}",
                    "insert_skills": [prerequisite],
                    "next_resource_level": "basic",
                },
                confidence=0.92,
                next_action="replan",
                summary=f"正确率不足60%，降低难度并补充{prerequisite_name}",
            )

        if practice_score < 0.5:
            return AgentResult(
                status="success",
                output={
                    "action": "add_practice",
                    "reason": "实操成功率低于50%，围绕当前技能追加可验证练习",
                    "insert_skills": [],
                    "next_resource_level": "basic",
                },
                confidence=0.9,
                next_action="replan",
                summary="实操成功率偏低，保持当前技能并增加基础实操",
            )

        if subjective == "too_hard":
            return AgentResult(
                status="success",
                output={
                    "action": "lower_difficulty",
                    "reason": "客观成绩已达标，但主观难度偏高；保留当前技能并降低下一份资源的信息密度",
                    "insert_skills": [current_skill],
                    "next_resource_level": "basic",
                },
                confidence=0.86,
                next_action="replan",
                summary="主观负荷偏高，当前技能以基础难度重新巩固",
            )

        level = "advanced" if subjective == "too_easy" and correct_rate >= 0.8 and practice_score >= 0.8 else "intermediate"
        reason = (
            "理论、实操均达标且主观难度偏低，可进入下一技能并提升资源难度"
            if level == "advanced"
            else "理论与实操达到要求，可进入学习路径中的下一技能"
        )
        return AgentResult(
            status="success",
            output={
                "action": "advance",
                "reason": reason,
                "insert_skills": [],
                "next_resource_level": level,
            },
            confidence=0.94,
            next_action="advance",
            summary="掌握度达标，进入下一技能",
        )
