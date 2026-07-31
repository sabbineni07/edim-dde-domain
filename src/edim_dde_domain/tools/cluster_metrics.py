"""Cluster resource-capacity helpers (no dollar pricing)."""

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
    negative when upsizing. No currency or SKU list prices.
    """
    cur_cap = max(int(current_vcpus) * max(int(current_max_workers), 0), 1)
    rec_cap = max(int(recommended_vcpus) * max(int(recommended_max_workers), 0), 1)
    optimization_pct = (cur_cap - rec_cap) / cur_cap * 100.0
    return {
        "current_capacity_vcpu": cur_cap,
        "recommended_capacity_vcpu": rec_cap,
        "resource_optimization_pct": round(optimization_pct, 1),
    }
