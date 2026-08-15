"""Validate the public knowledge-point JSON contract.

The public contract intentionally uses ``dificulty`` because that is the field
name consumed by the current interface. Internal skill packages may still use
the correctly-spelled legacy field ``difficulty``; ``from_domain`` performs the
compatibility mapping before validation.
"""

from __future__ import annotations

from typing import Any

from app.services.domain_package_service import load_skill_edges, load_skill_nodes


class KnowledgePointValidator:
    """Strict, side-effect-free validator for one knowledge-point object."""

    required_fields = (
        "id",
        "name",
        "module",
        "description",
        "dificulty",
        "estimated_minutes",
        "objectives",
        "criteria",
        "prerequisite_ids",
        "key_points",
        "tags",
    )
    string_fields = ("id", "name", "module", "description")
    list_fields = ("objectives", "criteria", "prerequisite_ids", "key_points", "tags")

    @classmethod
    def from_domain(cls, domain_id: str, skill_id: str) -> tuple[dict[str, Any], set[str]]:
        """Build the public contract from a domain package's canonical skill node."""
        nodes = load_skill_nodes(domain_id)
        node_map = {str(item.get("id", "")): item for item in nodes}
        if skill_id not in node_map:
            return {}, set(node_map)

        node = node_map[skill_id]
        prerequisites = [
            str(edge.get("from_skill_id") or edge.get("from") or "")
            for edge in load_skill_edges(domain_id)
            if (edge.get("relation_type") or edge.get("relation")) == "prerequisite"
            and str(edge.get("to_skill_id") or edge.get("to") or "") == skill_id
        ]
        objectives = list(node.get("objectives") or [])
        criteria = list(node.get("criteria") or [])
        point = {
            "id": skill_id,
            "name": node.get("name", ""),
            "module": node.get("module") or domain_id,
            "description": node.get("description") or "；".join(str(item) for item in objectives),
            "dificulty": node.get("dificulty", node.get("difficulty")),
            "estimated_minutes": node.get("estimated_minutes"),
            "objectives": objectives,
            "criteria": criteria,
            "prerequisite_ids": list(node.get("prerequisite_ids") or prerequisites),
            "key_points": list(node.get("key_points") or objectives),
            "tags": list(node.get("tags") or [domain_id, skill_id]),
        }
        return point, set(node_map)

    @classmethod
    def validate(cls, payload: Any, *, known_ids: set[str] | None = None) -> dict[str, Any]:
        issues: list[dict[str, str]] = []

        def add(field: str, description: str) -> None:
            issues.append({
                "type": "knowledge_point_schema",
                "location": f"knowledge_point.{field}" if field else "knowledge_point",
                "description": description,
            })

        if not isinstance(payload, dict):
            add("", "知识点必须是JSON对象")
            return cls._result(issues)

        for field in cls.required_fields:
            if field not in payload:
                add(field, f"知识点缺少必需字段{field}")

        for field in cls.string_fields:
            if field in payload and (not isinstance(payload[field], str) or not payload[field].strip()):
                add(field, f"{field}必须是非空字符串")

        difficulty = payload.get("dificulty")
        if "dificulty" in payload and (
            isinstance(difficulty, bool) or not isinstance(difficulty, int) or not 1 <= difficulty <= 5
        ):
            add("dificulty", "dificulty必须是1到5之间的整数")

        minutes = payload.get("estimated_minutes")
        if "estimated_minutes" in payload and (
            isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0
        ):
            add("estimated_minutes", "estimated_minutes必须是正整数")

        for field in cls.list_fields:
            if field not in payload:
                continue
            value = payload[field]
            if not isinstance(value, list):
                add(field, f"{field}必须是字符串数组")
                continue
            if field != "prerequisite_ids" and not value:
                add(field, f"{field}不能为空")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                add(field, f"{field}只能包含非空字符串")
            if len(value) != len(set(item for item in value if isinstance(item, str))):
                add(field, f"{field}不能包含重复值")

        point_id = payload.get("id")
        prerequisite_ids = payload.get("prerequisite_ids")
        if isinstance(prerequisite_ids, list):
            if point_id in prerequisite_ids:
                add("prerequisite_ids", "知识点不能依赖自身")
            if known_ids is not None:
                unknown = sorted({item for item in prerequisite_ids if isinstance(item, str)} - known_ids)
                if unknown:
                    add("prerequisite_ids", f"存在未知前置知识点：{'、'.join(unknown)}")

        return cls._result(issues)

    @classmethod
    def _result(cls, issues: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "name": "knowledge_point_json_validator",
            "valid": not issues,
            "schema_fields": list(cls.required_fields),
            "issues": issues,
        }
