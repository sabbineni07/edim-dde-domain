"""Tests for cluster_tuning historical_context (store + RAG merge)."""

from __future__ import annotations

from edim_dde_ai.recommendations import (
    MemoryRecommendationStore,
    RecommendationRecord,
    clear_recommendation_store,
    set_recommendation_store,
)
from edim_dde_domain.agents.cluster_tuning.helpers.historical_context import (
    build_retrieval_query,
    compose_historical_context,
    format_store_history,
    select_history_records,
    similarity_score,
)
from edim_dde_domain.agents.cluster_tuning.logic import prepare_sizing_payload


def test_build_retrieval_query_includes_sku():
    out = build_retrieval_query(
        {
            "metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 16,
                "peak_worker_cpu_utilization_pct": 20,
            }
        }
    )
    assert "Standard_E8s_v3" in out["retrieval_query"]
    assert "rightsizing" in out["retrieval_query"]


def test_compose_includes_store_and_guidance():
    store = MemoryRecommendationStore()
    set_recommendation_store(store)
    try:
        store.save(
            RecommendationRecord(
                recommendation_id="rec-1",
                job_id="j-1",
                status="accepted",
                response={
                    "recommendation": {
                        "recommended_max_workers": 4,
                        "recommended_node_type": "Standard_E4s_v3",
                    },
                    "job_cluster_metrics": {
                        "azure_worker_vm_size": "Standard_E8s_v3",
                        "max_worker_nodes_provisioned": 16,
                        "peak_worker_cpu_utilization_pct": 20,
                    },
                    "reason_codes": ["CAPACITY_HEADROOM_HIGH"],
                    "risk_assessment": {"level": "low"},
                },
            )
        )
        text = compose_historical_context(
            {
                "job_id": "j-1",
                "metrics": {
                    "azure_worker_vm_size": "Standard_E8s_v3",
                    "max_worker_nodes_provisioned": 16,
                },
                "guidance_context": "Prefer reducing max_workers when underutilized.",
            }
        )
        assert "Prior recommendations" in text
        assert "accepted" in text
        assert "4" in text
        assert "Retrieved sizing guidance" in text
        assert "underutilized" in text
    finally:
        clear_recommendation_store()


def test_compose_empty_is_none():
    clear_recommendation_store()
    assert compose_historical_context({"job_id": "missing"}) == "None"


def test_format_store_history_empty():
    assert format_store_history([]) == ""


def test_select_prefers_job_then_similar():
    state = {
        "job_id": "j-target",
        "metrics": {
            "azure_worker_vm_size": "Standard_E8s_v3",
            "max_worker_nodes_provisioned": 16,
            "peak_worker_cpu_utilization_pct": 22,
            "peak_worker_memory_utilization_pct": 30,
            "avg_worker_nodes_consumed": 4,
        },
    }
    same = RecommendationRecord(
        recommendation_id="same-1",
        job_id="j-target",
        status="accepted",
        response={
            "recommendation": {"recommended_max_workers": 4},
            "job_cluster_metrics": state["metrics"],
        },
    )
    similar = RecommendationRecord(
        recommendation_id="sim-1",
        job_id="j-other",
        status="applied",
        response={
            "recommendation": {"recommended_max_workers": 6},
            "job_cluster_metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 14,
                "peak_worker_cpu_utilization_pct": 25,
                "peak_worker_memory_utilization_pct": 28,
                "avg_worker_nodes_consumed": 5,
            },
        },
    )
    unrelated = RecommendationRecord(
        recommendation_id="noise-1",
        job_id="j-noise",
        status="proposed",
        response={
            "recommendation": {"recommended_max_workers": 64},
            "job_cluster_metrics": {
                "azure_worker_vm_size": "Standard_D32s_v3",
                "max_worker_nodes_provisioned": 100,
                "peak_worker_cpu_utilization_pct": 95,
            },
        },
    )
    selected = select_history_records(
        state,
        [unrelated, similar, same],
        config={"history_job_top_n": 2, "history_similar_top_n": 2},
    )
    ids = [r["recommendation_id"] for r in selected]
    assert ids[0] == "same-1"
    assert "sim-1" in ids
    assert selected[0]["_match_kind"] == "job_id"


def test_select_similar_when_no_job_match():
    state = {
        "job_id": "brand-new",
        "metrics": {
            "azure_worker_vm_size": "Standard_E8s_v3",
            "max_worker_nodes_provisioned": 16,
            "peak_worker_cpu_utilization_pct": 20,
        },
    }
    peer = RecommendationRecord(
        recommendation_id="peer-1",
        job_id="j-peer",
        status="accepted",
        response={
            "recommendation": {"recommended_max_workers": 4},
            "job_cluster_metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 16,
                "peak_worker_cpu_utilization_pct": 18,
            },
        },
    )
    selected = select_history_records(
        state, [peer], config={"history_job_top_n": 5, "history_similar_top_n": 3}
    )
    assert len(selected) == 1
    assert selected[0]["_match_kind"] == "similar"
    assert similarity_score(state, peer) > 0


def test_prepare_sizing_uses_historical_context():
    store = MemoryRecommendationStore()
    set_recommendation_store(store)
    try:
        store.save(
            RecommendationRecord(
                recommendation_id="rec-2",
                job_id="job-x",
                status="proposed",
                response={
                    "recommendation": {"recommended_max_workers": 8},
                    "job_cluster_metrics": {
                        "azure_worker_vm_size": "Standard_E8s_v3",
                        "max_worker_nodes_provisioned": 16,
                    },
                },
            )
        )
        payload = prepare_sizing_payload(
            {
                "job_id": "job-x",
                "metrics": {
                    "azure_worker_vm_size": "Standard_E8s_v3",
                    "max_worker_nodes_provisioned": 16,
                },
            },
            history_config={"history_job_top_n": 3, "history_similar_top_n": 2},
        )
        assert payload["historical_context"] != "None"
        assert "Prior recommendations" in payload["historical_context"]
    finally:
        clear_recommendation_store()
