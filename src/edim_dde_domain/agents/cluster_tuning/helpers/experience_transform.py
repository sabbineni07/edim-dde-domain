"""Cluster-tuning ExperienceTransform — pressure/action cards for outcomes corpus.

Cards describe observed resource dimensions and action direction. They never
infer failure events from utilization and do not depend on a fixed scenario list.
``job_id`` remains metadata for entity/chat lookup filters.
"""

from __future__ import annotations

from typing import Any

from edim_dde_ai.experiences.models import ExperienceDocument
from edim_dde_ai.recommendations.models import RecommendationRecord
from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import (
    compute_resource_pressure,
    parse_family_from_node_type,
)

CORPUS = "cluster-tuning-outcomes"
AGENT_ID = "cluster_tuning"

def _metrics_from_record(record: RecommendationRecord) -> dict[str, Any]:
    response = record.response if isinstance(record.response, dict) else {}
    request = record.request if isinstance(record.request, dict) else {}
    for blob in (
        response.get("job_cluster_metrics"),
        request.get("metrics"),
        response.get("current_configuration"),
    ):
        if isinstance(blob, dict) and blob:
            return blob
    return {}


def _recommendation_blob(record: RecommendationRecord) -> dict[str, Any]:
    response = record.response if isinstance(record.response, dict) else {}
    rec = response.get("recommendation") or {}
    return rec if isinstance(rec, dict) else {}


def infer_feature_labels(
    *,
    metrics: dict[str, Any],
    resource_pressure: dict[str, Any] | None = None,
    resource_pressure_config: dict[str, Any] | None = None,
) -> list[str]:
    """Generate labels from configured dimensions, without scenario vocabulary."""
    pressure = (
        resource_pressure
        if isinstance(resource_pressure, dict) and resource_pressure.get("dimensions")
        else compute_resource_pressure(metrics, config=resource_pressure_config)
    )
    labels: list[str] = []
    for name, details in (pressure.get("dimensions") or {}).items():
        level = str((details or {}).get("level") or "unknown")
        if level != "unknown":
            labels.append(f"{name}_pressure_{level}")
    limiting = str(pressure.get("limiting_resource") or "unknown")
    if limiting not in {"none", "unknown"}:
        labels.append(f"limiting_resource_{limiting}")
        current_family = parse_family_from_node_type(
            str(metrics.get("azure_worker_vm_size") or "")
        )
        preferred = [str(f).upper() for f in pressure.get("preferred_families") or []]
        if current_family and preferred and current_family not in preferred:
            labels.append("resource_shape_mismatch")
    headroom = str(pressure.get("capacity_headroom") or "unknown")
    if headroom != "unknown":
        labels.append(f"capacity_headroom_{headroom}")
    if not labels:
        labels.append("resource_pressure_unknown")
    return list(dict.fromkeys(labels))


def _action_parts(
    metrics: dict[str, Any], recommendation: dict[str, Any]
) -> tuple[list[str], str]:
    """Human action lines + compact signature for de-dupe."""
    lines: list[str] = []
    sig_bits: list[str] = []

    cur_sku = str(metrics.get("azure_worker_vm_size") or "").strip()
    new_sku = str(
        recommendation.get("recommended_node_type")
        or recommendation.get("azure_worker_vm_size")
        or ""
    ).strip()
    if new_sku and cur_sku and new_sku.lower() != cur_sku.lower():
        lines.append(f"changed sku {cur_sku} → {new_sku}")
        sig_bits.append("sku:changed")
        current_family = parse_family_from_node_type(cur_sku)
        new_family = parse_family_from_node_type(new_sku)
        sig_bits.append(
            "family:changed"
            if current_family and new_family and current_family != new_family
            else "family:retained"
        )
    elif new_sku:
        lines.append(f"recommended sku {new_sku}")
        sig_bits.append("sku:recommended")

    cur_max = metrics.get("max_worker_nodes_provisioned")
    new_max = recommendation.get("recommended_max_workers") or recommendation.get(
        "max_workers"
    )
    if new_max is not None and cur_max is not None:
        try:
            if int(new_max) != int(cur_max):
                direction = "reduced" if int(new_max) < int(cur_max) else "increased"
                lines.append(f"{direction} max_workers {cur_max} → {new_max}")
                sig_bits.append(f"max_workers:{direction}")
        except (TypeError, ValueError):
            pass
    elif new_max is not None:
        lines.append(f"recommended max_workers={new_max}")
        sig_bits.append(f"max_workers:{new_max}")

    new_min = recommendation.get("min_workers")
    if new_min is not None:
        lines.append(f"min_workers={new_min}")

    fam = str(recommendation.get("node_family") or "").strip()
    if fam:
        lines.append(f"node_family={fam}")
        sig_bits.append(f"family:{fam.lower()}")

    if not lines:
        lines.append("no material config change recorded")
        sig_bits.append("noop")

    return lines, "|".join(sig_bits)


def build_experience_text(
    *,
    feature_labels: list[str],
    metrics: dict[str, Any],
    recommendation: dict[str, Any],
    resource_pressure: dict[str, Any],
    status: str,
) -> tuple[str, str]:
    """Return (index_text, action_signature)."""
    action_lines, action_sig = _action_parts(metrics, recommendation)
    sku = str(metrics.get("azure_worker_vm_size") or "").strip() or "unknown"
    pressure_signals = " ".join(
        f"{name}={details.get('value_pct')}%({details.get('level')})"
        for name, details in (resource_pressure.get("dimensions") or {}).items()
    )
    parts = [
        f"Resource features: {', '.join(feature_labels)}",
        f"Signals: sku={sku} {pressure_signals}".strip(),
        "Action: " + "; ".join(action_lines),
        f"Outcome: {status}",
    ]
    return "\n".join(parts), action_sig


def build_experience_query(
    state: dict[str, Any],
    *,
    resource_pressure_config: dict[str, Any] | None = None,
) -> str:
    """Free-text query for the outcomes corpus from the live job metrics."""
    metrics = state.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    pressure = compute_resource_pressure(metrics, config=resource_pressure_config)
    labels = infer_feature_labels(metrics=metrics, resource_pressure=pressure)
    sku = str(metrics.get("azure_worker_vm_size") or "").strip()
    parts = [
        "databricks cluster tuning past outcome",
        " ".join(labels),
        f"sku={sku}" if sku else "",
        f"limiting_resource={pressure.get('limiting_resource')}",
        f"capacity_headroom={pressure.get('capacity_headroom')}",
        "what actions were taken",
    ]
    return " ".join(str(p) for p in parts if p not in ("", None)).strip()


class ClusterTuningExperienceTransform:
    """Domain Strategy: RecommendationRecord → ExperienceDocument."""

    def __init__(
        self, resource_pressure_config: dict[str, Any] | None = None
    ) -> None:
        self._resource_pressure_config = dict(resource_pressure_config or {})

    @property
    def agent_id(self) -> str:
        return AGENT_ID

    @property
    def corpus(self) -> str:
        return CORPUS

    def transform(self, record: RecommendationRecord) -> ExperienceDocument | None:
        metrics = _metrics_from_record(record)
        recommendation = _recommendation_blob(record)
        pressure = recommendation.get("resource_pressure")
        if not isinstance(pressure, dict) or not pressure.get("dimensions"):
            pressure = compute_resource_pressure(
                metrics, config=self._resource_pressure_config
            )
        labels = infer_feature_labels(
            metrics=metrics,
            resource_pressure=pressure,
        )
        text, action_sig = build_experience_text(
            feature_labels=labels,
            metrics=metrics,
            recommendation=recommendation,
            resource_pressure=pressure,
            status=str(record.status or "proposed"),
        )
        return ExperienceDocument(
            doc_id=str(record.recommendation_id),
            corpus=CORPUS,
            text=text,
            feature_labels=labels,
            action_signature=action_sig,
            metadata={
                "agent_id": AGENT_ID,
                "job_id": record.job_id,
                "cluster_id": record.cluster_id,
                "recommendation_id": record.recommendation_id,
                "status": record.status,
                "feature_labels": labels,
                "action_signature": action_sig,
            },
            source=f"recommendation:{record.recommendation_id}",
        )


def register_cluster_tuning_experience_transform(
    resource_pressure_config: dict[str, Any] | None = None,
) -> None:
    from edim_dde_ai.experiences import register_experience_transform

    register_experience_transform(
        ClusterTuningExperienceTransform(resource_pressure_config)
    )
