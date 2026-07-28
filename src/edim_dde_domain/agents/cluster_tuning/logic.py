"""Cluster tuning analysis steps (post-collect)."""

from __future__ import annotations

from typing import Any

from edim_dde_domain.llm.json_util import dumps, parse_json_object
from edim_dde_domain.tools.cluster_metrics import estimate_monthly_costs


def normalize_metrics(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure job_run_id and ids are set after sql.query / override / stub."""
    metrics = dict(state.get("metrics") or {})
    job_run_id = (
        state.get("job_run_id")
        or metrics.get("job_run_id")
        or "demo-run"
    )
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
    }
    peak_cpu = float(metrics.get("peak_worker_cpu_utilization_pct") or 0)
    peak_mem = float(metrics.get("peak_worker_memory_utilization_pct") or 0)
    util = max(peak_cpu, peak_mem)
    current_max = int(metrics.get("max_worker_nodes_provisioned") or 16)
    if util < 40:
        hint_max = max(2, current_max // 2)
    elif util > 80:
        hint_max = min(current_max + 4, 32)
    else:
        hint_max = current_max
    sizing_hints = {
        "recommended_max_workers": hint_max,
        "utilization_pct": util,
        "note": "Deterministic pre-check; ingest wins on conflict.",
    }
    return {
        "current_config": dumps(current_config),
        "job_run_ingest": dumps(metrics),
        "sizing_hints": dumps(sizing_hints),
        "guardrail_feedback": "None",
        "historical_context": "None",
    }


def parse_sizing(state: dict[str, Any]) -> dict[str, Any]:
    """Parse sizing LLM JSON into pattern_analysis + sizing dict."""
    raw = parse_json_object(state.get("sizing_raw"))
    metrics = state.get("metrics") or {}
    current_type = str(metrics.get("azure_worker_vm_size") or "Standard_E8s_v3")
    current_max = int(metrics.get("max_worker_nodes_provisioned") or 16)
    peak_cpu = float(metrics.get("peak_worker_cpu_utilization_pct") or 0)
    peak_mem = float(metrics.get("peak_worker_memory_utilization_pct") or 0)
    util = max(peak_cpu, peak_mem)

    node_type = str(raw.get("recommended_node_type") or current_type)
    try:
        rec_max = int(raw.get("recommended_max_workers") or current_max)
    except (TypeError, ValueError):
        rec_max = current_max
    pattern = str(raw.get("pattern_analysis") or raw.get("rationale") or "Sizing from LLM")

    return {
        "pattern_analysis": pattern,
        "sizing": {
            "current_node_type": current_type,
            "recommended_node_type": node_type,
            "current_max_workers": current_max,
            "recommended_max_workers": rec_max,
            "utilization_pct": util,
            "rationale": str(raw.get("rationale") or ""),
        },
    }


def assess_risks(state: dict[str, Any]) -> dict[str, Any]:
    sizing = state.get("sizing") or {}
    cur = int(sizing.get("current_max_workers") or 1)
    rec = int(sizing.get("recommended_max_workers") or 1)
    change_pct = abs(cur - rec) / max(cur, 1) * 100
    if change_pct >= 50:
        level = "high"
    elif change_pct >= 25:
        level = "medium"
    else:
        level = "low"
    return {
        "risk_assessment": {
            "risk_level": level,
            "change_magnitude_pct": round(change_pct, 1),
        }
    }


def generate_recommendation(state: dict[str, Any]) -> dict[str, Any]:
    sizing = state.get("sizing") or {}
    risk = state.get("risk_assessment") or {}
    costs = estimate_monthly_costs(
        current_max_workers=int(sizing.get("current_max_workers") or 1),
        recommended_max_workers=int(sizing.get("recommended_max_workers") or 1),
        recommended_node_type=str(sizing.get("recommended_node_type") or ""),
    )
    recommendation = {
        **sizing,
        **costs,
        "risk_level": risk.get("risk_level", "low"),
    }
    return {"recommendation": recommendation}


def prepare_explanation_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Stringify fields for the explanation human prompt (non-colliding keys)."""
    return {
        "recommendation_text": dumps(state.get("recommendation") or {}),
        "job_run_ingest": dumps(state.get("metrics") or {}),
        "pattern_analysis": str(state.get("pattern_analysis") or ""),
        "risk_assessment_text": dumps(state.get("risk_assessment") or {}),
    }
