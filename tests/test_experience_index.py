"""Tests for experience index (transform, dedupe, auto-index on store write)."""

from __future__ import annotations

from edim_dde_ai.experiences import (
    clear_experience_transforms,
    content_hash,
    dedupe_retrieval_hits,
    get_experience_transform,
    register_experience_transform,
)
from edim_dde_ai.recommendations import (
    MemoryRecommendationStore,
    RecommendationRecord,
    clear_recommendation_store,
    get_recommendation_store,
    set_recommendation_store,
)
from edim_dde_ai.retrieval import (
    MemoryRetrieval,
    RetrievalHit,
    clear_retrieval_provider,
    search_corpus,
    set_retrieval_provider,
)
from edim_dde_domain.agents.cluster_tuning.helpers.experience_transform import (
    ClusterTuningExperienceTransform,
    build_experience_query,
    infer_situation_labels,
    register_cluster_tuning_experience_transform,
)
from edim_dde_domain.agents.cluster_tuning.helpers.historical_context import (
    compose_historical_context,
)


def setup_function() -> None:
    clear_recommendation_store()
    clear_retrieval_provider()
    clear_experience_transforms()


def teardown_function() -> None:
    clear_recommendation_store()
    clear_retrieval_provider()
    clear_experience_transforms()


def test_infer_over_provisioned_from_low_cpu():
    labels = infer_situation_labels(
        metrics={
            "azure_worker_vm_size": "Standard_D8s_v5",
            "peak_worker_cpu_utilization_pct": 22,
            "peak_worker_memory_utilization_pct": 30,
            "max_worker_nodes_provisioned": 16,
            "avg_worker_nodes_consumed": 2,
        },
        reason_codes=["OVERPROVISIONED_AUTOSCALE"],
        recommendation={"recommended_max_workers": 4, "recommended_node_type": "Standard_D4s_v5"},
    )
    assert "over_provisioned" in labels
    assert "sku_change" in labels


def test_transform_builds_situation_action_text():
    register_cluster_tuning_experience_transform()
    t = get_experience_transform("cluster_tuning")
    assert t is not None
    doc = t.transform(
        RecommendationRecord(
            recommendation_id="rec-xp-1",
            job_id="job-9",
            status="applied",
            response={
                "job_cluster_metrics": {
                    "azure_worker_vm_size": "Standard_D8s_v5",
                    "max_worker_nodes_provisioned": 16,
                    "peak_worker_cpu_utilization_pct": 25,
                    "peak_worker_memory_utilization_pct": 35,
                },
                "recommendation": {
                    "recommended_node_type": "Standard_D4s_v5",
                    "recommended_max_workers": 6,
                },
                "reason_codes": ["OVERPROVISIONED_AUTOSCALE", "PER_NODE_UNDERUTILIZED"],
            },
        )
    )
    assert doc is not None
    assert doc.corpus == "cluster-tuning-outcomes"
    assert doc.doc_id == "rec-xp-1"
    assert "Situation:" in doc.text
    assert "over_provisioned" in doc.situation_labels
    assert "reduced max_workers" in doc.text
    assert doc.metadata["job_id"] == "job-9"
    assert doc.action_signature


def test_save_indexes_experience_into_memory_retrieval():
    register_cluster_tuning_experience_transform()
    retrieval = MemoryRetrieval()
    set_retrieval_provider(retrieval)
    set_recommendation_store(MemoryRecommendationStore())

    store = get_recommendation_store()
    store.save(
        RecommendationRecord(
            recommendation_id="rec-idx-1",
            job_id="job-a",
            status="proposed",
            response={
                "job_cluster_metrics": {
                    "azure_worker_vm_size": "Standard_E8s_v3",
                    "max_worker_nodes_provisioned": 12,
                    "peak_worker_cpu_utilization_pct": 18,
                    "peak_worker_memory_utilization_pct": 40,
                },
                "recommendation": {
                    "recommended_node_type": "Standard_E4s_v3",
                    "recommended_max_workers": 4,
                },
                "reason_codes": ["PER_NODE_UNDERUTILIZED"],
            },
        )
    )
    hits = search_corpus(
        "over_provisioned reduced max_workers",
        corpus="cluster-tuning-outcomes",
        top_k=3,
    )
    assert hits
    assert hits[0].id == "rec-idx-1"
    assert "Situation:" in hits[0].text


def test_rejected_removes_from_experience_index():
    register_cluster_tuning_experience_transform()
    set_retrieval_provider(MemoryRetrieval())
    set_recommendation_store(MemoryRecommendationStore())
    store = get_recommendation_store()
    store.save(
        RecommendationRecord(
            recommendation_id="rec-rej-1",
            status="proposed",
            response={
                "job_cluster_metrics": {"azure_worker_vm_size": "Standard_D8s_v5"},
                "recommendation": {"recommended_max_workers": 2},
                "reason_codes": ["OVERPROVISIONED_AUTOSCALE"],
            },
        )
    )
    assert search_corpus("over_provisioned", corpus="cluster-tuning-outcomes", top_k=5)
    store.update_status("rec-rej-1", "rejected")
    assert search_corpus("over_provisioned", corpus="cluster-tuning-outcomes", top_k=5) == []


def test_degradation_risk_does_not_imply_under_provisioned():
    """PERFORMANCE_DEGRADATION_RISK describes the proposed change, not cluster state."""
    labels = infer_situation_labels(
        metrics={
            "azure_worker_vm_size": "Standard_D8s_v5",
            "peak_worker_cpu_utilization_pct": 25,
            "peak_worker_memory_utilization_pct": 30,
            "max_worker_nodes_provisioned": 14,
            "avg_worker_nodes_consumed": 3,
        },
        reason_codes=["PERFORMANCE_DEGRADATION_RISK"],
        recommendation={"recommended_max_workers": 7},
    )
    assert "over_provisioned" in labels
    assert "under_provisioned" not in labels


def test_over_and_under_are_mutually_exclusive():
    labels = infer_situation_labels(
        metrics={
            "peak_worker_cpu_utilization_pct": 95,
            "peak_worker_memory_utilization_pct": 92,
            "max_worker_nodes_provisioned": 10,
            "avg_worker_nodes_consumed": 1,
        },
        reason_codes=["OVERPROVISIONED_AUTOSCALE"],
        recommendation={},
    )
    assert "under_provisioned" in labels
    assert "over_provisioned" not in labels


def test_dedupe_counts_collapsed_duplicates():
    """Repeat patterns must be counted, not silently dropped."""
    hits = [
        RetrievalHit(id="a", text="t", score=0.9, metadata={"action_signature": "s1", "job_id": "j1"}),
        RetrievalHit(id="b", text="t", score=0.8, metadata={"action_signature": "s1", "job_id": "j2"}),
        RetrievalHit(id="c", text="t", score=0.7, metadata={"action_signature": "s1", "job_id": "j3"}),
    ]
    out = dedupe_retrieval_hits(hits)
    assert len(out) == 1
    assert out[0].metadata["occurrences"] == 3
    assert out[0].metadata["also_job_ids"] == ["j2", "j3"]


def test_dedupe_by_id_and_action_signature():
    hits = [
        RetrievalHit(id="a", text="reduced max_workers", score=0.9, metadata={"action_signature": "max_workers:reduced"}),
        RetrievalHit(id="a", text="reduced max_workers again", score=0.5, metadata={"action_signature": "max_workers:reduced"}),
        RetrievalHit(id="b", text="also reduced", score=0.8, metadata={"action_signature": "max_workers:reduced"}),
        RetrievalHit(id="c", text="increased max_workers", score=0.7, metadata={"action_signature": "max_workers:increased"}),
    ]
    out = dedupe_retrieval_hits(hits)
    assert [h.id for h in out] == ["a", "c"]
    assert out[0].score == 0.9


def test_content_hash_stable():
    assert content_hash("Hello  World") == content_hash("hello world")


def test_compose_prefers_experience_block():
    register_cluster_tuning_experience_transform()
    set_retrieval_provider(MemoryRetrieval())
    set_recommendation_store(MemoryRecommendationStore())
    get_recommendation_store().save(
        RecommendationRecord(
            recommendation_id="rec-comp-1",
            job_id="other-job",
            status="applied",
            response={
                "job_cluster_metrics": {
                    "azure_worker_vm_size": "Standard_D8s_v5",
                    "max_worker_nodes_provisioned": 16,
                    "peak_worker_cpu_utilization_pct": 20,
                    "peak_worker_memory_utilization_pct": 30,
                    "avg_worker_nodes_consumed": 2,
                },
                "recommendation": {
                    "recommended_node_type": "Standard_D4s_v5",
                    "recommended_max_workers": 4,
                },
                "reason_codes": ["OVERPROVISIONED_AUTOSCALE"],
            },
        )
    )
    text = compose_historical_context(
        {
            "job_id": "current-job",
            "metrics": {
                "azure_worker_vm_size": "Standard_D8s_v5",
                "max_worker_nodes_provisioned": 14,
                "peak_worker_cpu_utilization_pct": 22,
                "peak_worker_memory_utilization_pct": 28,
                "avg_worker_nodes_consumed": 3,
            },
        }
    )
    assert "Similar past experiences" in text
    assert "over_provisioned" in text
    # Heuristic similar shelf suppressed when experience hits exist
    assert "similar_heuristic=" not in text or "similar_heuristic=0" in text


def test_build_experience_query_mentions_situation():
    q = build_experience_query(
        {
            "metrics": {
                "azure_worker_vm_size": "Standard_D8s_v5",
                "peak_worker_cpu_utilization_pct": 15,
                "peak_worker_memory_utilization_pct": 20,
            }
        }
    )
    assert "over_provisioned" in q
    assert "Standard_D8s_v5" in q


def test_register_transform_idempotent():
    register_experience_transform(ClusterTuningExperienceTransform())
    register_cluster_tuning_experience_transform()
    assert get_experience_transform("cluster_tuning") is not None
