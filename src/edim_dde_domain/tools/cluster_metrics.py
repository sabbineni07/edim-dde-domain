"""Cluster cost estimates from approximate Azure VM hourly rates."""

from __future__ import annotations

from typing import Any

# Approximate list prices (USD/hr) — replace with live SKU pricing later.
NODE_PRICING: dict[str, float] = {
    "Standard_D4s_v3": 0.192,
    "Standard_D4s_v5": 0.192,
    "Standard_D4ds_v5": 0.206,
    "Standard_D8s_v3": 0.384,
    "Standard_D8ds_v5": 0.412,
    "Standard_E4s_v3": 0.252,
    "Standard_E4s_v5": 0.252,
    "Standard_E4ds_v5": 0.272,
    "Standard_E8s_v3": 0.504,
    "Standard_E8s_v5": 0.504,
    "Standard_E8ds_v5": 0.544,
    "Standard_E16ds_v5": 1.088,
    "Standard_F4s_v2": 0.169,
    "Standard_F8s_v2": 0.338,
    "Standard_F16s_v2": 0.676,
}

DEFAULT_HOURLY = 0.25
HOURS_PER_MONTH = 730.0


def _hourly_rate(node_type: str) -> float:
    if node_type in NODE_PRICING:
        return NODE_PRICING[node_type]
    # Fuzzy family match
    for key, rate in NODE_PRICING.items():
        if node_type and key.split("_")[1][:2] == node_type.split("_")[1][:2]:
            return rate
    return DEFAULT_HOURLY


def calculate_cluster_cost(
    *,
    node_type: str,
    avg_nodes: float,
    hours_per_month: float = HOURS_PER_MONTH,
) -> dict[str, Any]:
    hourly_rate = _hourly_rate(node_type)
    avg = max(float(avg_nodes or 0), 0.0)
    monthly_cost = hourly_rate * avg * hours_per_month
    return {
        "node_type": node_type,
        "hourly_rate": round(hourly_rate, 4),
        "avg_nodes": round(avg, 2),
        "hours_per_month": hours_per_month,
        "monthly_cost": round(monthly_cost, 2),
    }


def estimate_monthly_costs(
    *,
    current_node_type: str,
    recommended_node_type: str,
    current_avg_nodes: float,
    recommended_avg_nodes: float,
    hours_per_month: float = HOURS_PER_MONTH,
) -> dict[str, float]:
    """Compare current vs recommended monthly spend."""
    current = calculate_cluster_cost(
        node_type=current_node_type,
        avg_nodes=current_avg_nodes,
        hours_per_month=hours_per_month,
    )
    recommended = calculate_cluster_cost(
        node_type=recommended_node_type,
        avg_nodes=recommended_avg_nodes,
        hours_per_month=hours_per_month,
    )
    cur = float(current["monthly_cost"])
    rec = float(recommended["monthly_cost"])
    savings = cur - rec
    savings_pct = (savings / cur * 100.0) if cur > 0 else 0.0
    return {
        "monthly_cost_current_usd": round(cur, 2),
        "monthly_cost_recommended_usd": round(rec, 2),
        "savings_usd": round(savings, 2),
        "savings_pct": round(savings_pct, 1),
        "annual_savings_usd": round(savings * 12, 2),
        "current_hourly_rate": float(current["hourly_rate"]),
        "recommended_hourly_rate": float(recommended["hourly_rate"]),
    }
