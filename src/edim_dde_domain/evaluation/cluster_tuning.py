"""Deterministic cluster-tuning quality rubric and golden-case support."""

from __future__ import annotations

import re
from typing import Any

from edim_dde_ai.evaluation import EvaluationResult, register_evaluator
from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import (
    compute_resource_pressure,
    parse_family_from_node_type,
)

_REQUIRED_PATTERN_HEADINGS = (
    "workload type",
    "resource utilization",
    "performance characteristics",
    "optimization opportunities",
    "historical evidence",
)
_CRITICAL_METRICS = (
    "azure_worker_vm_size",
    "max_worker_nodes_provisioned",
    "peak_worker_cpu_utilization_pct",
    "peak_worker_memory_utilization_pct",
)


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _recommendation(output: dict[str, Any]) -> dict[str, Any]:
    rec = output.get("recommendation")
    return rec if isinstance(rec, dict) else output


def _family_from_sku(sku: str) -> str:
    return parse_family_from_node_type(sku)


class ClusterTuningQualityEvaluator:
    """Score legality, evidence grounding, direction, history use, and safety."""

    def __init__(
        self, resource_pressure_config: dict[str, Any] | None = None
    ) -> None:
        self._resource_pressure_config = dict(resource_pressure_config or {})

    @property
    def name(self) -> str:
        return "cluster_tuning.quality"

    def evaluate(
        self,
        *,
        inputs: dict[str, Any],
        output: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        metrics = inputs.get("metrics") or inputs.get("job_run_ingest") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        rec = _recommendation(output)
        pattern = str(
            output.get("pattern_analysis")
            or rec.get("pattern_analysis")
            or ""
        )
        rationale = str(rec.get("rationale") or output.get("rationale") or "")
        history = str((context or {}).get("historical_context") or "None")
        findings: list[str] = []

        dimensions: dict[str, float] = {}

        # 1. Contract / legality (25%)
        family = str(rec.get("node_family") or "")
        vcpus = _number(rec.get("vcpus"))
        min_w = _number(rec.get("recommended_min_workers", rec.get("min_workers")))
        max_w = _number(rec.get("recommended_max_workers", rec.get("max_workers")))
        auto = _number(rec.get("auto_termination_minutes"))
        legal_checks = [
            family in {"D", "E", "F", "L"},
            vcpus is not None and 4 <= vcpus <= 64,
            min_w is not None and max_w is not None and 0 <= min_w <= max_w,
            auto == 0,
        ]
        dimensions["contract"] = sum(legal_checks) / len(legal_checks)
        if not all(legal_checks):
            findings.append("Output contract/guardrail fields are incomplete or illegal")

        # 2. Evidence grounding (20%)
        evidence_text = f"{pattern}\n{rationale}".lower()
        available_numbers = [
            str(v).lower()
            for key in _CRITICAL_METRICS[1:]
            if (v := metrics.get(key)) is not None
        ]
        metric_citations = sum(n in evidence_text for n in available_numbers)
        citation_score = (
            metric_citations / len(available_numbers) if available_numbers else 0.0
        )
        heading_score = sum(
            heading in pattern.lower() for heading in _REQUIRED_PATTERN_HEADINGS
        ) / len(_REQUIRED_PATTERN_HEADINGS)
        dimensions["evidence"] = 0.6 * citation_score + 0.4 * heading_score
        if citation_score < 0.5:
            findings.append("Rationale/pattern_analysis cites too few live metrics")
        if heading_score < 1:
            findings.append("pattern_analysis is missing required headings")

        # 3. Directional correctness (25%)
        current_max = _number(metrics.get("max_worker_nodes_provisioned"))
        current_family = _family_from_sku(
            str(metrics.get("azure_worker_vm_size") or "")
        )
        pressure_config = (context or {}).get(
            "resource_pressure_config", self._resource_pressure_config
        )
        persisted_pressure = rec.get("resource_pressure")
        pressure = (
            persisted_pressure
            if isinstance(persisted_pressure, dict)
            and persisted_pressure.get("dimensions")
            else compute_resource_pressure(
                metrics,
                config=pressure_config if isinstance(pressure_config, dict) else None,
            )
        )
        direction_checks: list[bool] = []
        if max_w is not None and current_max is not None:
            capacity = next(
                (
                    details
                    for details in (pressure.get("dimensions") or {}).values()
                    if isinstance(details, dict)
                    and details.get("role") == "capacity"
                ),
                {},
            )
            capacity_level = str(capacity.get("level") or "unknown")
            if capacity_level == "low":
                direction_checks.append(max_w <= current_max)
            elif capacity_level in {"high", "saturated"}:
                direction_checks.append(max_w >= current_max)

        limiting = str(pressure.get("limiting_resource") or "unknown")
        preferred = [str(f).upper() for f in pressure.get("preferred_families") or []]
        if family and current_family:
            if limiting in {"none", "unknown"}:
                # A family/shape move requires pressure evidence; low utilization
                # alone only supports capacity or tier changes.
                direction_checks.append(family == current_family)
            elif preferred and current_family not in preferred:
                direction_checks.append(family in preferred)
        dimensions["direction"] = (
            sum(direction_checks) / len(direction_checks)
            if direction_checks
            else 1.0
        )
        if dimensions["direction"] < 1:
            findings.append("Recommended direction conflicts with observed utilization")

        # 4. History handling (15%)
        has_history = history.strip() not in {
            "",
            "None",
            "(no runbook / knowledge hits retrieved)",
        }
        hist_text = pattern.lower()
        if has_history:
            history_terms = (
                "histor",
                "experience",
                "guidance",
                "occurrence",
                "prior",
            )
            dimensions["history"] = 1.0 if any(t in hist_text for t in history_terms) else 0.0
            if dimensions["history"] == 0:
                findings.append("Historical context was present but not addressed")
        else:
            dimensions["history"] = (
                1.0
                if "historical evidence" in hist_text
                and any(t in hist_text for t in ("none", "absent", "no relevant"))
                else 0.5
            )

        # 5. Safety / uncertainty discipline (15%)
        no_invented_dollars = "$" not in evidence_text and " usd" not in evidence_text
        claims_failure = bool(
            re.search(
                r"\boom\b|out[\s_-]?of[\s_-]?memory|job\s+fail(?:ed|ure)",
                evidence_text,
                re.I,
            )
        )
        failure_evidence = " ".join(
            str(metrics.get(key) or "")
            for key in ("failure_reason", "error_message", "error_logs")
        )
        has_failure_evidence = bool(
            re.search(
                r"\boom\b|out[\s_-]?of[\s_-]?memory|job\s+fail(?:ed|ure)",
                failure_evidence,
                re.I,
            )
        )
        no_unsupported_failure = not (claims_failure and not has_failure_evidence)
        dimensions["safety"] = (
            float(no_invented_dollars) + float(no_unsupported_failure)
        ) / 2
        if not no_invented_dollars:
            findings.append("Invented dollar-cost claim detected")
        if not no_unsupported_failure:
            findings.append("Failure claim lacks failure/error evidence")

        weights = {
            "contract": 0.25,
            "evidence": 0.20,
            "direction": 0.25,
            "history": 0.15,
            "safety": 0.15,
        }
        score = sum(dimensions[k] * weights[k] for k in weights)

        # Confidence is evidence completeness + deterministic rubric coverage,
        # never the model's own confidence claim.
        metric_completeness = sum(
            metrics.get(k) is not None for k in _CRITICAL_METRICS
        ) / len(_CRITICAL_METRICS)
        confidence = 0.7 * metric_completeness + 0.3 * (
            len(dimensions) / len(weights)
        )
        return EvaluationResult(
            evaluator=self.name,
            score=round(score, 4),
            confidence=round(confidence, 4),
            passed=score >= 0.75 and dimensions["contract"] == 1.0,
            dimensions={k: round(v, 4) for k, v in dimensions.items()},
            findings=findings,
            metadata={
                "threshold": 0.75,
                "confidence_definition": "input completeness + deterministic rubric coverage",
            },
        )


def register_cluster_tuning_evaluator(
    resource_pressure_config: dict[str, Any] | None = None,
) -> None:
    register_evaluator(ClusterTuningQualityEvaluator(resource_pressure_config))
