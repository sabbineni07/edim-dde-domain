"""Domain agent e2e tests (override / stub paths)."""

from __future__ import annotations

from edim_dde_ai import create_agent

from edim_dde_domain import bootstrap_agents
from edim_dde_domain.sources import clear_sources
from edim_dde_domain.tools.spark_telemetry import build_evidence_pack_for_run


def setup_module() -> None:
    clear_sources()
    bootstrap_agents()


def test_tool_build_evidence_pack():
    pack = build_evidence_pack_for_run(
        job_run_id="jr-1",
        job_id="j-1",
        error_text="OutOfMemoryError: Java heap space",
    )
    assert pack["evidence"][0]["excerpt"].startswith("OutOfMemoryError")


def test_spark_rca_oom_stub():
    agent = create_agent("spark_rca")
    out = agent.invoke(
        {
            "job_run_id": "jr-1",
            "job_id": "j-1",
            "error_text": "Executor OutOfMemoryError: Java heap space",
        }
    )
    assert out["result"]["root_cause"]["category"] == "resource"


def test_spark_rca_evidence_override():
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


def test_cluster_tuning_with_explanation():
    agent = create_agent("cluster_tuning")
    out = agent.invoke(
        {
            "job_id": "j-1",
            "cluster_id": "c-1",
            "include_explanation": True,
            "metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 16,
                "peak_worker_cpu_utilization_pct": 20,
                "peak_worker_memory_utilization_pct": 25,
            },
        }
    )
    assert out["recommendation"]["recommended_max_workers"] < 16
    assert out["explanation"]


def test_cluster_tuning_skips_explanation():
    agent = create_agent("cluster_tuning")
    out = agent.invoke(
        {
            "job_id": "j-1",
            "cluster_id": "c-1",
            "include_explanation": False,
        }
    )
    assert out.get("recommendation")
    assert not out.get("explanation")
