"""Output guardrails: validate and clamp LLM sizing JSON."""

from __future__ import annotations

import logging
from typing import Any, Optional

from edim_dde_domain.agents.cluster_tuning.sizing_policy import recommended_min_max_workers
from edim_dde_domain.agents.cluster_tuning.sku_allowlist import nearest_allowed_node_type

logger = logging.getLogger(__name__)

VALID_NODE_FAMILIES = ("D", "E", "F", "L")
VCPUS_MIN, VCPUS_MAX = 4, 64
MIN_WORKERS_MIN, MIN_WORKERS_MAX = 0, 32
MAX_WORKERS_MIN, MAX_WORKERS_MAX = 1, 64
RATIONALE_MAX_LENGTH = 2000
DEFAULT_AUTO_TERMINATION_MINUTES = 0


def _record_adjustment(
    adjustments: list[dict[str, Any]],
    *,
    field: str,
    llm_value: Any,
    applied_value: Any,
    reason: str,
) -> None:
    if llm_value == applied_value:
        return
    adjustments.append(
        {
            "field": field,
            "llm_value": llm_value,
            "applied_value": applied_value,
            "reason": reason,
        }
    )


def _default_recommendation(reason: str) -> dict[str, Any]:
    return {
        "node_family": "E",
        "vcpus": 8,
        "min_workers": 1,
        "max_workers": 8,
        "auto_termination_minutes": DEFAULT_AUTO_TERMINATION_MINUTES,
        "azure_node_type": "Standard_E8s_v5",
        "rationale": f"Conservative fallback: {reason}",
    }


def validate_and_clamp_with_adjustments(
    rec: dict[str, Any],
    job_run_ingest: Optional[dict[str, Any]] = None,
    *,
    auto_termination_minutes: int = DEFAULT_AUTO_TERMINATION_MINUTES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Clamp recommendation and return (applied_config, guardrail_adjustments)."""
    if not rec or not isinstance(rec, dict):
        out = _default_recommendation("Missing or invalid recommendation object")
        return out, [
            {
                "field": "_recommendation",
                "llm_value": rec,
                "applied_value": "default",
                "reason": "invalid_recommendation_object",
            }
        ]

    adjustments: list[dict[str, Any]] = []
    out: dict[str, Any] = dict(rec)

    family = rec.get("node_family")
    if family is None or str(family).strip().upper() not in VALID_NODE_FAMILIES:
        applied_family = "E"
        out["node_family"] = applied_family
        _record_adjustment(
            adjustments,
            field="node_family",
            llm_value=family,
            applied_value=applied_family,
            reason="invalid_node_family",
        )
    else:
        out["node_family"] = str(family).strip().upper()

    try:
        v = int(rec.get("vcpus", 8))
        clamped = max(VCPUS_MIN, min(VCPUS_MAX, v))
        out["vcpus"] = clamped
        if clamped != v:
            _record_adjustment(
                adjustments,
                field="vcpus",
                llm_value=v,
                applied_value=clamped,
                reason="vcpus_out_of_range",
            )
    except (TypeError, ValueError):
        out["vcpus"] = 8
        _record_adjustment(
            adjustments,
            field="vcpus",
            llm_value=rec.get("vcpus"),
            applied_value=8,
            reason="vcpus_out_of_range",
        )

    try:
        v = int(rec.get("min_workers", 0))
        clamped = max(MIN_WORKERS_MIN, min(MIN_WORKERS_MAX, v))
        out["min_workers"] = clamped
        if clamped != v:
            _record_adjustment(
                adjustments,
                field="min_workers",
                llm_value=v,
                applied_value=clamped,
                reason="min_workers_out_of_range",
            )
    except (TypeError, ValueError):
        out["min_workers"] = 0

    llm_max_raw = rec.get("max_workers")
    try:
        v = int(rec.get("max_workers", 8))
        clamped = max(MAX_WORKERS_MIN, min(MAX_WORKERS_MAX, v))
        out["max_workers"] = clamped
        if clamped != v:
            _record_adjustment(
                adjustments,
                field="max_workers",
                llm_value=v,
                applied_value=clamped,
                reason="max_workers_out_of_range",
            )
    except (TypeError, ValueError):
        out["max_workers"] = 8
        _record_adjustment(
            adjustments,
            field="max_workers",
            llm_value=llm_max_raw,
            applied_value=8,
            reason="max_workers_out_of_range",
        )

    if out["min_workers"] > out["max_workers"]:
        prev_min = out["min_workers"]
        out["min_workers"] = out["max_workers"]
        _record_adjustment(
            adjustments,
            field="min_workers",
            llm_value=prev_min,
            applied_value=out["min_workers"],
            reason="min_workers_above_max_workers",
        )

    llm_max_before_floor = out["max_workers"]
    if job_run_ingest:
        _, floor_max = recommended_min_max_workers(job_run_ingest)
        ceiling_max = int(
            job_run_ingest.get("max_worker_nodes_provisioned")
            or job_run_ingest.get("max_worker_nodes_cluster_ceiling")
            or floor_max
        )
        if out["max_workers"] < floor_max:
            applied = min(floor_max, MAX_WORKERS_MAX)
            _record_adjustment(
                adjustments,
                field="max_workers",
                llm_value=llm_max_before_floor,
                applied_value=applied,
                reason="sizing_floor",
            )
            out["max_workers"] = applied
        elif out["max_workers"] > ceiling_max and ceiling_max > 0:
            applied = min(ceiling_max, MAX_WORKERS_MAX)
            _record_adjustment(
                adjustments,
                field="max_workers",
                llm_value=llm_max_before_floor,
                applied_value=applied,
                reason="sizing_ceiling",
            )
            out["max_workers"] = applied

        sku_before = out.get("azure_node_type") or out.get("recommended_node_type")
        current_type = job_run_ingest.get("azure_worker_vm_size")
        mapped = nearest_allowed_node_type(
            out["node_family"],
            out["vcpus"],
            current_node_type=str(current_type) if current_type else None,
        )
        out["azure_node_type"] = mapped
        if sku_before != mapped:
            _record_adjustment(
                adjustments,
                field="azure_node_type",
                llm_value=sku_before,
                applied_value=mapped,
                reason="sku_mapped",
            )
    else:
        out["azure_node_type"] = nearest_allowed_node_type(
            out["node_family"], out["vcpus"]
        )

    llm_atm = rec.get("auto_termination_minutes")
    if llm_atm != auto_termination_minutes:
        _record_adjustment(
            adjustments,
            field="auto_termination_minutes",
            llm_value=llm_atm,
            applied_value=auto_termination_minutes,
            reason="auto_termination_policy",
        )
    out["auto_termination_minutes"] = auto_termination_minutes

    rationale = rec.get("rationale", "")
    if isinstance(rationale, str) and len(rationale) > RATIONALE_MAX_LENGTH:
        out["rationale"] = rationale[: RATIONALE_MAX_LENGTH - 3] + "..."
    else:
        out["rationale"] = str(rationale) if rationale is not None else "No rationale provided."

    applied_note = (
        f"Applied autoscale (authoritative): min_workers={out['min_workers']}, "
        f"max_workers={out['max_workers']}, "
        f"auto_termination_minutes={out['auto_termination_minutes']}."
    )
    if applied_note not in out["rationale"]:
        out["rationale"] = f"{out['rationale'].rstrip()} {applied_note}".strip()

    return out, adjustments
