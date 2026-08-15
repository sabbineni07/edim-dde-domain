"""Deterministic sizing hints from configurable resource-pressure dimensions."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any


DEFAULT_RESOURCE_PRESSURE_CONFIG: dict[str, Any] = {
    "target_utilization_pct": 90.0,
    "capacity_buffer_pct": 10.0,
    "shape_change_min_level": "high",
    "dimensions": {
        "cpu": {
            "role": "resource",
            "metric_keys": [
                "peak_worker_cpu_utilization_pct",
                "peak_driver_cpu_utilization_pct",
            ],
            "thresholds": {"low_below": 40.0, "high_at": 70.0, "saturated_at": 85.0},
            "preferred_families": ["F", "D"],
        },
        "memory": {
            "role": "resource",
            "metric_keys": [
                "peak_worker_memory_utilization_pct",
                "peak_driver_memory_utilization_pct",
                "avg_driver_memory_utilization_pct",
            ],
            "thresholds": {"low_below": 40.0, "high_at": 70.0, "saturated_at": 90.0},
            "preferred_families": ["E"],
        },
        "worker_capacity": {
            "role": "capacity",
            "ratio": {
                "numerator_key": "avg_worker_nodes_consumed",
                "denominator_key": "max_worker_nodes_provisioned",
                "scale": 100.0,
            },
            "thresholds": {"low_below": 40.0, "high_at": 70.0, "saturated_at": 90.0},
            "preferred_families": [],
        },
    },
}

_LEVEL_RANK = {"unknown": -1, "low": 0, "moderate": 1, "high": 2, "saturated": 3}


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def default_sizing_policy() -> dict[str, Any]:
    """Return an isolated copy so per-agent overrides cannot mutate defaults."""
    return deepcopy(DEFAULT_RESOURCE_PRESSURE_CONFIG)


def normalize_resource_pressure_config(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge an agent-YAML override onto safe packaged defaults."""
    return _deep_merge(DEFAULT_RESOURCE_PRESSURE_CONFIG, dict(config or {}))


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _dimension_value(
    metrics: dict[str, Any], dimension: dict[str, Any]
) -> tuple[float | None, list[str]]:
    ratio = dimension.get("ratio")
    if isinstance(ratio, dict):
        numerator_key = str(ratio.get("numerator_key") or "")
        denominator_key = str(ratio.get("denominator_key") or "")
        numerator = _number(metrics.get(numerator_key))
        denominator = _number(metrics.get(denominator_key))
        if numerator is None or denominator is None or denominator <= 0:
            return None, []
        scale = _number(ratio.get("scale")) or 100.0
        return numerator / denominator * scale, [numerator_key, denominator_key]

    keys = [str(key) for key in dimension.get("metric_keys") or []]
    observed = [
        (key, value)
        for key in keys
        if (value := _number(metrics.get(key))) is not None
    ]
    if not observed:
        return None, []
    aggregation = str(dimension.get("aggregation") or "max").lower()
    values = [value for _, value in observed]
    value = sum(values) / len(values) if aggregation == "mean" else max(values)
    return value, [key for key, _ in observed]


def _pressure_level(value: float | None, thresholds: dict[str, Any]) -> str:
    if value is None:
        return "unknown"
    low_below = _number(thresholds.get("low_below"))
    high_at = _number(thresholds.get("high_at"))
    saturated_at = _number(thresholds.get("saturated_at"))
    low_below = 40.0 if low_below is None else low_below
    high_at = 70.0 if high_at is None else high_at
    saturated_at = 90.0 if saturated_at is None else saturated_at
    if not low_below <= high_at <= saturated_at:
        raise ValueError(
            "resource-pressure thresholds must satisfy "
            "low_below <= high_at <= saturated_at"
        )
    if value >= saturated_at:
        return "saturated"
    if value >= high_at:
        return "high"
    if value < low_below:
        return "low"
    return "moderate"


def compute_resource_pressure(
    metrics: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute generic pressure facts; scenario names are intentionally absent."""
    policy = normalize_resource_pressure_config(config)
    dimensions: dict[str, dict[str, Any]] = {}
    for name, raw_dimension in (policy.get("dimensions") or {}).items():
        if not isinstance(raw_dimension, dict):
            continue
        value, source_metrics = _dimension_value(metrics, raw_dimension)
        level = _pressure_level(value, dict(raw_dimension.get("thresholds") or {}))
        dimensions[str(name)] = {
            "value_pct": round(value, 2) if value is not None else None,
            "level": level,
            "source_metrics": source_metrics,
            "role": str(raw_dimension.get("role") or "resource"),
            "preferred_families": [
                str(f).upper() for f in raw_dimension.get("preferred_families") or []
            ],
        }

    resource_dimensions = {
        name: details
        for name, details in dimensions.items()
        if details["role"] == "resource" and details["level"] != "unknown"
    }
    limiting_resource = "unknown"
    limiting_level = "unknown"
    if resource_dimensions:
        limiting_resource, limiting = max(
            resource_dimensions.items(),
            key=lambda item: (
                _LEVEL_RANK[item[1]["level"]],
                item[1]["value_pct"] or 0.0,
            ),
        )
        limiting_level = str(limiting["level"])
        min_level = str(policy.get("shape_change_min_level") or "high")
        if _LEVEL_RANK[limiting_level] < _LEVEL_RANK.get(min_level, 2):
            limiting_resource = "none"

    capacity = next(
        (
            details
            for details in dimensions.values()
            if details.get("role") == "capacity"
        ),
        {},
    )
    capacity_level = str(capacity.get("level") or "unknown")
    headroom = {
        "low": "high",
        "moderate": "moderate",
        "high": "low",
        "saturated": "none",
    }.get(capacity_level, "unknown")
    preferred = (
        dimensions.get(limiting_resource, {}).get("preferred_families", [])
        if limiting_resource not in {"none", "unknown"}
        else []
    )
    return {
        "dimensions": dimensions,
        "limiting_resource": limiting_resource,
        "limiting_level": limiting_level,
        "capacity_headroom": headroom,
        "preferred_families": preferred,
    }


def recommended_min_max_workers(
    ingest: dict[str, Any],
    *,
    buffer_pct: float = 10.0,
) -> tuple[int, int]:
    """Floor/ceiling hint for max_workers from observed worker nodes."""
    p95 = float(ingest.get("p95_worker_nodes_consumed") or 0)
    p99 = float(ingest.get("p99_worker_nodes_consumed") or p95)
    ceiling = int(ingest.get("max_worker_nodes_provisioned") or 1)
    min_w = max(int(ingest.get("driver_node_count") or 1) - 1, 0)

    if p95 > 0:
        base_nodes = p95
    elif p99 > 0:
        base_nodes = p99
    else:
        base_nodes = max(float(ingest.get("avg_worker_nodes_consumed") or 1), 1.0)
    buffered = math.ceil(base_nodes * (1.0 + buffer_pct / 100.0))
    max_w = max(int(buffered), 1)
    max_w = min(max_w, ceiling) if ceiling > 0 else max_w
    return max(min_w, 0), int(max_w)


def compute_sizing_hints(
    ingest: dict[str, Any],
    *,
    resource_pressure_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hints for LLM and guardrails: limiting resource, suggested family, worker bounds."""
    policy = normalize_resource_pressure_config(resource_pressure_config)
    target = float(policy["target_utilization_pct"])
    buffer = float(policy["capacity_buffer_pct"])

    peak_cpu = float(ingest.get("peak_worker_cpu_utilization_pct") or 0)
    peak_mem = float(ingest.get("peak_worker_memory_utilization_pct") or 0)
    avg_cpu = float(ingest.get("avg_worker_cpu_utilization_pct") or 0)
    avg_mem = float(ingest.get("avg_worker_memory_utilization_pct") or 0)
    peak_driver_cpu = float(ingest.get("peak_driver_cpu_utilization_pct") or 0)
    avg_driver_cpu = float(ingest.get("avg_driver_cpu_utilization_pct") or 0)
    avg_driver_mem = float(ingest.get("avg_driver_memory_utilization_pct") or 0)

    cluster_peak_cpu = max(peak_cpu, peak_driver_cpu)
    cluster_peak_mem = max(peak_mem, avg_driver_mem)
    pressure = compute_resource_pressure(ingest, config=policy)
    limiting = str(pressure["limiting_resource"])
    driver_limiting = peak_driver_cpu >= peak_cpu and peak_driver_cpu >= 40

    alloc_vcpu = float(ingest.get("avg_worker_vcpus_consumed") or 0)
    util_vcpu = float(ingest.get("avg_worker_vcpus_utilized") or 0)
    alloc_mem = float(ingest.get("avg_worker_memory_gb_consumed") or 0)
    util_mem = float(ingest.get("avg_worker_memory_gb_utilized") or 0)

    vcpu_util_pct = (util_vcpu / alloc_vcpu * 100.0) if alloc_vcpu > 0 else avg_cpu
    mem_util_pct = (util_mem / alloc_mem * 100.0) if alloc_mem > 0 else avg_mem
    driver_underutilized = avg_driver_cpu < 40 and avg_driver_mem < 40
    worker_underutilized = vcpu_util_pct < 40 and mem_util_pct < 40

    current_family = parse_family_from_node_type(
        str(ingest.get("azure_worker_vm_size") or "")
    )
    preferred_families = list(pressure.get("preferred_families") or [])
    suggested_family = preferred_families[0] if preferred_families else current_family

    min_w, max_w = recommended_min_max_workers(ingest, buffer_pct=buffer)
    ceiling = int(ingest.get("max_worker_nodes_provisioned") or max_w)
    p95 = float(ingest.get("p95_worker_nodes_consumed") or 0)
    over_autoscale = ceiling > max(max_w * 2, 2) and p95 > 0

    return {
        "target_utilization_pct": target,
        "capacity_buffer_pct": buffer,
        "limiting_resource": limiting,
        "resource_pressure": pressure,
        "suggested_vm_family": suggested_family,
        "recommended_min_workers": min_w,
        "recommended_max_workers": max_w,
        "vcpu_utilization_pct_of_allocated": round(vcpu_util_pct, 2),
        "memory_utilization_pct_of_allocated": round(mem_util_pct, 2),
        "avg_driver_cpu_utilization_pct": round(avg_driver_cpu, 2),
        "avg_driver_memory_utilization_pct": round(avg_driver_mem, 2),
        "peak_driver_cpu_utilization_pct": round(peak_driver_cpu, 2),
        "driver_limiting": driver_limiting,
        "driver_underutilized": driver_underutilized,
        "overprovisioned_autoscale": over_autoscale,
        "per_node_underutilized": driver_underutilized and worker_underutilized,
    }


def sizing_hints_for_llm(hints: dict[str, Any]) -> dict[str, Any]:
    """Narrow hints for the sizing LLM prompt."""
    return {
        k: hints[k]
        for k in (
            "target_utilization_pct",
            "capacity_buffer_pct",
            "limiting_resource",
            "resource_pressure",
            "recommended_min_workers",
            "recommended_max_workers",
            "suggested_vm_family",
        )
        if k in hints
    }


# Utilization / capacity / SKU fields that count as evidence for reason codes.
# Request-level job_id / cluster_id alone are identifiers, not sizing evidence.
_REASON_CODE_SIGNAL_KEYS = (
    "azure_worker_vm_size",
    "max_worker_nodes_provisioned",
    "avg_worker_nodes_consumed",
    "p99_worker_nodes_consumed",
    "peak_worker_cpu_utilization_pct",
    "peak_worker_memory_utilization_pct",
    "avg_worker_cpu_utilization_pct",
    "avg_worker_memory_utilization_pct",
)


def _has_sizing_signal(ingest: dict[str, Any]) -> bool:
    return any(ingest.get(key) not in (None, "") for key in _REASON_CODE_SIGNAL_KEYS)


def infer_reason_codes(
    ingest: dict[str, Any],
    recommendation: dict[str, Any],
    *,
    change_required: bool = True,
    resource_pressure_config: dict[str, Any] | None = None,
) -> list[str]:
    """Derive machine-readable reason codes from metrics + recommendation.

    ``INSUFFICIENT_EVIDENCE`` means the metrics row has no usable utilization,
    capacity, or SKU signal — not that ``job_id`` / ``cluster_id`` were missing.
    Identifiers may live on the request while ``metrics`` is an override blob.
    """
    if not _has_sizing_signal(ingest):
        return ["INSUFFICIENT_EVIDENCE"]

    hints = compute_sizing_hints(
        ingest, resource_pressure_config=resource_pressure_config
    )
    codes: list[str] = []

    pressure = hints.get("resource_pressure") or {}
    for name, details in (pressure.get("dimensions") or {}).items():
        level = str((details or {}).get("level") or "unknown").upper()
        if level != "UNKNOWN":
            codes.append(f"RESOURCE_PRESSURE_{str(name).upper()}_{level}")
    headroom = str(pressure.get("capacity_headroom") or "unknown").upper()
    if headroom != "UNKNOWN":
        codes.append(f"CAPACITY_HEADROOM_{headroom}")

    node_type = str(ingest.get("azure_worker_vm_size") or "")
    fam_match = re.search(r"Standard_([DEFL])", node_type, re.IGNORECASE)
    current_family = fam_match.group(1).upper() if fam_match else ""
    rec_family = str(recommendation.get("node_family") or "").upper()
    if rec_family and current_family and rec_family != current_family:
        codes.append("RESOURCE_SHAPE_CHANGED")

    if int(ingest.get("max_worker_nodes_provisioned") or 0) <= 1:
        codes.append("MINIMAL_WORKER_CAPACITY")

    if not change_required:
        codes.append("NO_CHANGE_RECOMMENDED")

    if not codes:
        codes.append("NO_CHANGE_RECOMMENDED" if not change_required else "RESOURCE_SIGNAL_AVAILABLE")

    return codes


def parse_vcpus_from_node_type(node_type: str) -> int:
    m = re.search(r"Standard_[DEFL](\d+)", str(node_type or ""), re.IGNORECASE)
    if m:
        try:
            return max(4, int(m.group(1)))
        except ValueError:
            pass
    return 8


def parse_family_from_node_type(node_type: str) -> str:
    m = re.search(r"Standard_([DEFL])", str(node_type or ""), re.IGNORECASE)
    return m.group(1).upper() if m else ""
