"""Cluster tuning analysis steps (post-collect)."""

from __future__ import annotations

from typing import Any

from edim_dde_domain.agents.cluster_tuning.guardrails import (
    validate_and_clamp_with_adjustments,
)
from edim_dde_domain.agents.cluster_tuning.sizing_policy import (
    compute_sizing_hints,
    infer_reason_codes,
    parse_family_from_node_type,
    parse_vcpus_from_node_type,
    sizing_hints_for_llm,
)
from edim_dde_domain.llm.json_util import dumps, parse_json_object
from edim_dde_domain.tools.cluster_metrics import estimate_monthly_costs


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
    """Flatten metrics into string fields for the sizing human prompt."""
    metrics = state.get("metrics") or {}
    current_config = {
        "azure_worker_vm_size": metrics.get("azure_worker_vm_size"),
        "max_worker_nodes_provisioned": metrics.get("max_worker_nodes_provisioned"),
        "azure_driver_vm_size": metrics.get("azure_driver_vm_size"),
        "driver_node_count": metrics.get("driver_node_count"),
        "dbr_version": metrics.get("dbr_version"),
    }
    hints = compute_sizing_hints(metrics)
    return {
        "current_config": dumps(current_config),
        "job_run_ingest": dumps(metrics),
        "sizing_hints": dumps(sizing_hints_for_llm(hints)),
        "guardrail_feedback": "None",
        "historical_context": "None",
        "sizing_hints_full": hints,
    }


def parse_sizing(state: dict[str, Any]) -> dict[str, Any]:
    """Parse sizing LLM JSON, apply guardrails + SKU allow-list."""
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
    }


def assess_risks(state: dict[str, Any]) -> dict[str, Any]:
    """Capacity-change risk from current vs recommended vCPU × workers."""
    sizing = state.get("sizing") or {}
    metrics = state.get("metrics") or {}

    cur_type = str(sizing.get("current_node_type") or metrics.get("azure_worker_vm_size") or "")
    rec_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(cur_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(rec_type))
    cur_max = int(sizing.get("current_max_workers") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or 1)

    cur_cap = max(cur_vcpus * cur_max, 1)
    rec_cap = max(rec_vcpus * rec_max, 1)
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
        level = "high" if level != "high" else level
        mitigations.append(
            "Peak utilization is high while capacity decreases — validate against peak windows."
        )
    if not mitigations:
        mitigations.append("Validate on a non-prod run before applying broadly.")

    return {
        "risk_assessment": {
            "risk_level": level,
            "change_magnitude_pct": round(change_pct, 1),
            "current_capacity_vcpu": cur_cap,
            "recommended_capacity_vcpu": rec_cap,
            "mitigations": mitigations,
        }
    }


def generate_recommendation(state: dict[str, Any]) -> dict[str, Any]:
    sizing = state.get("sizing") or {}
    risk = state.get("risk_assessment") or {}
    metrics = state.get("metrics") or {}

    current_type = str(sizing.get("current_node_type") or "")
    recommended_type = str(sizing.get("recommended_node_type") or "")
    current_avg = float(
        metrics.get("avg_worker_nodes_consumed")
        or sizing.get("current_max_workers")
        or 1
    )
    # Use recommended max as conservative avg when downsizing; else avg of current
    rec_max = float(sizing.get("recommended_max_workers") or 1)
    recommended_avg = min(current_avg, rec_max) if rec_max < current_avg else current_avg

    costs = estimate_monthly_costs(
        current_node_type=current_type,
        recommended_node_type=recommended_type,
        current_avg_nodes=current_avg,
        recommended_avg_nodes=max(recommended_avg, float(sizing.get("min_workers") or 0) or 1),
    )

    change_required = (
        recommended_type != current_type
        or int(sizing.get("recommended_max_workers") or 0)
        != int(sizing.get("current_max_workers") or 0)
        or int(sizing.get("min_workers") or 0) != 0
    )
    reason_codes = infer_reason_codes(
        metrics, sizing, change_required=change_required
    )

    recommendation = {
        **sizing,
        **costs,
        "risk_level": risk.get("risk_level", "low"),
        "reason_codes": reason_codes,
    }
    comparison = {
        "current": {
            "azure_node_type": current_type,
            "max_workers": sizing.get("current_max_workers"),
            "min_workers": sizing.get("current_min_workers", 0),
        },
        "recommended": {
            "azure_node_type": recommended_type,
            "node_family": sizing.get("node_family"),
            "vcpus": sizing.get("vcpus"),
            "max_workers": sizing.get("recommended_max_workers"),
            "min_workers": sizing.get("recommended_min_workers"),
            "auto_termination_minutes": sizing.get("auto_termination_minutes"),
        },
        "cost": {
            "monthly_current_usd": costs.get("monthly_cost_current_usd"),
            "monthly_recommended_usd": costs.get("monthly_cost_recommended_usd"),
            "savings_usd": costs.get("savings_usd"),
            "savings_pct": costs.get("savings_pct"),
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
