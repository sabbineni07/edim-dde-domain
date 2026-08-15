from __future__ import annotations

from edim_dde_domain.evaluation.spark_rca import SparkRcaQualityEvaluator


def _pack() -> dict:
    return {
        "raw_anchors": {
            "failure_reason": "AnalysisException: table customer_orders not found"
        },
        "sections": {
            "logs": {"top_exceptions": ["AnalysisException"]},
            "stage_metrics": {},
            "sql_plans": {"sql_errors": ["table not found"]},
        },
        "evidence": [
            {
                "ref": "logs:error:1",
                "source": "logs",
                "excerpt": "AnalysisException: table customer_orders not found",
            }
        ],
    }


def _good_output() -> dict:
    return {
        "root_cause": {
            "category": "sql_error",
            "summary": "The query failed because customer_orders could not be resolved.",
            "failure_signature": "AnalysisException:table_not_found",
            "confidence": 0.9,
        },
        "recommended_actions": [
            "Verify the catalog and schema qualification for customer_orders.",
            "Confirm the executing principal can resolve the target table.",
        ],
        "recommendations": {
            "code_query_rewrites": ["Fully qualify the table identifier."],
            "spark_delta_configs": [],
            "infrastructure": [],
        },
        "evidence_analysis": {
            "log_signals": "AnalysisException and table not found",
            "metric_anomalies": "No stage metrics were available.",
            "physical_plan_bottlenecks": "The query did not reach execution.",
        },
        "evidence": [{"ref": "logs:error:1", "source": "logs"}],
        "classification_hint": {"category": "sql_error", "confidence": 0.75},
        "context_assessment": {
            "runbooks": "not used",
            "history": "not used",
            "web": "not used",
            "web_citations": [],
        },
    }


def test_spark_rca_quality_passes_grounded_actionable_result():
    result = SparkRcaQualityEvaluator().evaluate(
        inputs={"evidence_pack": _pack()},
        output=_good_output(),
    )
    assert result.passed
    assert result.score >= 0.75
    assert result.confidence < 1.0  # missing stage metrics reduces confidence
    assert result.metadata["model_confidence"] == 0.9


def test_spark_rca_quality_rejects_invalid_refs_and_generic_fix():
    output = _good_output()
    output["evidence"] = [{"ref": "invented:ref"}]
    output["recommended_actions"] = ["Check logs"]
    output["recommendations"] = {
        "code_query_rewrites": [],
        "spark_delta_configs": [],
        "infrastructure": [],
    }
    result = SparkRcaQualityEvaluator().evaluate(
        inputs={"evidence_pack": _pack()},
        output=output,
    )
    assert not result.passed
    assert result.dimensions["evidence"] < 1
    assert result.dimensions["actions"] < 1


def test_spark_rca_quality_rejects_unsupplied_web_citation():
    output = _good_output()
    output["web_search_hits"] = [
        {"url": "https://docs.databricks.com/valid"}
    ]
    output["context_assessment"]["web"] = "corroborated by external documentation"
    output["context_assessment"]["web_citations"] = [
        "https://malicious.example/invented"
    ]
    result = SparkRcaQualityEvaluator().evaluate(
        inputs={"evidence_pack": _pack()},
        output=output,
        context={"web_search_context": "external context"},
    )
    assert result.dimensions["safety"] < 1
