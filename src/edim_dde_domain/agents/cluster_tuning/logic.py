"""Cluster Tuning graph business logic (pure state → state patches).

Business purpose
----------------
Each public function here is the body of a ``domain.tuning.*`` LangGraph node
(see ``nodes.py``). Together they implement the product pipeline::

    SQL collect_metrics (framework) → normalize_metrics
      → build_retrieval_query → rag.retrieve (guidance)
      → prepare_sizing_payload → run_sizing (llm_chain)
      → parse_sizing ⇄ prepare_sizing_payload (guardrail retry)
      → validate_performance → assess_risks → generate_recommendation
      → [optional] prepare_explanation_payload → generate_explanation → END

Authoritative signal is always the live ``metrics`` row (SQL or client override).
History (experiences, same-job shelf, guidance RAG) is a **secondary** context
lane and must never block the request when empty or when providers fail.

SQL collection itself lives in a ``domain.sql.query`` node configured in
``cluster_tuning.agent.yaml``; this module only normalizes / prepares /
validates / assembles around those metrics.

Public API
----------
* ``normalize_metrics`` — seed ids after collect / override
* ``build_retrieval_query`` — guidance RAG query text
* ``prepare_sizing_payload`` — flatten metrics + history for sizing prompt
* ``parse_sizing`` — parse LLM JSON, guardrails, retry flags
* ``validate_performance`` — peak-load fitness (no LLM)
* ``assess_risks`` — capacity-change risk level
* ``generate_recommendation`` — API-shaped recommendation + comparison
* ``prepare_explanation_payload`` — string fields for explanation prompt

Public entry points mirror node type ids without the ``domain.tuning.`` prefix.
"""

from __future__ import annotations

from typing import Any

from edim_dde_domain.agents.cluster_tuning.helpers.historical_context import (
    build_retrieval_query as _build_retrieval_query,
    compose_historical_context,
)
from edim_dde_domain.agents.cluster_tuning.helpers.guardrails import (
    format_guardrail_feedback,
    should_retry_sizing,
    validate_and_clamp_with_adjustments,
)
from edim_dde_domain.agents.cluster_tuning.helpers.resource_optimization import (
    estimate_resource_optimization,
)
from edim_dde_domain.agents.cluster_tuning.helpers.sizing_policy import (
    compute_resource_pressure,
    compute_sizing_hints,
    infer_reason_codes,
    parse_family_from_node_type,
    parse_vcpus_from_node_type,
    sizing_hints_for_llm,
)
from edim_dde_domain.agents.cluster_tuning.helpers.validate_performance import (
    validate_performance as _validate_performance,
)
from edim_dde_domain.llm.json_util import dumps, parse_json_object


def normalize_metrics(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure ``job_run_id`` and identity fields are set after SQL / override.

    Prefer request-level ids; fall back to values embedded in the metrics row
    (common when the client posts a metrics override blob).

    Args:
        state: Graph state after ``collect_metrics`` (or metrics override).
            Expected keys: ``metrics``, optional ``job_id`` / ``cluster_id`` /
            ``job_run_id``.

    Returns:
        Patch with ``job_id``, ``cluster_id``, ``job_run_id``, and ``metrics``.
    """
    metrics = dict(state.get("metrics") or {})
    job_run_id = state.get("job_run_id") or metrics.get("job_run_id") or "unknown-run"
    return {
        "job_id": state.get("job_id") or metrics.get("job_id"),
        "cluster_id": state.get("cluster_id") or metrics.get("cluster_id"),
        "job_run_id": job_run_id,
        "metrics": metrics,
    }


def build_retrieval_query(state: dict[str, Any]) -> dict[str, Any]:
    """Build free-text query for cluster-tuning guidance RAG.

    Args:
        state: Graph state with ``metrics``.

    Returns:
        Patch with ``retrieval_query`` for the ``rag.retrieve`` node.
    """
    return _build_retrieval_query(state)


def prepare_sizing_payload(
    state: dict[str, Any],
    *,
    history_config: dict[str, Any] | None = None,
    resource_pressure_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Flatten metrics into string fields for the sizing human prompt.

    On guardrail retry, preserves ``guardrail_feedback`` set by ``parse_sizing``
    and reuses prior ``historical_context`` to avoid re-fetch churn. Otherwise
    fills history from RecommendationStore + optional RAG hits.

    Args:
        state: Graph state after guidance retrieve (and optionally after a
            prior sizing attempt). Reads ``metrics``, ``guardrail_feedback``,
            ``historical_context``, ``sizing_attempts``.
        history_config: YAML history knobs forwarded from the node factory.
        resource_pressure_config: Optional dimension/threshold overrides.

    Returns:
        Patch with ``current_config``, ``job_run_ingest``, ``sizing_hints``,
        ``guardrail_feedback``, ``historical_context``, ``sizing_hints_full``,
        and ``resource_pressure_config``.

    Example:
        First pass yields ``guardrail_feedback="None"``; after a clamp retry the
        same key carries the violation list for the re-prompt.
    """
    metrics = state.get("metrics") or {}
    current_config = {
        "azure_worker_vm_size": metrics.get("azure_worker_vm_size"),
        "max_worker_nodes_provisioned": metrics.get("max_worker_nodes_provisioned"),
        "azure_driver_vm_size": metrics.get("azure_driver_vm_size"),
        "driver_node_count": metrics.get("driver_node_count"),
        "dbr_version": metrics.get("dbr_version"),
    }
    hints = compute_sizing_hints(
        metrics, resource_pressure_config=resource_pressure_config
    )
    feedback = state.get("guardrail_feedback")
    if not feedback or str(feedback).strip() in ("", "None"):
        feedback = "None"
    # On guardrail retry, keep prior historical_context (avoid re-fetch churn).
    prior = state.get("historical_context")
    if (
        prior
        and str(prior).strip() not in ("", "None")
        and state.get("sizing_attempts")
    ):
        historical = str(prior)
    else:
        historical = compose_historical_context(
            state,
            config=history_config,
            resource_pressure_config=resource_pressure_config,
        )
    return {
        "current_config": dumps(current_config),
        "job_run_ingest": dumps(metrics),
        "sizing_hints": dumps(sizing_hints_for_llm(hints)),
        "guardrail_feedback": feedback,
        "historical_context": historical,
        "sizing_hints_full": hints,
        "resource_pressure_config": resource_pressure_config or {},
    }


def parse_sizing(state: dict[str, Any]) -> dict[str, Any]:
    """Parse sizing LLM JSON, apply guardrails + SKU allow-list.

    Accepts both the current schema (``node_family`` / ``vcpus`` / …) and a
    legacy simplified shape that only had ``recommended_node_type``. When
    retryable clamps remain and attempts < max, sets ``sizing_needs_retry``
    and ``guardrail_feedback`` so the graph can re-run sizing.

    Args:
        state: After ``run_sizing``. Expected: ``sizing_raw``, ``metrics``,
            optional ``resource_pressure_config``, ``sizing_attempts``.

    Returns:
        Patch with ``pattern_analysis``, ``sizing``, ``guardrail_adjustments``,
        ``llm_recommendation``, attempt counters, ``sizing_needs_retry``, and
        ``guardrail_feedback``.
    """
    raw = parse_json_object(state.get("sizing_raw"))
    metrics = state.get("metrics") or {}
    current_type = str(metrics.get("azure_worker_vm_size") or "Standard_E8s_v3")
    current_max = int(metrics.get("max_worker_nodes_provisioned") or 16)

    # Accept both original schema and legacy simplified keys
    if "node_family" not in raw and raw.get("recommended_node_type"):
        raw = {
            **raw,
            "node_family": parse_family_from_node_type(str(raw["recommended_node_type"])),
            "vcpus": parse_vcpus_from_node_type(str(raw["recommended_node_type"])),
            "min_workers": int(raw.get("min_workers") or 0),
            "max_workers": int(
                raw.get("max_workers") or raw.get("recommended_max_workers") or current_max
            ),
            "auto_termination_minutes": int(raw.get("auto_termination_minutes") or 0),
        }

    applied, adjustments = validate_and_clamp_with_adjustments(
        raw,
        job_run_ingest=metrics,
        resource_pressure_config=state.get("resource_pressure_config"),
    )
    pattern = str(raw.get("pattern_analysis") or applied.get("rationale") or "Sizing from LLM")

    attempts = int(state.get("sizing_attempts") or 0) + 1
    needs_retry = should_retry_sizing(adjustments, sizing_attempts=attempts)
    feedback = format_guardrail_feedback(adjustments) if needs_retry else "None"

    sizing = {
        "current_node_type": current_type,
        "current_max_workers": current_max,
        "current_min_workers": 0,
        "node_family": applied["node_family"],
        "vcpus": applied["vcpus"],
        "min_workers": applied["min_workers"],
        "max_workers": applied["max_workers"],
        "recommended_node_type": applied["azure_node_type"],
        "recommended_max_workers": applied["max_workers"],
        "recommended_min_workers": applied["min_workers"],
        "auto_termination_minutes": applied["auto_termination_minutes"],
        "rationale": applied.get("rationale") or "",
        "azure_node_type": applied["azure_node_type"],
    }
    return {
        "pattern_analysis": pattern,
        "sizing": sizing,
        "guardrail_adjustments": adjustments,
        "llm_recommendation": raw,
        "sizing_attempts": attempts,
        "guardrail_retries": max(0, attempts - 1),
        "sizing_needs_retry": needs_retry,
        "guardrail_feedback": feedback,
    }


def validate_performance(state: dict[str, Any]) -> dict[str, Any]:
    """Rule-based peak-load fitness check (no LLM). Runs after sizing settles.

    Args:
        state: After ``parse_sizing`` (retry loop exited). Reads ``sizing``,
            ``metrics``, optional ``resource_pressure_config``.

    Returns:
        Patch with ``performance_validation`` (meets_peak, reduction risk, …).
    """
    sizing = state.get("sizing") or {}
    metrics = state.get("metrics") or {}

    cur_type = str(sizing.get("current_node_type") or metrics.get("azure_worker_vm_size") or "")
    rec_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(cur_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(rec_type))
    cur_max = int(sizing.get("current_max_workers") or metrics.get("max_worker_nodes_provisioned") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or sizing.get("max_workers") or 1)

    return {
        "performance_validation": _validate_performance(
            current_vcpus=cur_vcpus,
            current_max_workers=cur_max,
            recommended_vcpus=rec_vcpus,
            recommended_max_workers=rec_max,
            peak_cpu_pct=float(metrics.get("peak_worker_cpu_utilization_pct") or 0),
            peak_memory_pct=float(metrics.get("peak_worker_memory_utilization_pct") or 0),
            job_run_ingest=metrics,
            resource_pressure_config=state.get("resource_pressure_config"),
        )
    }


def assess_risks(state: dict[str, Any]) -> dict[str, Any]:
    """Capacity-change risk from current vs recommended vCPU × workers.

    Incorporates ``performance_validation`` when present (legacy fold-in):
    elevated resource pressure while shrinking, peak-requirement failures, and
    aggressive reduction risk all escalate the level and append mitigations.

    Args:
        state: After ``validate_performance``. Reads ``sizing``, ``metrics``,
            ``performance_validation``, optional ``resource_pressure_config``.

    Returns:
        Patch with ``risk_assessment`` (level, magnitude %, capacities, mitigations).
    """
    sizing = state.get("sizing") or {}
    metrics = state.get("metrics") or {}
    perf = state.get("performance_validation") or {}

    cur_type = str(sizing.get("current_node_type") or metrics.get("azure_worker_vm_size") or "")
    rec_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(cur_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(rec_type))
    cur_max = int(sizing.get("current_max_workers") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or 1)

    cur_cap = int(perf.get("current_capacity_vcpu") or max(cur_vcpus * cur_max, 1))
    rec_cap = int(perf.get("recommended_capacity_vcpu") or max(rec_vcpus * rec_max, 1))
    change_pct = abs(cur_cap - rec_cap) / cur_cap * 100.0

    pressure = compute_resource_pressure(
        metrics, config=state.get("resource_pressure_config")
    )
    elevated_pressure = any(
        isinstance(details, dict)
        and details.get("role") == "resource"
        and str(details.get("level") or "") in {"high", "saturated"}
        for details in (pressure.get("dimensions") or {}).values()
    )

    mitigations: list[str] = []
    if change_pct >= 50:
        level = "high"
        mitigations.append(
            "Roll out on a canary job first; monitor run duration, resource pressure, "
            "and explicit failure events."
        )
    elif change_pct >= 25:
        level = "medium"
        mitigations.append("Compare next run duration and spill metrics against baseline.")
    else:
        level = "low"

    if elevated_pressure and rec_cap < cur_cap:
        level = "high"
        mitigations.append(
            "Resource pressure is elevated while capacity decreases — validate against "
            "peak windows."
        )

    if perf and not perf.get("meets_peak_requirements", True):
        if level == "low":
            level = "medium"
        elif level == "medium":
            level = "high"
        mitigations.append(
            "Performance validation flagged degradation risk "
            f"({', '.join(perf.get('reasons') or ['capacity_check_failed'])})."
        )

    reduction_risk = str(perf.get("reduction_risk_level") or "")
    if reduction_risk == "high" and level != "high":
        level = "high" if level == "medium" else "medium"
        mitigations.append(
            "Aggressive capacity reduction — monitor first runs and keep rollback ready."
        )

    if not mitigations:
        mitigations.append("Validate on a non-prod run before applying broadly.")

    # Dedupe while preserving order
    seen: set[str] = set()
    unique_mitigations: list[str] = []
    for m in mitigations:
        if m not in seen:
            seen.add(m)
            unique_mitigations.append(m)

    return {
        "risk_assessment": {
            "risk_level": level,
            "change_magnitude_pct": round(change_pct, 1),
            "current_capacity_vcpu": cur_cap,
            "recommended_capacity_vcpu": rec_cap,
            "mitigations": unique_mitigations,
            "meets_peak_requirements": bool(perf.get("meets_peak_requirements", True))
            if perf
            else None,
        }
    }


def generate_recommendation(state: dict[str, Any]) -> dict[str, Any]:
    """Assemble the API-facing recommendation, comparison, and reason codes.

    Merges sizing + resource optimization + risk level + pressure snapshot.
    Copies request ``job_id`` / ``cluster_id`` into a local metrics view so
    reason-code consumers see a complete row without mutating agent state.

    Args:
        state: After ``assess_risks``. Reads ``sizing``, ``risk_assessment``,
            ``metrics``, ``sizing_hints_full``, ``performance_validation``,
            optional ``resource_pressure_config``.

    Returns:
        Patch with ``recommendation``, ``comparison``, ``reason_codes``, and
        ``current_configuration``.
    """
    sizing = state.get("sizing") or {}
    risk = state.get("risk_assessment") or {}
    # Metrics override blobs often omit job_id/cluster_id (those live on the
    # request). Copy request IDs into the local metrics view so reason-code /
    # downstream consumers see a complete row without mutating agent state.
    metrics = dict(state.get("metrics") or {})
    for key in ("job_id", "cluster_id"):
        if not metrics.get(key) and state.get(key):
            metrics[key] = state[key]

    current_type = str(sizing.get("current_node_type") or "")
    recommended_type = str(sizing.get("recommended_node_type") or "")
    cur_vcpus = parse_vcpus_from_node_type(current_type)
    rec_vcpus = int(sizing.get("vcpus") or parse_vcpus_from_node_type(recommended_type))
    cur_max = int(sizing.get("current_max_workers") or 1)
    rec_max = int(sizing.get("recommended_max_workers") or 1)

    optimization = estimate_resource_optimization(
        current_vcpus=cur_vcpus,
        current_max_workers=cur_max,
        recommended_vcpus=rec_vcpus,
        recommended_max_workers=rec_max,
    )

    change_required = (
        recommended_type != current_type
        or rec_max != cur_max
        or int(sizing.get("min_workers") or 0) != 0
    )
    reason_codes = infer_reason_codes(
        metrics,
        sizing,
        change_required=change_required,
        resource_pressure_config=state.get("resource_pressure_config"),
    )
    perf = state.get("performance_validation") or {}
    if perf and not perf.get("meets_peak_requirements", True):
        if "PERFORMANCE_DEGRADATION_RISK" not in reason_codes:
            reason_codes.append("PERFORMANCE_DEGRADATION_RISK")

    recommendation = {
        **sizing,
        **optimization,
        "resource_pressure": (state.get("sizing_hints_full") or {}).get(
            "resource_pressure", {}
        ),
        "risk_level": risk.get("risk_level", "low"),
        "reason_codes": reason_codes,
        "meets_peak_requirements": perf.get("meets_peak_requirements"),
        "estimated_performance_impact": perf.get("estimated_impact"),
    }
    comparison = {
        "current": {
            "azure_node_type": current_type,
            "max_workers": sizing.get("current_max_workers"),
            "min_workers": sizing.get("current_min_workers", 0),
            "capacity_vcpu": optimization["current_capacity_vcpu"],
        },
        "recommended": {
            "azure_node_type": recommended_type,
            "node_family": sizing.get("node_family"),
            "vcpus": sizing.get("vcpus"),
            "max_workers": sizing.get("recommended_max_workers"),
            "min_workers": sizing.get("recommended_min_workers"),
            "auto_termination_minutes": sizing.get("auto_termination_minutes"),
            "capacity_vcpu": optimization["recommended_capacity_vcpu"],
        },
        "resource_optimization": {
            "optimization_pct": optimization["resource_optimization_pct"],
            "current_capacity_vcpu": optimization["current_capacity_vcpu"],
            "recommended_capacity_vcpu": optimization["recommended_capacity_vcpu"],
        },
    }
    return {
        "recommendation": recommendation,
        "comparison": comparison,
        "reason_codes": reason_codes,
        "current_configuration": comparison["current"],
    }


def prepare_explanation_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Stringify fields for the explanation human prompt (non-colliding keys).

    Truncates ``historical_context`` so the explanation chain gets provenance
    without the full sizing-prompt budget.

    Args:
        state: After ``generate_recommendation`` when ``include_explanation``.
            Reads ``recommendation``, ``metrics``, ``pattern_analysis``,
            ``risk_assessment``, ``historical_context``.

    Returns:
        Patch with ``recommendation_text``, ``job_run_ingest``,
        ``pattern_analysis``, ``risk_assessment_text``, ``historical_context``.
    """
    history = str(state.get("historical_context") or "None")
    # Explanations need provenance, not the full sizing prompt budget.
    if len(history) > 3000:
        history = history[:2980] + "\n…[truncated]"
    return {
        "recommendation_text": dumps(state.get("recommendation") or {}),
        "job_run_ingest": dumps(state.get("metrics") or {}),
        "pattern_analysis": str(state.get("pattern_analysis") or ""),
        "risk_assessment_text": dumps(state.get("risk_assessment") or {}),
        "historical_context": history,
    }
