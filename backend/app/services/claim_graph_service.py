"""Build and validate a risk-adaptive claim/evidence/validator graph."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.services.validation_service import ValidationService
from app.workflow.state import WorkflowState


_HIGH_RISK_COMMAND = re.compile(
    r"\b(?:sudo|rm\s+-rf|mkfs|dd\s+if=|fdisk|parted|shutdown|reboot|poweroff|"
    r"iptables|ufw|nmcli|flash|firmware)\b|/dev/(?:sd|nvme|mmcblk|tty)", re.I,
)


def _claim_id(path: str, text: str) -> str:
    digest = hashlib.sha256(f"{path}\n{text}".encode("utf-8")).hexdigest()[:12]
    return f"claim_{digest}"


def _risk_value(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(str(value).lower(), 0)


def _max_risk(a: str, b: str) -> str:
    return a if _risk_value(a) >= _risk_value(b) else b


class ClaimGraphService:
    def __init__(self, domain_id: str):
        self.domain_id = domain_id
        self.validator = ValidationService(domain_id)

    @staticmethod
    def _evidence_map(context: WorkflowState) -> dict[str, dict]:
        return {
            str(item.get("evidence_id")): item
            for item in context.evidence_list
            if item.get("evidence_id")
        }

    def _make_claim(
        self,
        *,
        path: str,
        text: str,
        risk_level: str,
        evidence_ids: list[str] | None = None,
        validator_ids: list[str] | None = None,
        **extra: Any,
    ) -> dict:
        text = str(text or "").strip()
        risk = str(risk_level or "low").lower()
        command = str(extra.get("command", ""))
        if command and _HIGH_RISK_COMMAND.search(command):
            risk = _max_risk(risk, "high")
        return {
            "claim_id": _claim_id(path, text or command),
            "path": path,
            "text": text,
            "risk_level": risk,
            "evidence_ids": [str(item) for item in (evidence_ids or []) if item],
            "validator_ids": [str(item) for item in (validator_ids or []) if item],
            **extra,
        }

    def build(self, context: WorkflowState) -> dict:
        resources = context.generated_resources or {}
        claims: list[dict] = []

        lecture = resources.get("lecture") if isinstance(resources.get("lecture"), dict) else {}
        for index, section in enumerate(lecture.get("sections", []) or []):
            if not isinstance(section, dict):
                continue
            claims.append(self._make_claim(
                path=f"lecture.sections.{index}",
                text=section.get("content", ""),
                risk_level="low",
                evidence_ids=section.get("citations", []),
            ))

        guide = resources.get("practice_guide") if isinstance(resources.get("practice_guide"), dict) else {}
        guide_risk = str(guide.get("risk_level", "low"))
        guide_evidence = guide.get("evidence_ids", []) or []
        guide_validators = guide.get("validator_ids", []) or []
        for index, step in enumerate(guide.get("steps", []) or []):
            if not isinstance(step, dict):
                continue
            evidence_ids = step.get("evidence_ids", []) or guide_evidence
            validator_ids = step.get("validator_ids", []) or guide_validators
            command = str(step.get("command", ""))
            # Every executable command gets at least the safety validator.
            if command and "val_command_safety" not in validator_ids:
                validator_ids = [*validator_ids, "val_command_safety"]
            claims.append(self._make_claim(
                path=f"practice_guide.steps.{index}",
                text=f"{step.get('title', '')}: {step.get('expected_result', '')}",
                risk_level=step.get("risk_level", guide_risk),
                evidence_ids=evidence_ids,
                validator_ids=validator_ids,
                command=command,
                code=step.get("code", ""),
                ros_version=step.get("ros_version", ""),
            ))

        graded = resources.get("graded_test") if isinstance(resources.get("graded_test"), dict) else {}
        for index, item in enumerate(graded.get("items", []) or []):
            if not isinstance(item, dict):
                continue
            evidence_ids = item.get("evidence_ids", []) or []
            # A test explanation is a low-risk factual claim; if no explicit citation
            # exists, it remains visible as unsupported rather than being hidden.
            claims.append(self._make_claim(
                path=f"graded_test.items.{index}.explanation",
                text=item.get("explanation", ""),
                risk_level="low",
                evidence_ids=evidence_ids,
            ))

        evidence_map = self._evidence_map(context)
        edges: list[dict] = []
        validation_results: list[dict] = []
        unresolved_high_risk: list[str] = []
        unsupported_high_confidence: list[str] = []

        for claim in claims:
            for evidence_id in claim["evidence_ids"]:
                edges.append({"from": evidence_id, "to": claim["claim_id"], "type": "supports"})
            evidence_ok = bool(claim["evidence_ids"]) and all(
                evidence_id in evidence_map
                and str(evidence_map[evidence_id].get("verification_status", "pending")) in {"verified", "trusted_source"}
                for evidence_id in claim["evidence_ids"]
            )
            claim["evidence_status"] = "supported" if evidence_ok else "unsupported"

            results: list[dict] = []
            for validator_id in claim["validator_ids"]:
                result = self.validator.validate(
                    validator_id,
                    claim,
                    version_filter=context.version_filter,
                ).to_dict()
                result["claim_id"] = claim["claim_id"]
                results.append(result)
                validation_results.append(result)
                edges.append({"from": validator_id, "to": claim["claim_id"], "type": "validates"})
            claim["validation_results"] = results

            statuses = {item["status"] for item in results}
            if "fail" in statuses:
                disposition = "REJECT"
            elif "needs_confirmation" in statuses:
                disposition = "NEED_CONFIRMATION"
            elif claim["risk_level"] in {"high", "critical"} and (
                not evidence_ok or not results or "unknown" in statuses
            ):
                disposition = "NEED_CONFIRMATION"
            elif not evidence_ok:
                disposition = "DOWNGRADE"
            else:
                disposition = "PASS"
            claim["final_disposition"] = disposition

            if claim["risk_level"] in {"high", "critical"} and disposition != "PASS":
                unresolved_high_risk.append(claim["claim_id"])
            if not evidence_ok and claim["risk_level"] in {"medium", "high", "critical"}:
                unsupported_high_confidence.append(claim["claim_id"])

        summary = {
            "claim_count": len(claims),
            "high_risk_claim_count": sum(1 for c in claims if c["risk_level"] in {"high", "critical"}),
            "supported_claim_count": sum(1 for c in claims if c["evidence_status"] == "supported"),
            "validated_claim_count": sum(1 for c in claims if c["validation_results"]),
            "rejected_claim_count": sum(1 for c in claims if c["final_disposition"] == "REJECT"),
            "needs_confirmation_count": sum(1 for c in claims if c["final_disposition"] == "NEED_CONFIRMATION"),
            "unresolved_high_risk_claim_ids": unresolved_high_risk,
            "unsupported_medium_plus_claim_ids": unsupported_high_confidence,
        }
        summary["high_risk_traceability"] = (
            1.0 if summary["high_risk_claim_count"] == 0 else
            (summary["high_risk_claim_count"] - len(unresolved_high_risk)) / summary["high_risk_claim_count"]
        )
        return {
            "claims": claims,
            "edges": edges,
            "validation_results": validation_results,
            "summary": summary,
        }
