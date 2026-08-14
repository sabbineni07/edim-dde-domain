"""Cluster tuning analysis steps (post-collect)."""

from __future__ import annotations

from typing import Any

from edim_dde_domain.agents.cluster_tuning.helpers.guardrails import (
    format_guardrail_feedback,
    should_retry_sizing,
    validate_and_clamp_with_adjustments,
)
from edim_dde_domain.agents.cluster_tuning.helpers.resource_optimization import (
    estimate_resource_optimization,
)
from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import (
    compute_sizing_hints,
    infer_reason_codes,
    parse_family_from_node_type,
    parse_vcpus_from_node_type,
    sizing_hints_for_llm,
)
from edim_dde_domain.agents.cluster_tuning.helpers.validate_performance import (
    validate_performance as _validate_performance,
)
from edim_dde_domain.llm.json_util import dumps, parse_json_object


def normalize_metrics(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure job_run_id and ids are set after sql.query / metrics override."""
    metrics = dict(state.get("metrics") or {})
    job_run_id = state.get("job_run_id") or metrics.get("job_run_id") or "unknown-run"
    return {
        "job_id": state.get("job_id") or metrics.get("job_id"),
        "cluster_id": state.get("cluster_id") or metrics.get("cluster_id"),
        "job_run_id": job_run_id,
        "metrics": metrics,
    }


def prepare_sizing_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Flatten metrics into string fields for the sizing human prompt.

    On guardrail retry, preserves ``guardrail_feedback`` set by ``parse_sizing``.
    """
    metrics = state.get("metrics") or {}
    current_config = {
        "azure_worker_vm_size": metrics.get("azure_worker_vm_size"),
        "max_worker_nodes_provisioned": metrics.get("max_worker_nodes_provisioned"),
        "azure_driver_vm_size": metrics.get("azure_driver_vm_size"),
        "driver_node_count": metrics.get("driver_node_count"),
        "dbr_version": metrics.get("dbr_version"),
    }
    hints = compute_sizing_hints(metrics)
    feedback = state.get("guardrail_feedback")
    if not feedback or str(feedback).strip() in ("", "None"):
        feedback = "None"
    return {
        "current_config": dumps(current_config),
        "job_run_ingest": dumps(metrics),
        "sizing_hints": dumps(sizing_hints_for_llm(hints)),
        "guardrail_feedback": feedback,
        "historical_context": "None",
        "sizing_hints_full": hints,
    }


def parse_sizing(state: dict[str, Any]) -> dict[str, Any]:
    """Parse sizing LLM JSON, apply guardrails + SKU allow-list.

    When retryable clamps remain and attempts < max, sets ``sizing_needs_retry``
    and ``guardrail_feedback`` so the graph can re-run sizing.
    """
    raw = parse_json_object(state.get("sizing_raw"))
    metrics = state.get("metrics") or {}
    current_type = str(metrics.get("azure_worker_vm_size") or "Standard_E8s_v3")
    current_max = int(metrics.get("max_worker_nodes_provisioned") or 16)

    # Accept both original schema and legacy simplified keys
    if "node_family" not in raw and raw.get("recommended_node_type"):
        raw = {
            **raw,
            "node_family": parse_family_from_node_type(str(raw["recommended_node_type"])),
            "vcpus": parse_vcpus_from_node_type(str(raw["recommended_node_type"])),
            "min_workers": int(raw.get("min_workers") or 0),
            "max_workers": int(
                raw.get("max_workers") or raw.get("recommended_max_workers") or current_max
            ),
            "auto_termination_minutes": int(raw.get("auto_termination_minutes") or 0),
        }

    applied, adjustments = validate_and_clamp_with_adjustments(
        raw, job_run_ingest=metrics
    )
    pattern = str(raw.get("pattern_analysis") or applied.get("rationale") or "Sizing from LLM")

    attempts = int(state.get("sizing_attempts") or 0) + 1
    needs_retry = should_retry_sizing(adjustments, sizing_attempts=attempts)
    feedback = format_guardrail_feedback(adjustments) if needs_retry else "None"

    sizing = {
        "current_node_type": current_type,
        "current_max_workers": current_max,
        "current_min_workers": 0,
        "node_family": applied["node_family"],
        "vcpus": applied["vcpus"],
        "min_workers": applied["min_workers"],
        "max_workers": applied["max_workers"],
        "recommended_node_type": applied["azure_node_type"],
        "recommended_max_workers": applied["max_workers"],
        "recommended_min_workers": applied["min_workers"],
        "auto_termination_minutes": applied["auto_termination_minutes"],
        "rationale": applied.get("rationale") or "",
        "azure_node_type": applied["azure_node_type"],
    }
    return {
        "pattern_analysis": pattern,
        "sizing": sizing,
        "guardrail_adjustments": adjustments,
        "llm_recommendation": raw,
        "sizing_attempts": attempts,
        "guardrail_retries": max(0, attempts - 1),
        "sizing_needs_retry": needs_retry,
        "guardrail_feedback": feedback,
    }


def validate_performance(state: dict[str, Any]) -> dict[str, Any]:
    """Rule-based peak-load fitness check (no LLM). Runs after sizing settles."""
    sizing = state.get("sizing") or {}
    metrics = state.get("metrics") or {}

    cur_type = str(sizing.get("current_node_type") or metrics.get("azure_worker_vm_size") or "")
    rec_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(cur_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(rec_type))
    cur_max = int(sizing.get("current_max_workers") or metrics.get("max_worker_nodes_provisioned") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or sizing.get("max_workers") or 1)

    return {
        "performance_validation": _validate_performance(
            current_vcpus=cur_vcpus,
            current_max_workers=cur_max,
            recommended_vcpus=rec_vcpus,
            recommended_max_workers=rec_max,
            peak_cpu_pct=float(metrics.get("peak_worker_cpu_utilization_pct") or 0),
            peak_memory_pct=float(metrics.get("peak_worker_memory_utilization_pct") or 0),
            job_run_ingest=metrics,
        )
    }


def assess_risks(state: dict[str, Any]) -> dict[str, Any]:
    """Capacity-change risk from current vs recommended vCPU × workers.

    Incorporates ``performance_validation`` when present (legacy fold-in).
    """
    sizing = state.get("sizing") or {}
    metrics = state.get("metrics") or {}
    perf = state.get("performance_validation") or {}

    cur_type = str(sizing.get("current_node_type") or metrics.get("azure_worker_vm_size") or "")
    rec_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(cur_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(rec_type))
    cur_max = int(sizing.get("current_max_workers") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or 1)

    cur_cap = int(perf.get("current_capacity_vcpu") or max(cur_vcpus * cur_max, 1))
    rec_cap = int(perf.get("recommended_capacity_vcpu") or max(rec_vcpus * rec_max, 1))
    change_pct = abs(cur_cap - rec_cap) / cur_cap * 100.0

    peak_cpu = float(metrics.get("peak_worker_cpu_utilization_pct") or 0)
    peak_mem = float(metrics.get("peak_worker_memory_utilization_pct") or 0)
    peak_util = max(peak_cpu, peak_mem)

    mitigations: list[str] = []
    if change_pct >= 50:
        level = "high"
        mitigations.append("Roll out on a canary job first; monitor run duration and OOMs.")
    elif change_pct >= 25:
        level = "medium"
        mitigations.append("Compare next run duration and spill metrics against baseline.")
    else:
        level = "low"

    if peak_util > 85 and rec_cap < cur_cap:
        level = "high"
        mitigations.append(
            "Peak utilization is high while capacity decreases — validate against peak windows."
        )

    if perf and not perf.get("meets_peak_requirements", True):
        if level == "low":
            level = "medium"
        elif level == "medium":
            level = "high"
        mitigations.append(
            "Performance validation flagged degradation risk "
            f"({', '.join(perf.get('reasons') or ['capacity_check_failed'])})."
        )

    reduction_risk = str(perf.get("reduction_risk_level") or "")
    if reduction_risk == "high" and level != "high":
        level = "high" if level == "medium" else "medium"
        mitigations.append(
            "Aggressive capacity reduction — monitor first runs and keep rollback ready."
        )

    if not mitigations:
        mitigations.append("Validate on a non-prod run before applying broadly.")

    # Dedupe while preserving order
    seen: set[str] = set()
    unique_mitigations: list[str] = []
    for m in mitigations:
        if m not in seen:
            seen.add(m)
            unique_mitigations.append(m)

    return {
        "risk_assessment": {
            "risk_level": level,
            "change_magnitude_pct": round(change_pct, 1),
            "current_capacity_vcpu": cur_cap,
            "recommended_capacity_vcpu": rec_cap,
            "mitigations": unique_mitigations,
            "meets_peak_requirements": bool(perf.get("meets_peak_requirements", True))
            if perf
            else None,
        }
    }


def generate_recommendation(state: dict[str, Any]) -> dict[str, Any]:
    sizing = state.get("sizing") or {}
    risk = state.get("risk_assessment") or {}
    metrics = state.get("metrics") or {}

    current_type = str(sizing.get("current_node_type") or "")
    recommended_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(current_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(recommended_type))
    cur_max = int(sizing.get("current_max_workers") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or 1)

    optimization = estimate_resource_optimization(
        current_vcpus=cur_vcpus,
        current_max_workers=cur_max,
        recommended_vcpus=rec_vcpus,
        recommended_max_workers=rec_max,
    )

    change_required = (
        recommended_type != current_type
        or rec_max != cur_max
        or int(sizing.get("min_workers") or 0) != 0
    )
    reason_codes = infer_reason_codes(
        metrics, sizing, change_required=change_required
    )
    perf = state.get("performance_validation") or {}
    if perf and not perf.get("meets_peak_requirements", True):
        if "PERFORMANCE_DEGRADATION_RISK" not in reason_codes:
            reason_codes.append("PERFORMANCE_DEGRADATION_RISK")

    recommendation = {
        **sizing,
        **optimization,
        "risk_level": risk.get("risk_level", "low"),
        "reason_codes": reason_codes,
        "meets_peak_requirements": perf.get("meets_peak_requirements"),
        "estimated_performance_impact": perf.get("estimated_impact"),
    }
    comparison = {
        "current": {
            "azure_node_type": current_type,
            "max_workers": sizing.get("current_max_workers"),
            "min_workers": sizing.get("current_min_workers", 0),
            "capacity_vcpu": optimization["current_capacity_vcpu"],
        },
        "recommended": {
            "azure_node_type": recommended_type,
            "node_family": sizing.get("node_family"),
            "vcpus": sizing.get("vcpus"),
            "max_workers": sizing.get("recommended_max_workers"),
            "min_workers": sizing.get("recommended_min_workers"),
            "auto_termination_minutes": sizing.get("auto_termination_minutes"),
            "capacity_vcpu": optimization["recommended_capacity_vcpu"],
        },
        "resource_optimization": {
            "optimization_pct": optimization["resource_optimization_pct"],
            "current_capacity_vcpu": optimization["current_capacity_vcpu"],
            "recommended_capacity_vcpu": optimization["recommended_capacity_vcpu"],
        },
    }
    return {
        "recommendation": recommendation,
        "comparison": comparison,
        "reason_codes": reason_codes,
        "current_configuration": comparison["current"],
    }


def prepare_explanation_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Stringify fields for the explanation human prompt (non-colliding keys)."""
    return {
        "recommendation_text": dumps(state.get("recommendation") or {}),
        "job_run_ingest": dumps(state.get("metrics") or {}),
        "pattern_analysis": str(state.get("pattern_analysis") or ""),
        "risk_assessment_text": dumps(state.get("risk_assessment") or {}),
    }
