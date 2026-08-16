"""Domain evaluators, golden corpus, and quality harness.

Business purpose
----------------
Re-exports agent quality rubrics registered at bootstrap into the
edim-dde-ai evaluator registry (``cluster_tuning.quality``,
``spark_rca.quality``), plus Quality Phase 2 corpus / harness helpers.

Public API
----------
* ``ClusterTuningQualityEvaluator`` / ``register_cluster_tuning_evaluator``
* ``SparkRcaQualityEvaluator`` / ``register_spark_rca_evaluator``
* ``load_quality_corpus`` / ``QualityCase`` / ``QualityCorpus``
* ``run_harness`` / ``score_corpus_offline``
"""

from edim_dde_domain.evaluation.cluster_tuning import (
    ClusterTuningQualityEvaluator,
    register_cluster_tuning_evaluator,
)
from edim_dde_domain.evaluation.corpus import (
    QualityCase,
    QualityCorpus,
    load_quality_corpus,
)
from edim_dde_domain.evaluation.correlation import (
    correlate_recommendation_outcomes,
    merge_outcome_extra,
    quality_snapshot,
)
from edim_dde_domain.evaluation.harness import (
    run_harness,
    score_corpus_offline,
)
from edim_dde_domain.evaluation.spark_rca import (
    SparkRcaQualityEvaluator,
    register_spark_rca_evaluator,
)

__all__ = [
    "ClusterTuningQualityEvaluator",
    "register_cluster_tuning_evaluator",
    "SparkRcaQualityEvaluator",
    "register_spark_rca_evaluator",
    "QualityCase",
    "QualityCorpus",
    "load_quality_corpus",
    "run_harness",
    "score_corpus_offline",
    "correlate_recommendation_outcomes",
    "merge_outcome_extra",
    "quality_snapshot",
]
