"""Prompt construction for evidence-grounded learning resources."""

import json

from app.workflow.state import WorkflowState


SYSTEM_INSTRUCTIONS = """你是学习资源生成 Agent。只能依据给定证据生成内容，不得编造来源。
仅输出一个合法 JSON 对象，不要输出 Markdown 代码块或额外说明。
JSON 顶层必须包含 resources；resources 必须包含 lecture、practice_guide、graded_test。
lecture.sections 每节必须包含 heading、content、citations；citations 只能使用给定 evidence_id。
practice_guide 必须包含 steps、safety_notes；每个 step 必须包含 order、title、command、expected_result、skill_id。
graded_test.items 至少 3 题，每题必须包含 id、type、difficulty、stem、options、correct_answer、skill_id、explanation。
ROS2 领域所有实操步骤必须明确 ros_version=humble。"""


def build_resource_prompt(context: WorkflowState, *, difficulty: str, revision_instructions: list[str]) -> str:
    evidence = []
    for item in context.evidence_list[:8]:
        evidence.append({
            "evidence_id": item.get("evidence_id"),
            "title": item.get("title"),
            "source_url": item.get("source_url"),
            "version": item.get("version"),
            "content": str(item.get("content", ""))[:1800],
        })
    request = {
        "domain_id": context.domain_id,
        "target_goal": context.target_goal,
        "target_skills": context.target_skills,
        "difficulty": difficulty,
        "learner_profile": context.learner_profile or {},
        "assessment_result": context.assessment_result or {},
        "feedback": context.feedback or {},
        "revision_instructions": revision_instructions,
        "evidence": evidence,
    }
    return "根据以下输入生成可审核学习资源：\n" + json.dumps(request, ensure_ascii=False)
