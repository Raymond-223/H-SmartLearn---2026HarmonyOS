"""Prerequisite-aware planner driven by the Beta-Bernoulli learner model."""

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState
from app.services.domain_package_service import topological_path

# A skill is only treated as already-known when the posterior is both high and
# tight. High-but-uncertain (one lucky answer) still earns a place in the path.
MASTERED_PROBABILITY = 0.75
MASTERED_UNCERTAINTY = 0.35
WEAK_PROBABILITY = 0.6


class PlannerAgent(BaseAgent):
    agent_type = "planner_agent"

    @staticmethod
    def _default_target(domain_id: str) -> str | None:
        if domain_id == "ros2_robotics":
            return "ros2_topic"
        if domain_id == "c_programming":
            return "c_pointer"
        return None

    @staticmethod
    def _posterior_by_skill(context: WorkflowState) -> dict[str, dict]:
        """Per-skill posterior, preferring the learner model over legacy scores."""
        summary = context.mastery_summary or {}
        probabilities = summary.get("skill_mastery") or {}
        uncertainties = summary.get("skill_uncertainty") or {}

        states = {}
        learner_state = context.learner_state or {}
        for state in learner_state.get("skill_states") or []:
            states[state["skill_id"]] = state

        by_skill: dict[str, dict] = {}
        for skill_id in set(probabilities) | set(states):
            state = states.get(skill_id, {})
            by_skill[skill_id] = {
                "mastery_probability": probabilities.get(
                    skill_id, state.get("mastery_probability", 0.5)
                ),
                "uncertainty": uncertainties.get(skill_id, state.get("uncertainty", 1.0)),
                "tested_concept_count": state.get("tested_concept_count", 0),
                "weak_concept_ids": list(state.get("weak_concept_ids") or []),
            }

        # Fall back to the legacy 0-100 mastery_state for skills the model has
        # nothing on, so a workflow that never ran adaptive diagnosis still plans.
        for skill_id, legacy in (context.mastery_state or {}).items():
            if skill_id in by_skill:
                continue
            score = float((legacy or {}).get("score", 0))
            confidence = float((legacy or {}).get("confidence", 0.5))
            by_skill[skill_id] = {
                "mastery_probability": round(score / 100.0, 4),
                "uncertainty": round(max(0.0, 1.0 - confidence), 4),
                "tested_concept_count": 1 if score else 0,
                "weak_concept_ids": [],
            }
        return by_skill

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
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

        posteriors = self._posterior_by_skill(context)
        weak_by_skill: dict[str, list[str]] = {}
        for concept in context.weak_concepts or []:
            weak_by_skill.setdefault(concept.get("skill_id"), []).append(concept["concept_id"])
        uncertain_by_skill: dict[str, list[str]] = {}
        for concept in context.uncertain_concepts or []:
            uncertain_by_skill.setdefault(concept.get("skill_id"), []).append(concept["concept_id"])

        path = []
        focus_count = 0
        for order, skill_id in enumerate(ordered_ids, start=1):
            node = node_by_id[skill_id]
            posterior = posteriors.get(skill_id, {})
            probability = float(posterior.get("mastery_probability", 0.5))
            uncertainty = float(posterior.get("uncertainty", 1.0))
            tested = int(posterior.get("tested_concept_count", 0))
            weak_concepts = weak_by_skill.get(skill_id) or posterior.get("weak_concept_ids") or []
            uncertain_concepts = uncertain_by_skill.get(skill_id, [])

            if tested == 0:
                status = "unassessed"
            elif probability < WEAK_PROBABILITY:
                status = "focus"
            elif probability >= MASTERED_PROBABILITY and uncertainty <= MASTERED_UNCERTAINTY:
                status = "mastered"
            else:
                status = "reinforce"

            if skill_id in requested:
                reason = "反馈识别出的待补前置技能"
            elif status == "focus":
                reason = f"掌握度{probability:.0%}低于阈值，需重点补强"
            elif status == "mastered":
                reason = f"掌握度{probability:.0%}且证据充分，可快速复习"
            elif status == "unassessed":
                reason = "尚无诊断证据，按前置依赖保留"
            elif skill_id == target_skill:
                reason = "当前主题核心技能"
            else:
                reason = f"掌握度{probability:.0%}但仍有不确定性，需巩固"

            if status == "focus":
                focus_count += 1

            path.append({
                "skill_id": skill_id,
                "name": node["name"],
                "order": order,
                "reason": reason,
                "estimated_minutes": node.get("estimated_minutes", 60),
                # Legacy 0-100 field the dashboard renders.
                "mastery": round(100.0 * probability, 1),
                "mastery_probability": round(probability, 4),
                "uncertainty": round(uncertainty, 4),
                "status": status,
                # A mastered prerequisite stays in the path (it is still a
                # dependency) but is flagged so the UI can collapse it.
                "skippable": status == "mastered" and skill_id != target_skill,
                "weak_concept_ids": weak_concepts,
                "uncertain_concept_ids": uncertain_concepts,
            })

        action = feedback.get("action", "initial")
        focus_skills = [item["skill_id"] for item in path if item["status"] == "focus"]
        summary = f"按技能依赖和学习者模型生成{len(path)}步合法学习路径"
        if focus_count:
            summary += f"，其中{focus_count}步需重点补强"

        return AgentResult(
            output={
                "learning_path": path,
                "target_skills": [item["skill_id"] for item in path],
                "focus_skills": focus_skills,
                "requested_difficulty": context.requested_difficulty,
                "feedback_action": action,
            },
            confidence=0.96,
            next_action="retrieve",
            summary=summary,
        )
