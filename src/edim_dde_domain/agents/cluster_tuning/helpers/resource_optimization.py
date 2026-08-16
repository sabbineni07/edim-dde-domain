"""Peak provisioned capacity comparison for cluster tuning (no dollar pricing).

Business purpose
----------------
After sizing settles, the recommendation assembler needs a simple, deterministic
view of how much peak capacity (vCPU × max workers) moves between current and
recommended configurations. This module never invents cost/dollar figures —
optimization percent is capacity-only.

Fits the pipeline after ``parse_sizing`` / ``assess_risks`` via
``logic.generate_recommendation``.

Public API
----------
* ``estimate_resource_optimization`` — capacity delta used in API comparison
"""

from __future__ import annotations

from typing import Any


def estimate_resource_optimization(
    *,
    current_vcpus: int,
    current_max_workers: int,
    recommended_vcpus: int,
    recommended_max_workers: int,
) -> dict[str, Any]:
    """Compare peak provisioned capacity (vCPU × max workers).

    ``resource_optimization_pct`` is the percent of capacity *released*
    relative to current: positive when recommended capacity is smaller,
    negative when upsizing.

    Args:
        current_vcpus: Parsed vCPUs of the current worker SKU.
        current_max_workers: Current max worker nodes provisioned.
        recommended_vcpus: Recommended worker SKU vCPUs.
        recommended_max_workers: Recommended max workers.

    Returns:
        Dict with ``current_capacity_vcpu``, ``recommended_capacity_vcpu``, and
        ``resource_optimization_pct`` (rounded to 1 decimal).

    Example:
        8 vCPU × 16 workers → 4 vCPU × 8 workers yields ~75% optimization.
    """
    cur_cap = max(int(current_vcpus) * max(int(current_max_workers), 0), 1)
    rec_cap = max(int(recommended_vcpus) * max(int(recommended_max_workers), 0), 1)
    optimization_pct = (cur_cap - rec_cap) / cur_cap * 100.0
    return {
        "current_capacity_vcpu": cur_cap,
        "recommended_capacity_vcpu": rec_cap,
        "resource_optimization_pct": round(optimization_pct, 1),
    }
