"""Rule-based performance fitness check for a sizing recommendation.

Legacy parity: after sizing/guardrails, before risk assessment. No LLM.
"""

from __future__ import annotations

from typing import Any, Optional

from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import (
    normalize_resource_pressure_config,
    recommended_min_max_workers,
)

# Recommended capacity should stay at least this fraction of current (legacy ~80%).
CAPACITY_FLOOR_RATIO = 0.8
# When peak is above target×1.05, require recommended capacity ≥ 90% of current.
HIGH_PEAK_CAPACITY_RATIO = 0.9


def validate_performance(
    *,
    current_vcpus: int,
    current_max_workers: int,
    recommended_vcpus: int,
    recommended_max_workers: int,
    peak_cpu_pct: float = 0.0,
    peak_memory_pct: float = 0.0,
    job_run_ingest: Optional[dict[str, Any]] = None,
    resource_pressure_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return whether the recommendation is likely to meet peak load.

    Checks (legacy-aligned):
    - recommended capacity (vCPU × max_workers) ≥ ~80% of current capacity
    - recommended max_workers ≥ sizing floor from ingest (when ingest present)
    - if peak CPU/mem is above the configured target, avoid cutting below ~90%
      of current capacity
    """
    policy = normalize_resource_pressure_config(resource_pressure_config)
    peak_target = float(policy["target_utilization_pct"])
    buffer_pct = float(policy["capacity_buffer_pct"])

    current_capacity = max(int(current_vcpus) * int(current_max_workers), 1)
    recommended_capacity = max(int(recommended_vcpus) * int(recommended_max_workers), 1)

    meets = recommended_capacity >= (current_capacity * CAPACITY_FLOOR_RATIO)
    reasons: list[str] = []

    if not meets:
        reasons.append("recommended_capacity_below_80pct_of_current")

    ingest = job_run_ingest or {}
    if ingest:
        _, floor_max = recommended_min_max_workers(ingest, buffer_pct=buffer_pct)
        if int(recommended_max_workers) < int(floor_max):
            meets = False
            reasons.append("recommended_max_workers_below_sizing_floor")

        peak_cpu = float(
            ingest.get("peak_worker_cpu_utilization_pct")
            or ingest.get("peak_cpu_utilization_pct")
            or peak_cpu_pct
            or 0
        )
        peak_mem = float(
            ingest.get("peak_worker_memory_utilization_pct")
            or ingest.get("peak_memory_utilization_pct")
            or peak_memory_pct
            or 0
        )
    else:
        peak_cpu = float(peak_cpu_pct or 0)
        peak_mem = float(peak_memory_pct or 0)

    high_peak = peak_cpu > peak_target * 1.05 or peak_mem > peak_target * 1.05
    if high_peak and recommended_capacity < current_capacity * HIGH_PEAK_CAPACITY_RATIO:
        meets = False
        reasons.append("high_peak_util_with_aggressive_capacity_cut")

    reduction_pct = (
        ((current_capacity - recommended_capacity) / current_capacity) * 100.0
        if current_capacity > 0
        else 0.0
    )
    # Reduction-based severity (legacy thresholds).
    if reduction_pct > 20:
        reduction_risk = "high"
    elif reduction_pct > 10:
        reduction_risk = "medium"
    else:
        reduction_risk = "low"

    return {
        "meets_peak_requirements": meets,
        "current_capacity_vcpu": current_capacity,
        "recommended_capacity_vcpu": recommended_capacity,
        "reduction_pct": round(reduction_pct, 1),
        "reduction_risk_level": reduction_risk,
        "estimated_impact": "maintained" if meets else "degradation_risk",
        "peak_cpu_pct": peak_cpu,
        "peak_memory_pct": peak_mem,
        "reasons": reasons,
    }
