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
from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import compute_sizing_hints
from edim_dde_domain.agents.cluster_tuning.logic import parse_sizing, prepare_sizing_payload


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
