"""Golden-case quality gates for cluster_tuning recommendations."""

from __future__ import annotations

import pytest

from edim_dde_domain.evaluation import ClusterTuningQualityEvaluator


def _pattern(history: str) -> str:
    return (
        "### 1. Workload type\nBatch.\n"
        "### 2. Resource utilization\nPeak CPU 22 and memory 31.\n"
        "### 3. Performance characteristics\nStable.\n"
        "### 4. Optimization opportunities\nReduce max workers.\n"
        f"### 5. Historical evidence\n{history}"
    )


@pytest.mark.parametrize(
    ("metrics", "recommendation", "min_score"),
    [
        (
            {
                "azure_worker_vm_size": "Standard_D8s_v5",
                "max_worker_nodes_provisioned": 16,
                "peak_worker_cpu_utilization_pct": 22,
                "peak_worker_memory_utilization_pct": 31,
            },
            {
                "node_family": "D",
                "vcpus": 4,
                "recommended_min_workers": 0,
                "recommended_max_workers": 8,
                "auto_termination_minutes": 0,
                "rationale": "Peak CPU 22 and memory 31 with current max 16.",
                "pattern_analysis": _pattern(
                    "An applied experience seen 2 occurrences corroborated reducing workers."
                ),
            },
            0.9,
        ),
        (
            {
                "azure_worker_vm_size": "Standard_E8s_v5",
                "max_worker_nodes_provisioned": 10,
                "peak_worker_cpu_utilization_pct": 75,
                "peak_worker_memory_utilization_pct": 95,
            },
            {
                "node_family": "E",
                "vcpus": 8,
                "recommended_min_workers": 0,
                "recommended_max_workers": 10,
                "auto_termination_minutes": 0,
                "rationale": "Peak CPU 75 and memory 95 with current max 10.",
                "pattern_analysis": _pattern(
                    "Memory-pressure guidance supported keeping E-family."
                ),
            },
            0.85,
        ),
    ],
)
def test_golden_recommendations_pass(metrics, recommendation, min_score):
    result = ClusterTuningQualityEvaluator().evaluate(
        inputs={"metrics": metrics},
        output={"recommendation": recommendation},
        context={"historical_context": "### Similar past experiences\nOutcome: applied"},
    )
    assert result.passed
    assert result.score >= min_score
    assert result.confidence == 1.0


def test_bad_low_util_family_flip_is_caught():
    metrics = {
        "azure_worker_vm_size": "Standard_D8s_v5",
        "max_worker_nodes_provisioned": 16,
        "peak_worker_cpu_utilization_pct": 22,
        "peak_worker_memory_utilization_pct": 31,
    }
    result = ClusterTuningQualityEvaluator().evaluate(
        inputs={"metrics": metrics},
        output={
            "recommendation": {
                "node_family": "E",
                "vcpus": 4,
                "recommended_min_workers": 0,
                "recommended_max_workers": 8,
                "auto_termination_minutes": 0,
                "rationale": "Use E because similar jobs did.",
                "pattern_analysis": "Downsize.",
            }
        },
        context={"historical_context": "### Similar past experiences\nOutcome: applied"},
    )
    assert not result.passed
    assert result.dimensions["direction"] < 1.0
    assert result.dimensions["history"] == 0.0
    assert result.findings


def test_confidence_drops_when_critical_metrics_are_missing():
    result = ClusterTuningQualityEvaluator().evaluate(
        inputs={"metrics": {"azure_worker_vm_size": "Standard_D8s_v5"}},
        output={
            "node_family": "D",
            "vcpus": 4,
            "min_workers": 0,
            "max_workers": 4,
            "auto_termination_minutes": 0,
            "pattern_analysis": _pattern("No relevant history."),
            "rationale": "Insufficient metrics.",
        },
    )
    assert result.confidence < 0.6


def test_headroom_is_not_misread_as_oom():
    result = ClusterTuningQualityEvaluator().evaluate(
        inputs={
            "metrics": {
                "azure_worker_vm_size": "Standard_D8s_v5",
                "max_worker_nodes_provisioned": 16,
                "peak_worker_cpu_utilization_pct": 22,
                "peak_worker_memory_utilization_pct": 31,
            }
        },
        output={
            "node_family": "D",
            "vcpus": 4,
            "min_workers": 0,
            "max_workers": 8,
            "auto_termination_minutes": 0,
            "pattern_analysis": _pattern("No relevant history. Headroom available."),
            "rationale": "Peak CPU 22 and memory 31 with current max 16.",
        },
    )
    assert result.dimensions["safety"] == 1.0


def test_high_memory_utilization_does_not_support_oom_claim():
    result = ClusterTuningQualityEvaluator().evaluate(
        inputs={
            "metrics": {
                "azure_worker_vm_size": "Standard_E8s_v5",
                "max_worker_nodes_provisioned": 10,
                "peak_worker_cpu_utilization_pct": 70,
                "peak_worker_memory_utilization_pct": 98,
            }
        },
        output={
            "recommendation": {
                "node_family": "E",
                "vcpus": 8,
                "recommended_min_workers": 0,
                "recommended_max_workers": 10,
                "auto_termination_minutes": 0,
                "pattern_analysis": _pattern("No relevant history."),
                "rationale": "The job failed with OOM because memory reached 98.",
            }
        },
    )
    assert result.dimensions["safety"] == 0.5
    assert "Failure claim lacks failure/error evidence" in result.findings


def test_direction_uses_thresholds_from_evaluation_context():
    result = ClusterTuningQualityEvaluator().evaluate(
        inputs={
            "metrics": {
                "azure_worker_vm_size": "Standard_D8s_v5",
                "max_worker_nodes_provisioned": 8,
                "peak_worker_cpu_utilization_pct": 65,
                "peak_worker_memory_utilization_pct": 30,
            }
        },
        output={
            "recommendation": {
                "node_family": "F",
                "vcpus": 8,
                "recommended_min_workers": 0,
                "recommended_max_workers": 8,
                "auto_termination_minutes": 0,
                "pattern_analysis": _pattern("No relevant history."),
                "rationale": "CPU 65 is high under the configured policy; memory is 30.",
            }
        },
        context={
            "resource_pressure_config": {
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
            }
        },
    )
    assert result.dimensions["direction"] == 1.0
