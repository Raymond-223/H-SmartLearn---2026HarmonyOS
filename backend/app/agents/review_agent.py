"""Three-layer content review: structure, evidence, and safe execution."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.validators import KnowledgePointValidator
from app.workflow.state import WorkflowState


class ReviewAgent(BaseAgent):
    agent_type = "review_agent"

    _unsafe_command_rules = (
        (re.compile(r"(^|[;&|]\s*)sudo(?:\s|$)", re.IGNORECASE), "命令要求sudo提权"),
        (re.compile(r"\brm\s+-[^\n]*r[^\n]*f[^\n]*(?:\s/|\s~(?:/|\s|$))", re.IGNORECASE), "命令可能递归删除系统或用户目录"),
        (re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba)?sh\b", re.IGNORECASE), "命令直接执行网络下载脚本"),
        (re.compile(r"\b(?:mkfs(?:\.[a-z0-9]+)?|shutdown|reboot)\b", re.IGNORECASE), "命令包含系统破坏或停机操作"),
        (re.compile(r"\bdd\b[^\n]*\bof=/dev/", re.IGNORECASE), "命令可能覆盖块设备"),
        (re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE), "命令会丢弃未提交修改"),
        (re.compile(r"\bchmod\s+(?:-R\s+)?777\b", re.IGNORECASE), "命令授予过宽文件权限"),
    )

    @staticmethod
    def _issue(layer: str, issue_type: str, location: str, description: str, severity: str | None = None) -> dict[str, str]:
        if severity is None:
            severity = "high" if issue_type in {"unsafe_command", "evidence_unverified", "version"} else "medium"
        return {
            "layer": layer,
            "type": issue_type,
            "location": location,
            "description": description,
            "severity": severity,
        }

    @staticmethod
    def _layer(level: int, name: str, issues: list[dict]) -> dict:
        return {
            "level": level,
            "name": name,
            "status": "pass" if not issues else "fail",
            "issue_count": len(issues),
            "issues": issues,
        }

    @staticmethod
    def _target_skill(context: WorkflowState) -> str:
        return context.source_skill_id or (context.target_skills[-1] if context.target_skills else "")

    def _review_structure(
        self,
        context: WorkflowState,
        resources: dict,
        knowledge_point: object,
        known_skill_ids: set[str] | None,
    ) -> tuple[list[dict], dict, bool]:
        layer = "structure"
        issues: list[dict] = []
        validator = KnowledgePointValidator.validate(knowledge_point, known_ids=known_skill_ids)
        issues.extend(
            self._issue(layer, item["type"], item["location"], item["description"])
            for item in validator["issues"]
        )

        for required in ("lecture", "practice_guide", "graded_test"):
            if not isinstance(resources.get(required), dict):
                issues.append(self._issue(layer, "structure", required, "缺少必需资源或资源不是JSON对象"))

        lecture = resources.get("lecture") if isinstance(resources.get("lecture"), dict) else {}
        sections = lecture.get("sections", [])
        if not isinstance(sections, list):
            issues.append(self._issue(layer, "structure", "lecture.sections", "讲义章节必须是数组"))
            sections = []
        if len(sections) < 2:
            issues.append(self._issue(layer, "coverage", "lecture.sections", "讲义章节少于2节"))

        analogy_found = False
        all_lecture_text: list[str] = []
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                issues.append(self._issue(layer, "structure", f"lecture.sections.{index}", "讲义章节必须是JSON对象"))
                continue
            for field in ("heading", "content", "citations"):
                if field not in section:
                    issues.append(self._issue(layer, "structure", f"lecture.sections.{index}.{field}", f"讲义章节缺少{field}"))
            content = str(section.get("content", ""))
            all_lecture_text.append(content)
            analogy_found = analogy_found or any(word in content for word in ("像", "就像", "类比", "广播"))

        # 类比属于教学风格，不作为所有用户的硬性审核条件

        normalized_lecture = " ".join(all_lecture_text).lower()
        if context.domain_id == "ros2_robotics" and not any(
            term in normalized_lecture for term in ("ros2", "ros 2", "节点", "topic", "话题")
        ):
            issues.append(self._issue(layer, "domain_consistency", "lecture", "ROS2领域讲义缺少ROS2核心语境"))
        if context.domain_id == "c_programming" and not any(
            term in normalized_lecture for term in ("c语言", "c程序", "编译", "变量", "函数", "指针")
        ):
            issues.append(self._issue(layer, "domain_consistency", "lecture", "C语言领域讲义缺少C语言核心语境"))

        guide = resources.get("practice_guide") if isinstance(resources.get("practice_guide"), dict) else {}
        steps = guide.get("steps", [])
        if not isinstance(steps, list):
            issues.append(self._issue(layer, "structure", "practice_guide.steps", "实操步骤必须是数组"))
            steps = []
        if len(steps) < 2:
            issues.append(self._issue(layer, "coverage", "practice_guide.steps", "实操步骤少于2步"))
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                issues.append(self._issue(layer, "structure", f"practice_guide.steps.{index}", "实操步骤必须是JSON对象"))
                continue
            for field in ("order", "title", "command", "expected_result", "skill_id"):
                if not step.get(field):
                    issues.append(self._issue(layer, "structure", f"practice_guide.steps.{index}.{field}", f"实操步骤缺少{field}"))

        graded_test = resources.get("graded_test") if isinstance(resources.get("graded_test"), dict) else {}
        items = graded_test.get("items", [])
        if not isinstance(items, list):
            issues.append(self._issue(layer, "structure", "graded_test.items", "测试题必须是数组"))
            items = []
        if len(items) < 3:
            issues.append(self._issue(layer, "coverage", "graded_test.items", "分阶测试少于3题"))

        target_skill = self._target_skill(context)
        planned = {str(entry.get("skill_id", "")) for entry in context.learning_path if isinstance(entry, dict)}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                issues.append(self._issue(layer, "structure", f"graded_test.items.{index}", "测试题必须是JSON对象"))
                continue
            for field in ("id", "type", "difficulty", "stem", "options", "correct_answer", "explanation", "skill_id"):
                if not item.get(field):
                    issues.append(self._issue(layer, "structure", f"graded_test.items.{index}.{field}", f"测试题缺少{field}"))
            options = item.get("options", [])
            if not isinstance(options, list):
                issues.append(self._issue(layer, "structure", f"graded_test.items.{index}.options", "选项必须是数组"))
                options = []
            option_keys = {
                str(option.get("key", "")) for option in options if isinstance(option, dict) and option.get("key")
            }
            if item.get("correct_answer") and str(item.get("correct_answer")) not in option_keys:
                issues.append(self._issue(layer, "answer_consistency", f"graded_test.items.{index}.correct_answer", "正确答案不在可选项中"))
            item_skill = str(item.get("skill_id", ""))
            allowed_skills = set(context.target_skills) | planned | ({target_skill} if target_skill else set())
            if item_skill and allowed_skills and item_skill not in allowed_skills:
                issues.append(self._issue(layer, "skill_consistency", f"graded_test.items.{index}.skill_id", f"测试题技能{item_skill}不在当前学习路径中"))

        return issues, validator, analogy_found

    def _review_evidence(self, resources: dict, evidence_list: list[dict]) -> list[dict]:
        layer = "evidence"
        issues: list[dict] = []
        evidence_map = {
            str(item.get("evidence_id")): item
            for item in evidence_list
            if isinstance(item, dict) and item.get("evidence_id")
        }

        if not evidence_map:
            issues.append(self._issue(layer, "evidence_missing", "evidence_list", "审核上下文没有可用证据"))
            return issues

        def check_ids(ids: object, location: str, required: bool = True, strict_presence: bool = True) -> None:
            if not isinstance(ids, list) or not ids:
                if required:
                    issues.append(self._issue(layer, "citation", location, "缺少证据引用"))
                return
            for citation in ids:
                evidence = evidence_map.get(str(citation))
                if evidence is None:
                    if strict_presence:
                        issues.append(self._issue(layer, "citation", location, f"引用不存在的证据 {citation}"))
                    continue
                verification_status = str(evidence.get("verification_status", "pending"))
                risk_level = str(evidence.get("risk_level", "low")).lower()
                if verification_status == "verified":
                    pass
                elif verification_status == "trusted_source":
                    # Source acceptance and claim-level validation are separate gates.
                    # High-risk use is enforced by the ProofGraph layer below.
                    pass
                else:
                    issues.append(self._issue(layer, "evidence_unverified", f"evidence_list.{citation}", f"证据 {citation} 未通过可接受的验证门"))
                if not str(evidence.get("content", "")).strip():
                    issues.append(self._issue(layer, "evidence_empty", f"evidence_list.{citation}", f"证据 {citation} 没有可核验内容"))
                source_type = str(evidence.get("source_type", "local"))
                if source_type in {"web", "official"}:
                    parsed = urlparse(str(evidence.get("source_url", "")))
                    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                        issues.append(self._issue(layer, "evidence_source", f"evidence_list.{citation}.source_url", f"证据 {citation} 缺少有效来源地址"))

        lecture = resources.get("lecture") if isinstance(resources.get("lecture"), dict) else {}
        sections = lecture.get("sections", []) if isinstance(lecture.get("sections", []), list) else []
        for index, section in enumerate(sections):
            if isinstance(section, dict):
                check_ids(section.get("citations", []), f"lecture.sections.{index}.citations", required=True)

        guide = resources.get("practice_guide") if isinstance(resources.get("practice_guide"), dict) else {}
        # Procedure-level evidence is preferred; step-level evidence is checked when present.
        check_ids(guide.get("evidence_ids", []), "practice_guide.evidence_ids", required=False, strict_presence=False)
        for index, step in enumerate(guide.get("steps", []) if isinstance(guide.get("steps", []), list) else []):
            if isinstance(step, dict) and "evidence_ids" in step:
                check_ids(step.get("evidence_ids", []), f"practice_guide.steps.{index}.evidence_ids", required=False, strict_presence=False)

        graded = resources.get("graded_test") if isinstance(resources.get("graded_test"), dict) else {}
        for index, item in enumerate(graded.get("items", []) if isinstance(graded.get("items", []), list) else []):
            if isinstance(item, dict) and "evidence_ids" in item:
                check_ids(item.get("evidence_ids", []), f"graded_test.items.{index}.evidence_ids", required=False, strict_presence=False)

        return issues

    def _review_safe_execution(self, resources: dict, context: WorkflowState) -> list[dict]:
        layer = "safe_execution"
        issues: list[dict] = []
        guide = resources.get("practice_guide") if isinstance(resources.get("practice_guide"), dict) else {}
        safety_notes = guide.get("safety_notes", [])
        if not isinstance(safety_notes, list) or not any(str(note).strip() for note in safety_notes):
            issues.append(self._issue(layer, "safety", "practice_guide.safety_notes", "缺少可执行前阅读的安全提示"))

        guide_risk = str(guide.get("risk_level", "low")).lower()
        if guide_risk in {"medium", "high", "critical"}:
            rollback = guide.get("rollback", [])
            if not isinstance(rollback, list) or not any(str(item).strip() for item in rollback):
                issues.append(self._issue(layer, "rollback", "practice_guide.rollback", "中高风险实操缺少回滚步骤", "high"))

        steps = guide.get("steps", []) if isinstance(guide.get("steps", []), list) else []
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            command = str(step.get("command", "")).strip()
            if not command:
                continue
            for pattern, description in self._unsafe_command_rules:
                if pattern.search(command):
                    issues.append(self._issue(layer, "unsafe_command", f"practice_guide.steps.{index}.command", description))
            required_version = getattr(context, "version_filter", None)
            if context.domain_id == "ros2_robotics" and required_version:
                if str(step.get("ros_version", "")).lower() != str(required_version).lower():
                    issues.append(self._issue(layer, "version", f"practice_guide.steps.{index}.ros_version", "实操命令版本与当前任务版本不一致"))
        return issues

    def _review_proof_graph(self, context: WorkflowState) -> list[dict]:
        layer = "proof_graph"
        issues: list[dict] = []
        graph = context.claim_graph or {}
        summary = graph.get("summary", {}) if isinstance(graph, dict) else {}
        if not graph:
            return []
        for claim_id in summary.get("unresolved_high_risk_claim_ids", []) or []:
            issues.append(self._issue(
                layer, "high_risk_unresolved", f"claim_graph.{claim_id}",
                "高风险声明未同时满足可信证据与确定性验证门", "high",
            ))
        if int(summary.get("rejected_claim_count", 0) or 0) > 0:
            issues.append(self._issue(
                layer, "validator_reject", "claim_graph.validation_results",
                f"有{summary.get('rejected_claim_count')}条声明被确定性验证器拒绝", "critical",
            ))
        for claim_id in summary.get("unsupported_medium_plus_claim_ids", []) or []:
            issues.append(self._issue(
                layer, "unsupported_claim", f"claim_graph.{claim_id}",
                "中高风险声明缺少完整证据链", "high",
            ))
        return issues

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        resources = context.generated_resources if isinstance(context.generated_resources, dict) else {}
        target_skill = self._target_skill(context)
        supplied_point = agent_input.get("knowledge_point")
        if supplied_point is None:
            knowledge_point, known_skill_ids = KnowledgePointValidator.from_domain(context.domain_id, target_skill)
        else:
            knowledge_point = supplied_point
            _, known_skill_ids = KnowledgePointValidator.from_domain(context.domain_id, target_skill)

        structure_issues, validator, analogy_found = self._review_structure(
            context, resources, knowledge_point, known_skill_ids
        )
        evidence_issues = self._review_evidence(resources, context.evidence_list)
        safety_issues = self._review_safe_execution(resources, context)
        proof_graph_issues = self._review_proof_graph(context)
        layers = [
            self._layer(1, "structure", structure_issues),
            self._layer(2, "evidence", evidence_issues),
            self._layer(3, "safe_execution", safety_issues),
        ]
        proof_graph_layer = self._layer(4, "proof_graph", proof_graph_issues)
        issues = structure_issues + evidence_issues + safety_issues + proof_graph_issues

        blocking = any(item.get("severity") in {"critical", "high"} for item in issues)
        if issues:
            decision = "revise" if context.revision_count < settings.max_revision_count else "reject"
        else:
            decision = "approve"

        total_issues = max(1, len(issues))
        scores = {
            "factuality": max(0.0, 1 - len(evidence_issues) / total_issues),
            "evidence_coverage": max(0.0, 1 - len(evidence_issues) / max(1, len(context.evidence_list))),
            "difficulty_match": 1.0 if not structure_issues else max(0.0, 1 - len(structure_issues) / total_issues),
            "actionability": 1.0 if not safety_issues else max(0.0, 1 - len(safety_issues) / total_issues),
            "traceability": 1.0 if not proof_graph_issues else max(0.0, 1 - len(proof_graph_issues) / total_issues),
        }
        return AgentResult(
            output={
                "decision": decision,
                "layers": layers,
                "proof_graph_layer": proof_graph_layer,
                "validator": validator,
                "knowledge_point": knowledge_point,
                "scores": scores,
                "issues": issues,
                "revision_instructions": [
                    {
                        "location": issue["location"],
                        "action": "modify",
                        "reason": issue["description"],
                        "severity": issue.get("severity", "medium"),
                    }
                    for issue in issues
                ],
            },
            confidence=0.95 if not issues else 0.84,
            next_action=decision,
            summary="审核通过（ProofGraph已接入）" if not issues else f"审核发现{len(issues)}个可定位问题",
        )
