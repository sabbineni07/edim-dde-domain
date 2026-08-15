"""Unit tests for validate_performance (legacy parity)."""

from __future__ import annotations

from edim_dde_domain.agents.cluster_tuning.helpers.validate_performance import (
    validate_performance,
)
from edim_dde_domain.agents.cluster_tuning.logic import assess_risks


def test_validate_performance_maintained_on_modest_downsize():
    # 8×16=128 → 4×16=64 (50% — fails 80% floor)
    out = validate_performance(
        current_vcpus=8,
        current_max_workers=16,
        recommended_vcpus=4,
        recommended_max_workers=16,
        peak_cpu_pct=20,
        peak_memory_pct=25,
    )
    assert out["meets_peak_requirements"] is False
    assert out["estimated_impact"] == "degradation_risk"
    assert "recommended_capacity_below_80pct_of_current" in out["reasons"]


def test_validate_performance_ok_when_near_current():
    # 8×16=128 → 8×14=112 (~87.5% ≥ 80%)
    out = validate_performance(
        current_vcpus=8,
        current_max_workers=16,
        recommended_vcpus=8,
        recommended_max_workers=14,
        peak_cpu_pct=30,
        peak_memory_pct=30,
    )
    assert out["meets_peak_requirements"] is True
    assert out["estimated_impact"] == "maintained"
    assert out["reasons"] == []


def test_validate_performance_high_peak_blocks_aggressive_cut():
    out = validate_performance(
        current_vcpus=8,
        current_max_workers=16,
        recommended_vcpus=8,
        recommended_max_workers=14,  # 112/128 = 87.5% < 90%
        peak_cpu_pct=96,
        peak_memory_pct=50,
        job_run_ingest={
            "peak_worker_cpu_utilization_pct": 96,
            "peak_worker_memory_utilization_pct": 50,
            "avg_worker_nodes_consumed": 10,
            "max_worker_nodes_provisioned": 16,
            "p99_worker_nodes_consumed": 12,
            "driver_node_count": 1,
        },
    )
    assert out["meets_peak_requirements"] is False
    assert "high_peak_util_with_aggressive_capacity_cut" in out["reasons"]


def test_validate_performance_honors_target_override():
    # Same cut as above, but a higher configured target treats 91 as not "high peak".
    out = validate_performance(
        current_vcpus=8,
        current_max_workers=16,
        recommended_vcpus=8,
        recommended_max_workers=14,
        peak_cpu_pct=91,
        peak_memory_pct=50,
        job_run_ingest={
            "peak_worker_cpu_utilization_pct": 91,
            "peak_worker_memory_utilization_pct": 50,
            "avg_worker_nodes_consumed": 10,
            "max_worker_nodes_provisioned": 16,
            "p99_worker_nodes_consumed": 12,
            "driver_node_count": 1,
        },
        resource_pressure_config={"target_utilization_pct": 95},
    )
    assert out["meets_peak_requirements"] is True
    assert "high_peak_util_with_aggressive_capacity_cut" not in out["reasons"]


def test_assess_risks_folds_performance_validation():
    out = assess_risks(
        {
            "sizing": {
                "current_node_type": "Standard_E8s_v3",
                "recommended_node_type": "Standard_E4s_v5",
                "vcpus": 4,
                "current_max_workers": 16,
                "recommended_max_workers": 8,
            },
            "metrics": {
                "peak_worker_cpu_utilization_pct": 20,
                "peak_worker_memory_utilization_pct": 25,
            },
            "performance_validation": {
                "meets_peak_requirements": False,
                "current_capacity_vcpu": 128,
                "recommended_capacity_vcpu": 32,
                "reduction_pct": 75.0,
                "reduction_risk_level": "high",
                "reasons": ["recommended_capacity_below_80pct_of_current"],
            },
        }
    )
    risk = out["risk_assessment"]
    assert risk["risk_level"] == "high"
    assert risk["meets_peak_requirements"] is False
    assert any("Performance validation" in m for m in risk["mitigations"])
