"""Quality corpus offline gate (Phase 2a)."""

from __future__ import annotations

from edim_dde_domain.evaluation.cluster_tuning import register_cluster_tuning_evaluator
from edim_dde_domain.evaluation.corpus import load_quality_corpus
from edim_dde_domain.evaluation.harness import run_harness, score_corpus_offline
from edim_dde_domain.evaluation.spark_rca import register_spark_rca_evaluator


def setup_module():
    register_cluster_tuning_evaluator()
    register_spark_rca_evaluator()


def test_load_v1_corpus_has_both_agents():
    corpus = load_quality_corpus(version="v1")
    assert corpus.version == "v1"
    agents = {c.agent_id for c in corpus.cases}
    assert agents == {"cluster_tuning", "spark_rca"}
    assert len(corpus.cases) >= 4


def test_v1_corpus_offline_scores_pass():
    corpus = load_quality_corpus(version="v1")
    rows = score_corpus_offline(corpus)
    assert rows
    failures = [
        f"{r.case_id}: error={r.error} exp={r.expectation_failures} score={r.score}"
        for r in rows
        if r.error or r.expectation_failures or not r.passed
    ]
    assert not failures, failures


def test_harness_offline_report_shape(tmp_path):
    corpus = load_quality_corpus(version="v1")
    report = run_harness(corpus, trials=2, live=False, bootstrap=False)
    assert report.trials == 2
    assert set(report.agents) == {"cluster_tuning", "spark_rca"}
    assert len(report.results) == len(corpus.cases) * 2
    payload = report.to_dict()
    assert "summary" in payload
    assert payload["summary"]["cases"]
    out = tmp_path / "report.json"
    out.write_text(__import__("json").dumps(payload), encoding="utf-8")
    assert out.is_file()
