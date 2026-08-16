"""Domain evaluators and golden-case quality gates.

Business purpose
----------------
Re-exports agent quality rubrics registered at bootstrap into the
edim-dde-ai evaluator registry (``cluster_tuning.quality``,
``spark_rca.quality``).

Public API
----------
* ``ClusterTuningQualityEvaluator`` / ``register_cluster_tuning_evaluator``
* ``SparkRcaQualityEvaluator`` / ``register_spark_rca_evaluator``
"""

from edim_dde_domain.evaluation.cluster_tuning import (
    ClusterTuningQualityEvaluator,
    register_cluster_tuning_evaluator,
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
]
