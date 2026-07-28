"""Cluster tuning analysis steps (post-collect)."""

from __future__ import annotations

from typing import Any

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


def run_sizing(state: dict[str, Any]) -> dict[str, Any]:
    """Heuristic right-size from utilization (stub for an LLM sizing chain)."""
    m = state.get("metrics") or {}
    peak_cpu = float(m.get("peak_worker_cpu_utilization_pct") or 0)
    peak_mem = float(m.get("peak_worker_memory_utilization_pct") or 0)
    current_max = int(m.get("max_worker_nodes_provisioned") or 16)
    current_type = str(m.get("azure_worker_vm_size") or "Standard_E8s_v3")

    util = max(peak_cpu, peak_mem)
    if util < 40:
        rec_max = max(2, current_max // 2)
        node_type = "Standard_E4s_v3"
        pattern = "Low utilization — recommend smaller SKU and fewer max workers"
    elif util > 80:
        rec_max = min(current_max + 4, 32)
        node_type = current_type
        pattern = "High utilization — keep SKU, raise max workers"
    else:
        rec_max = current_max
        node_type = current_type
        pattern = "Utilization in band — keep current sizing"

    return {
        "pattern_analysis": pattern,
        "sizing": {
            "current_node_type": current_type,
            "recommended_node_type": node_type,
            "current_max_workers": current_max,
            "recommended_max_workers": rec_max,
            "utilization_pct": util,
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


def generate_explanation(state: dict[str, Any]) -> dict[str, Any]:
    rec = state.get("recommendation") or {}
    pattern = state.get("pattern_analysis") or ""
    explanation = (
        f"{pattern}. Recommend {rec.get('recommended_node_type')} with "
        f"max_workers={rec.get('recommended_max_workers')} "
        f"(est. savings ${rec.get('savings_usd')}/mo, risk={rec.get('risk_level')})."
    )
    return {"explanation": explanation}
