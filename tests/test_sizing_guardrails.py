"""Unit tests for sizing policy, guardrails, and resource optimization."""

from __future__ import annotations

import json

from edim_dde_domain.agents.cluster_tuning.helpers.guardrails import (
    format_guardrail_feedback,
    should_retry_sizing,
    validate_and_clamp_with_adjustments,
)
from edim_dde_domain.agents.cluster_tuning.helpers.resource_optimization import (
    estimate_resource_optimization,
)
from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import (
    compute_sizing_hints,
    infer_reason_codes,
)
from edim_dde_domain.agents.cluster_tuning.logic import (
    generate_recommendation,
    parse_sizing,
    prepare_sizing_payload,
)


def test_compute_sizing_hints_low_util():
    hints = compute_sizing_hints(
        {
            "azure_worker_vm_size": "Standard_D8s_v5",
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


def test_compute_sizing_hints_honors_agent_yaml_threshold_override():
    hints = compute_sizing_hints(
        {
            "azure_worker_vm_size": "Standard_D8s_v5",
            "peak_worker_cpu_utilization_pct": 65,
            "peak_worker_memory_utilization_pct": 30,
        },
        resource_pressure_config={
            "dimensions": {
                "cpu": {
                    "thresholds": {
                        "low_below": 25,
                        "high_at": 60,
                        "saturated_at": 80,
                    },
                    "preferred_families": ["F"],
                }
            }
        },
    )
    pressure = hints["resource_pressure"]
    assert pressure["dimensions"]["cpu"]["level"] == "high"
    assert pressure["limiting_resource"] == "cpu"
    assert hints["suggested_vm_family"] == "F"


def test_guardrails_honor_capacity_buffer_override():
    applied, adjustments = validate_and_clamp_with_adjustments(
        {
            "node_family": "D",
            "vcpus": 8,
            "min_workers": 0,
            "max_workers": 4,
            "auto_termination_minutes": 0,
            "rationale": "downsize",
        },
        job_run_ingest={
            "azure_worker_vm_size": "Standard_D8s_v5",
            "max_worker_nodes_provisioned": 16,
            "avg_worker_nodes_consumed": 4,
            "p99_worker_nodes_consumed": 5,
            "driver_node_count": 1,
        },
        resource_pressure_config={"capacity_buffer_pct": 50},
    )
    # floor = ceil(5 * 1.5) = 8 under a 50% buffer override
    assert applied["max_workers"] >= 8
    assert any(a["reason"] == "sizing_floor" for a in adjustments)


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


def test_sku_mapped_alone_does_not_trigger_retry():
    adjustments = [
        {
            "field": "azure_node_type",
            "llm_value": None,
            "applied_value": "Standard_E4s_v5",
            "reason": "sku_mapped",
        }
    ]
    assert should_retry_sizing(adjustments, sizing_attempts=1) is False
    assert format_guardrail_feedback(adjustments) == "None"


def test_retryable_clamp_triggers_retry_once():
    adjustments = [
        {
            "field": "auto_termination_minutes",
            "llm_value": 99,
            "applied_value": 0,
            "reason": "auto_termination_policy",
        }
    ]
    assert should_retry_sizing(adjustments, sizing_attempts=1) is True
    assert should_retry_sizing(adjustments, sizing_attempts=2) is False
    feedback = format_guardrail_feedback(adjustments)
    assert "auto_termination_minutes" in feedback
    assert "required_applied=0" in feedback


def test_parse_sizing_sets_retry_flags():
    metrics = {
        "azure_worker_vm_size": "Standard_E8s_v3",
        "max_worker_nodes_provisioned": 16,
        "avg_worker_nodes_consumed": 4,
        "p99_worker_nodes_consumed": 5,
        "driver_node_count": 1,
    }
    out = parse_sizing(
        {
            "metrics": metrics,
            "sizing_raw": json.dumps(
                {
                    "pattern_analysis": "x",
                    "node_family": "E",
                    "vcpus": 4,
                    "min_workers": 0,
                    "max_workers": 2,
                    "auto_termination_minutes": 99,
                    "rationale": "bad",
                }
            ),
        }
    )
    assert out["sizing_attempts"] == 1
    assert out["guardrail_retries"] == 0
    assert out["sizing_needs_retry"] is True
    assert "auto_termination" in out["guardrail_feedback"]

    out2 = parse_sizing(
        {
            **out,
            "metrics": metrics,
            "sizing_raw": json.dumps(
                {
                    "pattern_analysis": "ok",
                    "node_family": "E",
                    "vcpus": 4,
                    "min_workers": 0,
                    "max_workers": 8,
                    "auto_termination_minutes": 0,
                    "rationale": "fixed",
                }
            ),
        }
    )
    assert out2["sizing_attempts"] == 2
    assert out2["guardrail_retries"] == 1
    assert out2["sizing_needs_retry"] is False


def test_prepare_sizing_preserves_feedback_on_retry():
    metrics = {"azure_worker_vm_size": "Standard_E8s_v3", "max_worker_nodes_provisioned": 8}
    payload = prepare_sizing_payload(
        {"metrics": metrics, "guardrail_feedback": "fix max_workers"}
    )
    assert payload["guardrail_feedback"] == "fix max_workers"


def test_estimate_resource_optimization_downsize():
    # 8 vCPU × 16 workers → 4 vCPU × 8 workers = 75% capacity released
    opt = estimate_resource_optimization(
        current_vcpus=8,
        current_max_workers=16,
        recommended_vcpus=4,
        recommended_max_workers=8,
    )
    assert opt["current_capacity_vcpu"] == 128
    assert opt["recommended_capacity_vcpu"] == 32
    assert opt["resource_optimization_pct"] == 75.0


def test_estimate_resource_optimization_upsize_is_negative():
    opt = estimate_resource_optimization(
        current_vcpus=4,
        current_max_workers=4,
        recommended_vcpus=8,
        recommended_max_workers=4,
    )
    assert opt["resource_optimization_pct"] == -100.0


def test_infer_reason_codes_without_ids_still_emits_pressure():
    """Metrics-override blobs often omit job_id/cluster_id; that is not 'no evidence'."""
    codes = infer_reason_codes(
        {
            "azure_worker_vm_size": "Standard_D8s_v5",
            "max_worker_nodes_provisioned": 10,
            "avg_worker_nodes_consumed": 8.0,
            "p99_worker_nodes_consumed": 10.0,
            "peak_worker_cpu_utilization_pct": 45,
            "peak_worker_memory_utilization_pct": 94,
        },
        {"node_family": "E", "recommended_max_workers": 10},
        change_required=True,
    )
    assert "INSUFFICIENT_EVIDENCE" not in codes
    assert "RESOURCE_PRESSURE_MEMORY_SATURATED" in codes
    assert "CAPACITY_HEADROOM_LOW" in codes
    assert "RESOURCE_SHAPE_CHANGED" in codes


def test_infer_reason_codes_empty_metrics_is_insufficient():
    assert infer_reason_codes({}, {"node_family": "D"}) == ["INSUFFICIENT_EVIDENCE"]
    assert infer_reason_codes(
        {"job_id": "j-1", "cluster_id": "c-1"},
        {"node_family": "D"},
    ) == ["INSUFFICIENT_EVIDENCE"]


def test_generate_recommendation_merges_request_ids_into_metrics_view():
    out = generate_recommendation(
        {
            "job_id": "j-override-1",
            "cluster_id": "c-override-1",
            "metrics": {
                "azure_worker_vm_size": "Standard_D8s_v5",
                "max_worker_nodes_provisioned": 16,
                "avg_worker_nodes_consumed": 3.0,
                "p99_worker_nodes_consumed": 5.0,
                "peak_worker_cpu_utilization_pct": 22,
                "peak_worker_memory_utilization_pct": 31,
            },
            "sizing": {
                "current_node_type": "Standard_D8s_v5",
                "recommended_node_type": "Standard_D8ads_v6",
                "node_family": "D",
                "vcpus": 8,
                "current_max_workers": 16,
                "recommended_min_workers": 0,
                "recommended_max_workers": 6,
                "min_workers": 0,
                "auto_termination_minutes": 0,
            },
            "risk_assessment": {"risk_level": "low"},
            "performance_validation": {"meets_peak_requirements": True},
            "sizing_hints_full": {},
        }
    )
    codes = out["recommendation"]["reason_codes"]
    assert "INSUFFICIENT_EVIDENCE" not in codes
    assert any(c.startswith("RESOURCE_PRESSURE_") for c in codes)
    assert any(c.startswith("CAPACITY_HEADROOM_") for c in codes)
    # Request IDs must not be written back into state metrics by side effect —
    # generate_recommendation only returns recommendation/comparison.
    assert set(out.keys()) >= {"recommendation", "comparison"}
