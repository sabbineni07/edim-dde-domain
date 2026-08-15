from __future__ import annotations

from edim_dde_ai.recommendations import (
    MemoryRecommendationStore,
    RecommendationRecord,
    get_recommendation_store,
    set_recommendation_store,
)
from edim_dde_ai.retrieval import MemoryRetrieval, set_retrieval_provider
from edim_dde_ai.retrieval import search_corpus
from edim_dde_domain.agents.spark_rca.helpers.experience_transform import (
    SparkRcaExperienceTransform,
    infer_failure_features,
    register_spark_rca_experience_transform,
)
from edim_dde_domain.agents.spark_rca.helpers.historical_context import (
    compose_historical_context,
)
from edim_dde_domain.agents.spark_rca.logic import build_web_search_query


def _pack(run_id: str = "jr-1") -> dict:
    return {
        "job_run_id": run_id,
        "raw_anchors": {
            "failure_reason": "ExecutorLostFailure caused by FetchFailedException"
        },
        "sections": {
            "logs": {"top_exceptions": ["FetchFailedException"]},
            "stage_metrics": {"stage_pressure_excerpts": ["shuffle fetch failed"]},
            "sql_plans": {},
        },
        "evidence": [
            {
                "ref": "metrics:stage:9",
                "source": "stage_metrics",
                "excerpt": "FetchFailedException during shuffle read",
            }
        ],
    }


def _record(rec_id: str, job_id: str, run_id: str) -> RecommendationRecord:
    return RecommendationRecord(
        recommendation_id=rec_id,
        agent_id="spark_rca",
        status="applied",
        job_id=job_id,
        job_run_id=run_id,
        response={
            "root_cause": {
                "category": "skew_shuffle",
                "summary": "Shuffle fetch failed after an executor was lost.",
                "failure_signature": "FetchFailedException",
            },
            "recommended_actions": [
                "Inspect executor loss and retry the failed shuffle stage."
            ],
            "classification_hint": {
                "category": "skew_shuffle",
                "confidence": 0.7,
            },
            "evidence_analysis": {
                "log_signals": "FetchFailedException",
                "metric_anomalies": "Failed shuffle stage",
                "physical_plan_bottlenecks": "",
            },
            "evidence_pack": _pack(run_id),
        },
    )


def test_rca_experience_features_are_open_vocabulary():
    labels = infer_failure_features(
        evidence_pack=_pack(),
        classification_hint={"category": "skew_shuffle"},
    )
    assert "hint_category_skew_shuffle" in labels
    assert any("fetchfailedexception" in label for label in labels)
    assert any(label.startswith("evidence_channel_") for label in labels)


def test_rca_transform_builds_diagnosis_action_card():
    doc = SparkRcaExperienceTransform().transform(
        _record("rec-1", "job-old", "jr-old")
    )
    assert doc is not None
    assert doc.corpus == "spark-rca-outcomes"
    assert "Diagnosis:" in doc.text
    assert "Actions:" in doc.text
    assert doc.metadata["job_run_id"] == "jr-old"


def test_rca_history_finds_similar_other_job_and_exact_job():
    register_spark_rca_experience_transform()
    set_retrieval_provider(MemoryRetrieval())
    set_recommendation_store(MemoryRecommendationStore())
    store = get_recommendation_store()
    store.save(_record("rec-similar", "job-other", "jr-other"))
    store.save(_record("rec-exact", "job-current", "jr-previous"))

    state = {
        "job_id": "job-current",
        "job_run_id": "jr-new",
        "evidence_pack": _pack("jr-new"),
        "classification_hint": {
            "category": "skew_shuffle",
            "confidence": 0.7,
        },
    }
    context = compose_historical_context(state, top_k=5, same_job_limit=3)
    assert "Similar past RCA outcomes" in context
    assert "Prior RCA records for this job/run" in context
    assert "job-other" in context
    assert "rec-exact" in context


def test_web_query_is_disabled_by_default_and_never_contains_ids_or_paths():
    state = {
        "job_id": "secret-job-123",
        "job_run_id": "secret-run-456",
        "evidence_pack": {
            **_pack(),
            "evidence": [
                {
                    "ref": "logs:1",
                    "source": "logs",
                    "excerpt": (
                        "NovelWidgetFailure at /mnt/private/customer.csv "
                        "for secret-job-123"
                    ),
                }
            ],
        },
        "classification_hint": {"category": "unknown", "confidence": 0.2},
    }
    assert build_web_search_query(state)["web_search_query"] == ""
    query = build_web_search_query(
        state,
        config={"enabled": True, "confidence_below": 0.55},
    )["web_search_query"]
    assert "secret-job-123" not in query
    assert "secret-run-456" not in query
    assert "/mnt/private" not in query
    assert "NovelWidgetFailure".lower() in query.lower()


def test_rca_history_filters_unrelated_tiny_corpus_hit():
    register_spark_rca_experience_transform()
    set_retrieval_provider(MemoryRetrieval())
    set_recommendation_store(MemoryRecommendationStore())
    get_recommendation_store().save(
        _record("rec-only-shuffle", "job-other", "jr-other")
    )
    context = compose_historical_context(
        {
            "job_id": "job-new",
            "job_run_id": "jr-new",
            "evidence_pack": {
                "raw_anchors": {
                    "failure_reason": "AnalysisException: table not found"
                },
                "evidence": [
                    {
                        "ref": "sql:1",
                        "source": "sql_plans",
                        "excerpt": "AnalysisException: table not found",
                    }
                ],
            },
            "classification_hint": {
                "category": "sql_error",
                "confidence": 0.75,
            },
        }
    )
    assert "rec-only-shuffle" not in context


def test_rca_proposed_is_not_cross_job_precedent_until_accepted():
    register_spark_rca_experience_transform()
    set_retrieval_provider(MemoryRetrieval())
    set_recommendation_store(MemoryRecommendationStore())
    record = _record("rec-review-gate", "job-a", "jr-a").with_status("proposed")
    store = get_recommendation_store()
    store.save(record)
    assert (
        search_corpus(
            "FetchFailedException", corpus="spark-rca-outcomes", top_k=5
        )
        == []
    )
    store.update_status("rec-review-gate", "accepted")
    assert search_corpus(
        "FetchFailedException", corpus="spark-rca-outcomes", top_k=5
    )
