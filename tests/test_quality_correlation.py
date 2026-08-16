"""Quality Phase 2c outcome correlation tests."""

from __future__ import annotations

from edim_dde_ai.recommendations.models import RecommendationRecord
from edim_dde_domain.evaluation.correlation import (
    correlate_recommendation_outcomes,
    merge_outcome_extra,
    quality_snapshot,
)


def _rec(
    *,
    rid: str,
    status: str,
    score: float | None,
    label: str | None = None,
    extra: dict | None = None,
) -> RecommendationRecord:
    quality = {}
    if score is not None:
        quality = {
            "evaluator": "spark_rca.quality",
            "score": score,
            "confidence": 0.8,
            "passed": score >= 0.75,
            "quality_label": label
            or ("high" if score >= 0.85 else "medium" if score >= 0.75 else "low"),
            "dimensions": {"contract": 1.0},
        }
    return RecommendationRecord(
        recommendation_id=rid,
        agent_id="spark_rca",
        status=status,
        response={"quality": quality} if quality else {},
        extra=extra or {},
    )


def test_quality_snapshot_and_correlation():
    rows = [
        _rec(rid="1", status="accepted", score=0.95, label="high"),
        _rec(rid="2", status="applied", score=0.9, label="high"),
        _rec(rid="3", status="rejected", score=0.7, label="low"),
        _rec(rid="4", status="proposed", score=None),
    ]
    snap = quality_snapshot(rows[0])
    assert snap is not None
    assert snap.score == 0.95
    assert snap.quality_label == "high"

    report = correlate_recommendation_outcomes(rows, agent_id="spark_rca")
    assert report.total_records == 4
    assert report.with_quality == 3
    assert report.without_quality == 1
    assert report.acceptance_by_band["high"]["acceptance_rate"] == 1.0
    assert report.acceptance_by_band["low"]["rejected"] == 1


def test_merge_outcome_extra_scaffolds_labels():
    extra = merge_outcome_extra(
        {},
        human_label="correct_root_cause",
        labeled_by="alice",
        rerun_success=True,
        rerun_job_run_id="jr-9",
    )
    outcome = extra["outcome"]
    assert outcome["human_label"] == "correct_root_cause"
    assert outcome["labeled_by"] == "alice"
    assert outcome["rerun_success"] is True
    assert outcome["rerun_job_run_id"] == "jr-9"
    assert "labeled_at" in outcome
    assert "measured_at" in outcome
