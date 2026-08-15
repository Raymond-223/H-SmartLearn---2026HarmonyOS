"""Deterministic risk router for the ProofGraph 1/2/4-call policy.

The router is intentionally cheap: it consumes state already produced by the
learner model and retriever, makes no model call, and returns an auditable score.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Iterable

from app.workflow.state import WorkflowState


_DANGEROUS = re.compile(
    r"\b(?:sudo|mkfs(?:\.|\s)|fdisk|parted|dd\s+if=|shutdown|reboot|poweroff|"
    r"flash|firmware|iptables|ufw\s+(?:disable|reset)|nmcli\s+con\s+(?:delete|modify))\b|"
    r"rm\s+-rf\s+/(?:\s|$)|/dev/(?:sd|nvme|mmcblk)",
    re.IGNORECASE,
)
_VERSION_OR_CONFIG = re.compile(
    r"\b(?:version|版本|humble|foxy|jazzy|iron|rolling|配置|parameter|参数|qos|dds|"
    r"launch|yaml|urdf|xacro|firmware|驱动|权限|udev)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RiskRoute:
    route: str
    pre_risk: float
    domain_risk: float
    uncertainty: float
    retrieval_weakness: float
    novelty: float
    model_call_budget: int
    requires_critic: bool
    requires_judge: bool
    force_strict: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class RiskRouterService:
    """Compute the pre-route specified by the project report.

    PreRisk = 0.35*DomainRisk + 0.25*Uncertainty
            + 0.25*RetrievalWeakness + 0.15*Novelty
    """

    FAST_MAX = 0.35
    STANDARD_MAX = 0.65

    @staticmethod
    def _text(context: WorkflowState) -> str:
        parts = [context.target_goal or "", context.source_skill_id or "", context.version_filter or ""]
        for item in context.evidence_list[:8]:
            parts.append(str(item.get("content", "")))
        return " ".join(parts)

    @staticmethod
    def _domain_risk(context: WorkflowState) -> tuple[float, bool, list[str]]:
        query = " ".join([context.target_goal or "", context.source_skill_id or ""])
        reasons: list[str] = []
        force_strict = bool(_DANGEROUS.search(query))
        if force_strict:
            reasons.append("请求包含危险/系统级操作关键词")
            return 1.0, True, reasons

        evidence_risks = [
            str(item.get("risk_level", "low")).lower() for item in context.evidence_list
        ]
        mapping = {"low": 0.15, "medium": 0.50, "high": 0.80, "critical": 1.0}
        evidence_risk = max((mapping.get(value, 0.3) for value in evidence_risks), default=0.15)
        query_risk = 0.55 if _VERSION_OR_CONFIG.search(query) else 0.20
        if query_risk >= 0.55:
            reasons.append("请求涉及版本/配置/机器人运行条件")
        return max(query_risk, evidence_risk), False, reasons

    @staticmethod
    def _uncertainty(context: WorkflowState) -> float:
        summary = context.mastery_summary or {}
        value = summary.get("overall_uncertainty")
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))

        confidences = [
            float(item.get("confidence", 0.0))
            for item in (context.mastery_state or {}).values()
            if isinstance(item, dict) and isinstance(item.get("confidence"), (int, float))
        ]
        if confidences:
            return max(0.0, min(1.0, 1.0 - sum(confidences) / len(confidences)))
        return 0.50

    @staticmethod
    def _retrieval_weakness(context: WorkflowState) -> tuple[float, list[str]]:
        if not context.evidence_list:
            return 1.0, ["检索无证据"]
        if context.retrieval_meta and context.retrieval_meta.get("version_filter_miss"):
            return 1.0, ["版本过滤后无可用证据"]

        head = context.evidence_list[:5]
        # RRF/MMR scores are not calibrated probabilities. Mix rank evidence,
        # source trust and verification coverage instead of treating one score as certainty.
        trust = sum(float(item.get("source_trust", 0.5)) for item in head) / max(1, len(head))
        verified = sum(
            1 for item in head
            if str(item.get("verification_status", "pending")) in {"verified", "trusted_source"}
        ) / max(1, len(head))
        coverage = min(1.0, len(head) / 5.0)
        strength = 0.45 * trust + 0.35 * verified + 0.20 * coverage
        weakness = max(0.0, min(1.0, 1.0 - strength))
        reasons = ["检索证据可信度/覆盖偏弱"] if weakness >= 0.45 else []
        return weakness, reasons

    @staticmethod
    def _novelty(context: WorkflowState) -> float:
        query = (context.target_goal or "").strip().lower()
        if not query:
            return 0.25
        query_terms = set(re.findall(r"[a-z0-9_./+-]+|[\u4e00-\u9fff]{2,}", query))
        if not query_terms:
            return 0.25
        evidence_text = " ".join(str(item.get("content", "")) for item in context.evidence_list[:8]).lower()
        covered = sum(1 for term in query_terms if term in evidence_text)
        return max(0.0, min(1.0, 1.0 - covered / len(query_terms)))

    def assess(self, context: WorkflowState) -> RiskRoute:
        domain_risk, force_strict, reasons = self._domain_risk(context)
        uncertainty = self._uncertainty(context)
        retrieval_weakness, retrieval_reasons = self._retrieval_weakness(context)
        novelty = self._novelty(context)
        reasons.extend(retrieval_reasons)

        pre_risk = (
            0.35 * domain_risk
            + 0.25 * uncertainty
            + 0.25 * retrieval_weakness
            + 0.15 * novelty
        )
        pre_risk = round(max(0.0, min(1.0, pre_risk)), 4)

        if force_strict or pre_risk >= self.STANDARD_MAX:
            route = "strict"
            budget = 4
            requires_critic = True
            requires_judge = True
        elif pre_risk >= self.FAST_MAX:
            route = "standard"
            budget = 2
            requires_critic = True
            requires_judge = False
        else:
            route = "fast"
            budget = 1
            requires_critic = False
            requires_judge = False

        if not reasons:
            reasons.append("风险、学情不确定性与检索弱度均处于可控范围")
        return RiskRoute(
            route=route,
            pre_risk=pre_risk,
            domain_risk=round(domain_risk, 4),
            uncertainty=round(uncertainty, 4),
            retrieval_weakness=round(retrieval_weakness, 4),
            novelty=round(novelty, 4),
            model_call_budget=budget,
            requires_critic=requires_critic,
            requires_judge=requires_judge,
            force_strict=force_strict,
            reasons=reasons,
        )
