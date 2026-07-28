"""Cost helpers for cluster tuning (SQL collect is domain.sql.query)."""

from __future__ import annotations


def estimate_monthly_costs(
    *,
    current_max_workers: int,
    recommended_max_workers: int,
    recommended_node_type: str,
) -> dict[str, float]:
    """Rough cost model (replace with SKU pricing later)."""
    cur_cost = float(current_max_workers) * 100.0
    rec_cost = float(recommended_max_workers) * 100.0
    if "E4" in recommended_node_type:
        rec_cost *= 0.55
    savings = max(0.0, cur_cost - rec_cost)
    return {
        "monthly_cost_current_usd": round(cur_cost, 2),
        "monthly_cost_recommended_usd": round(rec_cost, 2),
        "savings_usd": round(savings, 2),
    }
