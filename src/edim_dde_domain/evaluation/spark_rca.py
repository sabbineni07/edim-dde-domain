"""Deterministic quality rubric for Spark job-failure RCA."""

from __future__ import annotations

import re
from typing import Any

from edim_dde_ai.evaluation import EvaluationResult, register_evaluator
from edim_dde_domain.agents.spark_rca.helpers.classify import RCA_CATEGORIES

_GENERIC_ACTIONS = {
    "re-run with additional logging",
    "rerun with additional logging",
    "investigate",
    "check logs",
}


def _result(output: dict[str, Any]) -> dict[str, Any]:
    value = output.get("result")
    return value if isinstance(value, dict) else output


def _tokens(value: Any) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{3,}", str(value or ""))
    }


class SparkRcaQualityEvaluator:
    """Score contract, evidence, diagnosis, fixes, context use, and safety."""

    @property
    def name(self) -> str:
        return "spark_rca.quality"

    def evaluate(
        self,
        *,
        inputs: dict[str, Any],
        output: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        result = _result(output)
        pack = inputs.get("evidence_pack") or result.get("evidence_pack") or {}
        if not isinstance(pack, dict):
            pack = {}
        ctx = context or {}
        root = result.get("root_cause") or {}
        actions = [
            str(value).strip()
            for value in (result.get("recommended_actions") or [])
            if str(value).strip()
        ]
        analysis = result.get("evidence_analysis") or {}
        findings: list[str] = []
        dimensions: dict[str, float] = {}

        # Stable product contract.
        contract_checks = [
            str(root.get("category") or "") in RCA_CATEGORIES,
            bool(str(root.get("summary") or "").strip()),
            bool(str(root.get("failure_signature") or "").strip()),
            isinstance(actions, list) and bool(actions),
            0.0 <= float(root.get("confidence") or 0.0) <= 1.0,
        ]
        dimensions["contract"] = sum(contract_checks) / len(contract_checks)
        if dimensions["contract"] < 1:
            findings.append("RCA output contract is incomplete or invalid")

        # Evidence refs must resolve to the supplied pack; analysis must address
        # available channels without requiring channels that were not collected.
        allowed_refs = {
            str(item.get("ref"))
            for item in (pack.get("evidence") or [])
            if isinstance(item, dict) and item.get("ref")
        }
        used_refs = {
            str(item.get("ref"))
            for item in (result.get("evidence") or [])
            if isinstance(item, dict) and item.get("ref")
        }
        refs_valid = used_refs <= allowed_refs
        refs_present = bool(used_refs) if allowed_refs else True
        analysis_present = sum(
            bool(str(analysis.get(key) or "").strip())
            for key in (
                "log_signals",
                "metric_anomalies",
                "physical_plan_bottlenecks",
            )
        )
        dimensions["evidence"] = (
            float(refs_valid) + float(refs_present) + analysis_present / 3
        ) / 3
        if not refs_valid:
            findings.append("Output contains evidence refs absent from evidence_pack")
        if allowed_refs and not refs_present:
            findings.append("Available evidence was not cited")

        # Diagnosis should overlap observed failure signals or agree with a
        # high-confidence deterministic hint.
        evidence_text = " ".join(
            str(item.get("excerpt") or "")
            for item in (pack.get("evidence") or [])
            if isinstance(item, dict)
        )
        anchors = pack.get("raw_anchors") or {}
        evidence_text += " " + str(anchors)
        diagnosis_text = " ".join(
            [
                str(root.get("summary") or ""),
                str(root.get("failure_signature") or ""),
                str(analysis),
            ]
        )
        overlap = _tokens(evidence_text) & _tokens(diagnosis_text)
        hint = result.get("classification_hint") or {}
        hint_agrees = (
            float(hint.get("confidence") or 0.0) < 0.65
            or root.get("category") == hint.get("category")
        )
        dimensions["diagnosis"] = (
            float(bool(overlap)) + float(hint_agrees)
        ) / 2
        if not overlap and evidence_text.strip():
            findings.append("Diagnosis has weak lexical grounding in supplied evidence")
        if not hint_agrees:
            findings.append("Diagnosis conflicts with a high-confidence rule hint")

        # Fixes must be present and more useful than a generic fallback.
        specific_actions = [
            action
            for action in actions
            if action.lower().rstrip(".") not in _GENERIC_ACTIONS
            and len(action.split()) >= 4
        ]
        grouped = result.get("recommendations") or {}
        grouped_count = sum(
            len(value) for value in grouped.values() if isinstance(value, list)
        )
        dimensions["actions"] = (
            float(bool(actions))
            + float(bool(specific_actions))
            + float(grouped_count > 0 or len(specific_actions) >= 2)
        ) / 3
        if not specific_actions:
            findings.append("Recommended actions are missing or too generic")

        # Context is optional. When present, the structured context assessment
        # must explicitly say whether it corroborated, conflicted, or was unused.
        assessment = result.get("context_assessment") or {}
        context_values = [
            ctx.get("runbook_context") or result.get("runbook_context"),
            ctx.get("historical_context") or result.get("historical_context"),
            ctx.get("web_search_context") or result.get("web_search_context"),
        ]
        has_context = any(
            value
            and str(value).strip()
            not in {"None", "(no prior RCA history retrieved)"}
            and not str(value).startswith("(")
            for value in context_values
        )
        assessment_text = " ".join(str(value) for value in assessment.values()).lower()
        dimensions["context"] = (
            1.0
            if not has_context
            or any(
                term in assessment_text
                for term in ("corrobor", "conflict", "not used", "no relevant")
            )
            else 0.0
        )
        if has_context and dimensions["context"] == 0:
            findings.append("Retrieved context was not explicitly assessed")

        # Safety: web citations must come from supplied search hits, and web/history
        # cannot substitute for current-run evidence refs.
        supplied_urls = {
            str(hit.get("url"))
            for hit in (result.get("web_search_hits") or [])
            if isinstance(hit, dict) and hit.get("url")
        }
        cited_urls = {
            str(url)
            for url in (assessment.get("web_citations") or [])
            if str(url).strip()
        }
        citations_valid = cited_urls <= supplied_urls
        external_only_diagnosis = bool(cited_urls) and bool(allowed_refs) and not used_refs
        dimensions["safety"] = (
            float(citations_valid) + float(not external_only_diagnosis)
        ) / 2
        if not citations_valid:
            findings.append("Web citation was not returned by the web-search provider")
        if external_only_diagnosis:
            findings.append("External context replaced current-run evidence")

        weights = {
            "contract": 0.20,
            "evidence": 0.25,
            "diagnosis": 0.20,
            "actions": 0.15,
            "context": 0.10,
            "safety": 0.10,
        }
        score = sum(dimensions[key] * weights[key] for key in weights)

        sections = pack.get("sections") or {}
        evidence_components = [
            bool(pack.get("raw_anchors")),
            bool(pack.get("evidence")),
            bool((sections.get("logs") or {})),
            bool((sections.get("stage_metrics") or {})),
            bool((sections.get("sql_plans") or {})),
        ]
        evidence_completeness = sum(evidence_components) / len(evidence_components)
        rubric_coverage = len(dimensions) / len(weights)
        confidence = 0.7 * evidence_completeness + 0.3 * rubric_coverage

        return EvaluationResult(
            evaluator=self.name,
            score=round(score, 4),
            confidence=round(confidence, 4),
            passed=(
                score >= 0.75
                and dimensions["contract"] == 1.0
                and dimensions["evidence"] >= 0.75
                and dimensions["actions"] >= 0.66
                and dimensions["safety"] == 1.0
            ),
            dimensions={key: round(value, 4) for key, value in dimensions.items()},
            findings=findings,
            metadata={
                "threshold": 0.75,
                "confidence_definition": (
                    "evidence-pack completeness + deterministic rubric coverage"
                ),
                "model_confidence": root.get("confidence"),
            },
        )


def register_spark_rca_evaluator() -> None:
    register_evaluator(SparkRcaQualityEvaluator())
