"""Cluster-tuning ExperienceTransform — situation/action cards for outcomes corpus.

Turns a RecommendationRecord into searchable text focused on *features*
(over/under provisioned, OOM, SKU moves) rather than job_id. job_id stays in
metadata for entity/chat lookup filters.
"""

from __future__ import annotations

import re
from typing import Any

from edim_dde_ai.experiences.models import ExperienceDocument
from edim_dde_ai.recommendations.models import RecommendationRecord

CORPUS = "cluster-tuning-outcomes"
AGENT_ID = "cluster_tuning"

_OOM = re.compile(r"\boom\b|out[\s_]?of[\s_]?memory|memory.?bound", re.I)
_OVER = re.compile(
    r"over.?provision|underutil|OVERPROVISIONED|UNDERUTILIZED|PER_NODE_UNDERUTILIZED",
    re.I,
)
# NOTE: PERFORMANCE_DEGRADATION_RISK describes a risk of the *proposed change*,
# not the observed cluster state — it must not imply under-provisioning.
_UNDER = re.compile(
    r"under.?provision|capacity.?short|cpu.?bound|scale.?up|THROTTL",
    re.I,
)


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _reason_codes(record: RecommendationRecord) -> list[str]:
    response = record.response if isinstance(record.response, dict) else {}
    rec = _recommendation_blob(record)
    raw = response.get("reason_codes") or rec.get("reason_codes") or []
    if not isinstance(raw, list):
        return []
    return [str(c) for c in raw if str(c).strip()]


def infer_situation_labels(
    *,
    metrics: dict[str, Any],
    reason_codes: list[str],
    recommendation: dict[str, Any] | None = None,
) -> list[str]:
    """Map metrics + reason codes → coarse situation labels for indexing/query."""
    labels: list[str] = []
    joined = " ".join(reason_codes)
    peak_cpu = _as_float(metrics.get("peak_worker_cpu_utilization_pct"))
    peak_mem = _as_float(metrics.get("peak_worker_memory_utilization_pct"))
    max_w = _as_float(metrics.get("max_worker_nodes_provisioned"))
    avg_w = _as_float(metrics.get("avg_worker_nodes_consumed"))

    if _OOM.search(joined) or (peak_mem is not None and peak_mem >= 90):
        labels.append("oom_or_memory_pressure")

    over = bool(_OVER.search(joined)) or (
        peak_cpu is not None and peak_cpu < 40 and (peak_mem is None or peak_mem < 60)
    )
    if (
        max_w is not None
        and avg_w is not None
        and max_w >= 4
        and avg_w < max_w * 0.4
    ):
        over = True
    under = bool(_UNDER.search(joined)) or (peak_cpu is not None and peak_cpu >= 85)

    # Observed state cannot be both; live utilization decides when signals conflict.
    if over and under:
        if peak_cpu is not None and peak_cpu >= 85:
            over = False
        elif peak_cpu is not None and peak_cpu < 40:
            under = False
        else:
            under = False
    if over:
        labels.append("over_provisioned")
    if under:
        labels.append("under_provisioned")

    rec = recommendation or {}
    cur_sku = str(metrics.get("azure_worker_vm_size") or "").strip()
    new_sku = str(
        rec.get("recommended_node_type")
        or rec.get("azure_worker_vm_size")
        or ""
    ).strip()
    if cur_sku and new_sku and cur_sku.lower() != new_sku.lower():
        labels.append("sku_change")
        if re.search(r"_E\d", new_sku, re.I) and not re.search(r"_E\d", cur_sku, re.I):
            labels.append("moved_to_memory_sku")
        if re.search(r"ads|ds_v", new_sku, re.I):
            labels.append("moved_to_ds_or_ads")

    if not labels:
        labels.append("general_rightsizing")
    # stable unique order
    seen: set[str] = set()
    out: list[str] = []
    for lab in labels:
        if lab not in seen:
            seen.add(lab)
            out.append(lab)
    return out


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
        sig_bits.append(f"sku:{cur_sku.lower()}->{new_sku.lower()}")
    elif new_sku:
        lines.append(f"recommended sku {new_sku}")
        sig_bits.append(f"sku:{new_sku.lower()}")

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
    situation_labels: list[str],
    metrics: dict[str, Any],
    recommendation: dict[str, Any],
    reason_codes: list[str],
    status: str,
) -> tuple[str, str]:
    """Return (index_text, action_signature)."""
    action_lines, action_sig = _action_parts(metrics, recommendation)
    sku = str(metrics.get("azure_worker_vm_size") or "").strip() or "unknown"
    parts = [
        f"Situation: {', '.join(situation_labels)}",
        (
            f"Signals: sku={sku} "
            f"max_workers={metrics.get('max_worker_nodes_provisioned')} "
            f"peak_cpu_pct={metrics.get('peak_worker_cpu_utilization_pct')} "
            f"peak_memory_pct={metrics.get('peak_worker_memory_utilization_pct')} "
            f"avg_workers={metrics.get('avg_worker_nodes_consumed')} "
            f"p99_workers={metrics.get('p99_worker_nodes_consumed')}"
        ),
        f"Reason codes: {', '.join(reason_codes) if reason_codes else 'none'}",
        "Action: " + "; ".join(action_lines),
        f"Outcome: {status}",
    ]
    return "\n".join(parts), action_sig


def build_experience_query(state: dict[str, Any]) -> str:
    """Free-text query for the outcomes corpus from the live job metrics."""
    metrics = state.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    labels = infer_situation_labels(metrics=metrics, reason_codes=[], recommendation={})
    sku = str(metrics.get("azure_worker_vm_size") or "").strip()
    parts = [
        "databricks cluster tuning past outcome",
        " ".join(labels),
        f"sku={sku}" if sku else "",
        f"max_workers={metrics.get('max_worker_nodes_provisioned')}",
        f"peak_cpu_pct={metrics.get('peak_worker_cpu_utilization_pct')}",
        f"peak_memory_pct={metrics.get('peak_worker_memory_utilization_pct')}",
        "what actions were taken",
    ]
    return " ".join(str(p) for p in parts if p not in ("", None)).strip()


class ClusterTuningExperienceTransform:
    """Domain Strategy: RecommendationRecord → ExperienceDocument."""

    @property
    def agent_id(self) -> str:
        return AGENT_ID

    @property
    def corpus(self) -> str:
        return CORPUS

    def transform(self, record: RecommendationRecord) -> ExperienceDocument | None:
        metrics = _metrics_from_record(record)
        recommendation = _recommendation_blob(record)
        reasons = _reason_codes(record)
        labels = infer_situation_labels(
            metrics=metrics, reason_codes=reasons, recommendation=recommendation
        )
        text, action_sig = build_experience_text(
            situation_labels=labels,
            metrics=metrics,
            recommendation=recommendation,
            reason_codes=reasons,
            status=str(record.status or "proposed"),
        )
        return ExperienceDocument(
            doc_id=str(record.recommendation_id),
            corpus=CORPUS,
            text=text,
            situation_labels=labels,
            action_signature=action_sig,
            metadata={
                "agent_id": AGENT_ID,
                "job_id": record.job_id,
                "cluster_id": record.cluster_id,
                "recommendation_id": record.recommendation_id,
                "status": record.status,
                "situation_labels": labels,
                "action_signature": action_sig,
            },
            source=f"recommendation:{record.recommendation_id}",
        )


def register_cluster_tuning_experience_transform() -> None:
    from edim_dde_ai.experiences import register_experience_transform

    register_experience_transform(ClusterTuningExperienceTransform())
