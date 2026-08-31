"""Smoke tests for the LangGraph Agent Server adapter."""

from __future__ import annotations

from edim_dde_domain.langsmith_entrypoint import cluster_tuning_graph


def test_cluster_tuning_entrypoint_returns_flat_graph(bootstrapped_agents):
    graph = cluster_tuning_graph()

    node_names = set(graph.get_graph().nodes)

    assert "collect_metrics" in node_names
    assert "generate_recommendation" in node_names


def test_cluster_tuning_entrypoint_accepts_flat_input(bootstrapped_agents):
    graph = cluster_tuning_graph()

    result = graph.invoke(
        {
            "job_id": "langsmith-pilot-job",
            "cluster_id": "langsmith-pilot-cluster",
            "include_explanation": False,
            "metrics": {
                "azure_worker_vm_size": "Standard_D8s_v5",
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

    assert result["recommendation"]
    assert "data" not in result

