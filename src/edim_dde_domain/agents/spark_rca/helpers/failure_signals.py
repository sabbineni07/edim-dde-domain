"""YAML-driven failure signal extractors for Spark RCA experience features.

Business purpose
----------------
Parallel to cluster_tuning ``resource_pressure``: measurable telemetry attributes
(failed tasks, spill bytes, shuffle bytes, plan operators, …) become
``signal_*`` feature labels via **YAML**, not per-scenario Python branches.

The engine is dimension-agnostic — add a new attr key + min + label in
``spark_rca.agent.yaml`` without changing this module.

Used by ``experience_transform.infer_failure_features`` for both indexing and
live experience queries.

Public API
----------
* ``DEFAULT_FAILURE_SIGNALS_CONFIG`` — packaged defaults
* ``normalize_failure_signals_config`` — deep-merge YAML override
* ``extract_yaml_signal_labels`` — labels from evidence_pack + config
* ``extract_plan_op_labels`` / ``extract_exception_class_labels`` — bounded
  open tokens still useful alongside YAML presence bits
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,80}")
_PLAN_OP_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Exec|Join|Scan))\b")
_EXCEPTION_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Failure|Timeout))\b"
)

DEFAULT_FAILURE_SIGNALS_CONFIG: dict[str, Any] = {
    "max_exception_labels": 3,
    "max_plan_ops": 5,
    "max_msg_tokens": 4,
    "include_hint_category_label": True,
    "signals": {
        "failed_tasks": {
            "attr_keys": ["num_failed_tasks", "numFailedTasks"],
            "min": 1,
            "label": "signal_failed_tasks",
        },
        "spill_bytes": {
            "attr_keys": [
                "memoryBytesSpilled",
                "memory_bytes_spilled",
                "diskBytesSpilled",
                "disk_bytes_spilled",
            ],
            "min": 1,
            "label": "signal_spill_bytes",
        },
        "shuffle_bytes": {
            "attr_keys": [
                "shuffle_read_bytes",
                "shuffleReadBytes",
                "shuffle_write_bytes",
                "shuffleWriteBytes",
            ],
            "min": 1,
            "label": "signal_shuffle_bytes",
        },
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
            and key != "signals"
        ):
            out[key] = _deep_merge(out[key], value)
        elif key == "signals" and isinstance(value, dict):
            merged = dict(out.get("signals") or {})
            for sig_name, sig_cfg in value.items():
                if isinstance(sig_cfg, dict) and isinstance(merged.get(sig_name), dict):
                    merged[sig_name] = {**merged[sig_name], **sig_cfg}
                else:
                    merged[sig_name] = sig_cfg
            out["signals"] = merged
        else:
            out[key] = value
    return out


def normalize_failure_signals_config(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge agent-YAML override onto packaged defaults.

    Args:
        config: Optional partial override (e.g. from
            ``load_historical_context.failure_signals``).

    Returns:
        Full policy dict with defaults filled for omitted keys.
    """
    return _deep_merge(DEFAULT_FAILURE_SIGNALS_CONFIG, dict(config or {}))


def _iter_attr_maps(evidence_pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect attribute dicts from anchors, stage sections, and evidence rows."""
    maps: list[dict[str, Any]] = []
    anchors = evidence_pack.get("raw_anchors") or {}
    for key in ("pipeline_end",):
        row = anchors.get(key)
        if isinstance(row, dict):
            attrs = row.get("attributes")
            if isinstance(attrs, dict):
                maps.append(attrs)
            maps.append(row)
    for err in anchors.get("sql_errors") or []:
        if isinstance(err, dict):
            attrs = err.get("attributes")
            if isinstance(attrs, dict):
                maps.append(attrs)
            maps.append(err)
    sections = evidence_pack.get("sections") or {}
    stage = sections.get("stage_metrics")
    if isinstance(stage, dict):
        for value in stage.values():
            if isinstance(value, dict):
                maps.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        attrs = item.get("attributes")
                        if isinstance(attrs, dict):
                            maps.append(attrs)
                        maps.append(item)
    for item in evidence_pack.get("evidence") or []:
        if isinstance(item, dict):
            attrs = item.get("attributes")
            if isinstance(attrs, dict):
                maps.append(attrs)
    return maps


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_yaml_signal_labels(
    evidence_pack: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """Emit configured presence/threshold labels from pack attributes.

    Args:
        evidence_pack: Live or stored evidence pack.
        config: Optional failure_signals YAML override.

    Returns:
        Labels such as ``signal_failed_tasks``, ``signal_spill_bytes``.

    Example:
        >>> extract_yaml_signal_labels(
        ...     {"raw_anchors": {"pipeline_end": {"attributes": {"num_failed_tasks": 3}}}},
        ... )
        ['signal_failed_tasks']
    """
    policy = normalize_failure_signals_config(config)
    attr_maps = _iter_attr_maps(evidence_pack)
    labels: list[str] = []
    for _name, raw in (policy.get("signals") or {}).items():
        if not isinstance(raw, dict):
            continue
        keys = [str(k) for k in (raw.get("attr_keys") or [])]
        minimum = _number(raw.get("min"))
        minimum = 1.0 if minimum is None else minimum
        label = str(raw.get("label") or "").strip()
        if not label or not keys:
            continue
        matched = False
        for attrs in attr_maps:
            for key in keys:
                value = _number(attrs.get(key))
                if value is not None and value >= minimum:
                    matched = True
                    break
            if matched:
                break
        if matched and label not in labels:
            labels.append(label)
    return labels


def extract_exception_class_labels(
    text: str, *, limit: int = 3
) -> list[str]:
    """Bounded ``exception_class_*`` labels from free text (open vocabulary)."""
    out: list[str] = []
    for match in _EXCEPTION_RE.findall(str(text or "")):
        token = match.strip("._-").lower()
        label = f"exception_class_{token}"
        if label not in out:
            out.append(label)
        if len(out) >= max(1, limit):
            break
    return out


def extract_plan_op_labels(text: str, *, limit: int = 5) -> list[str]:
    """Bounded ``plan_op_*`` labels from CamelCase plan operator tokens."""
    out: list[str] = []
    for match in _PLAN_OP_RE.findall(str(text or "")):
        token = match.lower()
        label = f"plan_op_{token}"
        if label not in out:
            out.append(label)
        if len(out) >= max(1, limit):
            break
    return out


def blob_for_structural_extract(evidence_pack: dict[str, Any]) -> str:
    """Join anchors + short excerpts for exception/plan regex extractors."""
    parts: list[str] = []
    anchors = evidence_pack.get("raw_anchors") or {}
    parts.append(str(anchors.get("failure_reason") or ""))
    pe = anchors.get("pipeline_end") or {}
    if isinstance(pe, dict):
        parts.append(str(pe.get("failure_reason") or ""))
        attrs = pe.get("attributes") or {}
        if isinstance(attrs, dict):
            parts.append(str(attrs.get("error_type") or ""))
            parts.append(str(attrs.get("error_message") or ""))
            parts.append(str(attrs.get("physical_plan") or "")[:2000])
    for item in (evidence_pack.get("evidence") or [])[:6]:
        if isinstance(item, dict):
            parts.append(str(item.get("excerpt") or ""))
    sections = evidence_pack.get("sections") or {}
    plans = sections.get("sql_plans")
    if isinstance(plans, dict):
        parts.append(str(plans)[:3000])
    return "\n".join(parts)
