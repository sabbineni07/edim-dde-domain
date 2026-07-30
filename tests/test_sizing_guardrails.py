"""Unit tests for sizing policy, guardrails, and costs."""

from __future__ import annotations

from edim_dde_domain.agents.cluster_tuning.guardrails import (
    validate_and_clamp_with_adjustments,
)
from edim_dde_domain.agents.cluster_tuning.sizing_policy import compute_sizing_hints
from edim_dde_domain.tools.cluster_metrics import estimate_monthly_costs


def test_compute_sizing_hints_low_util():
    hints = compute_sizing_hints(
        {
            "peak_worker_cpu_utilization_pct": 20,
            "peak_worker_memory_utilization_pct": 25,
            "avg_worker_nodes_consumed": 4,
            "max_worker_nodes_provisioned": 16,
            "p99_worker_nodes_consumed": 5,
            "driver_node_count": 1,
        }
    )
    assert hints["recommended_max_workers"] <= 16
    assert hints["recommended_max_workers"] >= 1
    assert hints["suggested_vm_family"] in ("D", "E", "F", "L")


def test_guardrails_map_sku_and_clamp():
    applied, adjustments = validate_and_clamp_with_adjustments(
        {
            "node_family": "E",
            "vcpus": 4,
            "min_workers": 0,
            "max_workers": 2,
            "auto_termination_minutes": 99,
            "rationale": "downsize",
        },
        job_run_ingest={
            "azure_worker_vm_size": "Standard_E8s_v3",
            "max_worker_nodes_provisioned": 16,
            "avg_worker_nodes_consumed": 4,
            "p99_worker_nodes_consumed": 5,
            "driver_node_count": 1,
        },
    )
    assert applied["auto_termination_minutes"] == 0
    assert applied["max_workers"] >= 5  # sizing floor from p99+buffer
    assert applied["azure_node_type"].startswith("Standard_E")
    assert any(a["field"] == "auto_termination_minutes" for a in adjustments)


def test_estimate_monthly_costs_savings():
    costs = estimate_monthly_costs(
        current_node_type="Standard_E8s_v3",
        recommended_node_type="Standard_E4s_v3",
        current_avg_nodes=8,
        recommended_avg_nodes=4,
    )
    assert costs["savings_usd"] > 0
    assert costs["monthly_cost_current_usd"] > costs["monthly_cost_recommended_usd"]
