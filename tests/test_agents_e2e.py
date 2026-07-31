"""Domain agent e2e tests (metrics / evidence_pack overrides + test LLM)."""

from __future__ import annotations

from edim_dde_ai import create_agent

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
