"""Unit tests for spark_rca evidence ranking + classification + validate."""

from __future__ import annotations

from edim_dde_domain.agents.spark_rca.helpers.classify import classify_failure_pack
from edim_dde_domain.agents.spark_rca.helpers.evidence_pack import (
    build_evidence_pack,
    rank_stage_pressure,
)
from edim_dde_domain.agents.spark_rca.helpers.validate import validate_rca_llm_output
from edim_dde_domain.agents.spark_rca.logic import assemble_evidence, classify_failure


def test_rank_stage_pressure_prefers_failures():
    rows = [
        {
            "event_id": "ok-1",
            "event_type": "spark_stage_completed",
            "status": "SUCCESS",
            "successful": True,
            "attributes": "{}",
        },
        {
            "event_id": "fail-1",
            "event_type": "spark_stage_completed",
            "status": "FAILED",
            "successful": False,
            "attributes": '{"num_failed_tasks": 3}',
        },
        {
            "event_id": "ok-2",
            "event_type": "spark_stage_task_summary",
            "status": "SUCCESS",
            "attributes": '{"num_failed_tasks": 0}',
        },
    ]
    ranked = rank_stage_pressure(rows, limit=40)
    assert ranked[0]["event_id"] == "fail-1"
    assert len(ranked) == 3


def test_build_evidence_pack_surfaces_failed_stage_first():
    pack = build_evidence_pack(
        job_run_id="jr-1",
        stage_pressure=[
            {
                "event_id": "ok",
                "event_type": "spark_stage_completed",
                "event_ts": "2026-01-02T00:00:00",
                "status": "SUCCESS",
                "attributes": "{}",
            },
            {
                "event_id": "bad",
                "event_type": "spark_stage_completed",
                "event_ts": "2026-01-01T00:00:00",
                "status": "FAILED",
                "successful": False,
                "attributes": '{"num_failed_tasks": 5}',
            },
        ],
    )
    excerpts = pack["sections"]["stage_metrics"]["stage_pressure_excerpts"]
    assert excerpts
    assert "bad" in excerpts[0]["ref"]


def test_classify_resource_and_sql():
    oom = classify_failure_pack(
        {
            "raw_anchors": {"failure_reason": "Executor OutOfMemoryError: Java heap space"},
            "evidence": [{"excerpt": "Java heap space"}],
        },
        signal_groups=[
            {
                "category": "resource",
                "confidence": 0.7,
                "patterns": ["OutOfMemory|Java heap space"],
            }
        ],
    )
    assert oom["category"] == "resource"

    sql = classify_failure_pack(
        {
            "raw_anchors": {
                "failure_reason": "AnalysisException: Table not found",
                "sql_errors": [{"failure_reason": "table not found"}],
            },
            "evidence": [],
        }
    )
    assert sql["category"] == "sql_error"


def test_assemble_seeds_job_id_from_anchors():
    out = assemble_evidence(
        {
            "job_run_id": "jr-9",
            "failure_anchors": [
                {
                    "event_id": "1",
                    "event_type": "pipeline_end",
                    "job_id": "seeded-job",
                    "job_run_date": "2026-08-01",
                    "failure_reason": "boom",
                }
            ],
        }
    )
    assert out["job_id"] == "seeded-job"
    assert out["job_run_date"] == "2026-08-01"
    assert out["evidence_pack"]["job_id"] == "seeded-job"


def test_validate_preserves_rich_fields():
    pack = build_evidence_pack(
        job_run_id="jr-1",
        failure_anchors=[
            {
                "event_id": "1",
                "event_type": "pipeline_end",
                "failure_reason": "OOM",
            }
        ],
    )
    hint = classify_failure({"evidence_pack": pack})["classification_hint"]
    validated = validate_rca_llm_output(
        {
            "category": "resource",
            "confidence": 0.9,
            "confidence_label": "High",
            "summary": "Executor OOM",
            "failure_signature": "OutOfMemoryError",
            "recommended_actions": ["Increase executor memory"],
            "evidence_analysis": {
                "log_signals": "Java heap space",
                "metric_anomalies": "",
                "physical_plan_bottlenecks": "",
            },
            "contributing_factors": ["Large join"],
        },
        evidence_pack=pack,
        classification_hint=hint,
    )
    assert validated["root_cause"]["failure_signature"] == "OutOfMemoryError"
    assert validated["recommended_actions"][0].startswith("Increase")
    assert validated["evidence_analysis"]["log_signals"]


def _pack_with_refs() -> dict:
    """Minimal pack with two citable evidence rows."""
    return {
        "evidence": [
            {"ref": "e1", "source": "logs", "excerpt": "OOM here"},
            {"ref": "e2", "source": "metrics", "excerpt": "spill high"},
        ]
    }


def test_model_citations_are_authoritative_and_not_backfilled():
    validated = validate_rca_llm_output(
        {"summary": "OOM", "evidence_refs": ["e1"]},
        evidence_pack=_pack_with_refs(),
        classification_hint={"category": "resource", "confidence": 0.6},
    )
    assert validated["evidence_backfilled"] is False
    refs = [row["ref"] for row in validated["evidence"]]
    assert refs == ["e1"]
    assert all(row["backfilled"] is False for row in validated["evidence"])


def test_missing_citations_yield_labeled_preview_not_silent_fill():
    validated = validate_rca_llm_output(
        {"summary": "OOM", "evidence_refs": []},
        evidence_pack=_pack_with_refs(),
        classification_hint={"category": "resource", "confidence": 0.6},
    )
    # Preview rows exist for UX, but they are explicitly labeled.
    assert validated["evidence_backfilled"] is True
    assert validated["evidence"], "expected preview rows for UX"
    assert all(row["backfilled"] is True for row in validated["evidence"])


def test_backfilled_preview_does_not_count_as_model_citation_in_eval():
    from edim_dde_domain.evaluation.spark_rca import SparkRcaQualityEvaluator

    pack = _pack_with_refs()
    validated = validate_rca_llm_output(
        {"summary": "OOM", "evidence_refs": []},
        evidence_pack=pack,
        classification_hint={"category": "resource", "confidence": 0.6},
    )
    result = {**validated, "evidence_pack": pack}
    report = SparkRcaQualityEvaluator().evaluate(
        inputs={"evidence_pack": pack}, output=result
    )
    assert any("did not cite" in f for f in report.findings)
