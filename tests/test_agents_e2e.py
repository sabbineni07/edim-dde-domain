"""Domain agent e2e tests (metrics / evidence_pack overrides + test LLM)."""

from __future__ import annotations

from edim_dde_ai import create_agent
from edim_dde_ai.evaluation import evaluate

from edim_dde_domain.agents.spark_rca.helpers.evidence_pack import build_evidence_pack


def test_build_evidence_pack_from_failure_anchor():
    pack = build_evidence_pack(
        job_run_id="jr-1",
        job_id="j-1",
        failure_anchors=[
            {
                "event_id": "1",
                "event_type": "pipeline_end",
                "failure_reason": "OutOfMemoryError: Java heap space",
                "successful": False,
                "status": "failed",
            }
        ],
    )
    assert pack["evidence"][0]["excerpt"].startswith("OutOfMemoryError")
    assert pack["raw_anchors"]["failure_reason"].startswith("OutOfMemoryError")


def test_spark_rca_with_evidence_override(bootstrapped_agents):
    agent = create_agent("spark_rca")
    out = agent.invoke(
        {
            "job_run_id": "jr-1",
            "job_id": "j-1",
            "evidence_pack": {
                "job_run_id": "jr-1",
                "evidence": [
                    {
                        "ref": "e1",
                        "excerpt": "Executor OutOfMemoryError: Java heap space",
                    }
                ],
                "raw_anchors": {
                    "failure_reason": "Executor OutOfMemoryError: Java heap space"
                },
            },
        }
    )
    assert out["result"]["root_cause"]["category"] == "resource"
    assert out["result"]["quality"]["passed"] is True
    assert out["result"]["quality"]["confidence"] < 1.0


def test_spark_rca_sql_error_override(bootstrapped_agents):
    agent = create_agent("spark_rca")
    out = agent.invoke(
        {
            "job_run_id": "jr-1",
            "job_id": "j-1",
            "evidence_pack": {
                "job_run_id": "jr-1",
                "evidence": [{"ref": "e1", "excerpt": "Table not found: sales"}],
                "raw_anchors": {"failure_reason": "AnalysisException: Table not found"},
            },
        }
    )
    assert out["result"]["root_cause"]["category"] == "sql_error"
    assert out["result"]["quality"]["passed"] is True


def test_cluster_tuning_with_explanation(bootstrapped_agents):
    agent = create_agent("cluster_tuning")
    out = agent.invoke(
        {
            "job_id": "j-1",
            "cluster_id": "c-1",
            "include_explanation": True,
            "metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 16,
                "avg_worker_nodes_consumed": 4.0,
                "p99_worker_nodes_consumed": 5.0,
                "peak_worker_cpu_utilization_pct": 20,
                "peak_worker_memory_utilization_pct": 25,
                "avg_worker_cpu_utilization_pct": 15,
                "avg_worker_memory_utilization_pct": 18,
                "driver_node_count": 1,
            },
        }
    )
    assert out["recommendation"]["recommended_max_workers"] < 16
    assert out["explanation"]


def test_cluster_tuning_low_util_quality_gate(bootstrapped_agents):
    """Full graph + stub LLM must preserve D-family and pass the quality rubric."""
    metrics = {
        "job_id": "j-quality-1",
        "cluster_id": "c-quality-1",
        "azure_worker_vm_size": "Standard_D8s_v5",
        "max_worker_nodes_provisioned": 16,
        "avg_worker_nodes_consumed": 3.0,
        "p99_worker_nodes_consumed": 5.0,
        "peak_worker_cpu_utilization_pct": 22,
        "peak_worker_memory_utilization_pct": 31,
        "avg_worker_cpu_utilization_pct": 15,
        "avg_worker_memory_utilization_pct": 20,
        "driver_node_count": 1,
    }
    out = create_agent("cluster_tuning").invoke(
        {
            "job_id": "j-quality-1",
            "cluster_id": "c-quality-1",
            "include_explanation": False,
            "metrics": metrics,
        }
    )
    assert out["recommendation"]["node_family"] == "D"
    result = evaluate(
        "cluster_tuning.quality",
        inputs={"metrics": metrics},
        output=out,
        context={"historical_context": out.get("historical_context")},
    )
    assert result.passed, result.to_dict()
    assert result.score >= 0.85


def test_cluster_tuning_skips_explanation(bootstrapped_agents):
    agent = create_agent("cluster_tuning")
    out = agent.invoke(
        {
            "job_id": "j-1",
            "cluster_id": "c-1",
            "include_explanation": False,
            "metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 16,
                "avg_worker_nodes_consumed": 4.0,
                "p99_worker_nodes_consumed": 5.0,
                "peak_worker_cpu_utilization_pct": 20,
                "peak_worker_memory_utilization_pct": 25,
                "avg_worker_cpu_utilization_pct": 15,
                "avg_worker_memory_utilization_pct": 18,
                "driver_node_count": 1,
            },
        }
    )
    assert out.get("recommendation")
    assert not out.get("explanation")
    assert out.get("sizing_attempts") == 1
    assert out.get("guardrail_retries") == 0
    assert "performance_validation" in out
    assert "meets_peak_requirements" in out["performance_validation"]


def test_cluster_tuning_guardrail_retry_loop(bootstrapped_agents):
    """First sizing call violates policy; second call (with feedback) succeeds."""
    import json

    from edim_dde_ai import set_llm_provider

    from edim_dde_domain.testing import DomainStubLLM

    class _RetryThenOk(DomainStubLLM):
        def __init__(self) -> None:
            self.sizing_calls = 0

        def invoke(self, messages, *, config=None):  # type: ignore[no-untyped-def]
            chain = str((config or {}).get("chain") or "")
            if chain == "sizing":
                self.sizing_calls += 1
                if self.sizing_calls == 1:
                    return json.dumps(
                        {
                            "pattern_analysis": "first pass (violates)",
                            "node_family": "E",
                            "vcpus": 4,
                            "min_workers": 0,
                            "max_workers": 1,
                            "auto_termination_minutes": 99,
                            "rationale": "too aggressive",
                        }
                    )
            return super().invoke(messages, config=config)

    stub = _RetryThenOk()
    set_llm_provider(stub)
    try:
        agent = create_agent("cluster_tuning")
        out = agent.invoke(
            {
                "job_id": "j-1",
                "cluster_id": "c-1",
                "include_explanation": False,
                "metrics": {
                    "azure_worker_vm_size": "Standard_E8s_v3",
                    "max_worker_nodes_provisioned": 16,
                    "avg_worker_nodes_consumed": 4.0,
                    "p99_worker_nodes_consumed": 5.0,
                    "peak_worker_cpu_utilization_pct": 20,
                    "peak_worker_memory_utilization_pct": 25,
                    "avg_worker_cpu_utilization_pct": 15,
                    "avg_worker_memory_utilization_pct": 18,
                    "driver_node_count": 1,
                },
            }
        )
    finally:
        set_llm_provider(DomainStubLLM())

    assert stub.sizing_calls == 2
    assert out["sizing_attempts"] == 2
    assert out["guardrail_retries"] == 1
    assert out["sizing_needs_retry"] is False
    assert out["recommendation"]["auto_termination_minutes"] == 0
    assert out["recommendation"]["recommended_max_workers"] >= 5
