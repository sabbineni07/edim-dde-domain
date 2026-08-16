"""LangGraph node factories for the Cluster Tuning agent (``domain.tuning.*``).

Business purpose
----------------
This module is the **registration glue** between ``cluster_tuning.agent.yaml``
and ``logic.py``. Each ``@register_node`` factory:

1. Captures YAML config at graph-build time (closures).
2. Returns a callable ``(state) -> patch`` that the framework invokes at runtime.

No business logic lives here — keep factories thin so engineers read ``logic.py``
(and helpers) for behavior.

Registered type ids
-------------------
* ``domain.tuning.normalize_metrics``
* ``domain.tuning.build_retrieval_query`` — guidance RAG query
* ``domain.tuning.prepare_sizing_payload`` — history + resource_pressure YAML
* ``domain.tuning.parse_sizing`` — guardrails + retry flags
* ``domain.tuning.validate_performance``
* ``domain.tuning.assess_risks``
* ``domain.tuning.generate_recommendation``
* ``domain.tuning.prepare_explanation_payload``

Importing this module (via domain bootstrap) is enough to register the nodes.
"""

from __future__ import annotations

from typing import Any

from edim_dde_ai import register_node

from edim_dde_domain.agents.cluster_tuning import logic


@register_node("domain.tuning.normalize_metrics")
def normalize_metrics_factory(_config: dict[str, Any]):
    """Seed ``job_id`` / ``cluster_id`` / ``job_run_id`` from metrics when omitted.

    Args:
        _config: Unused; normalize has no YAML knobs today.

    Returns:
        Node callable merging ids + ``metrics`` onto state.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.normalize_metrics(state)

    return _node


@register_node("domain.tuning.build_retrieval_query")
def build_retrieval_query_factory(_config: dict[str, Any]):
    """Prepare ``retrieval_query`` for the guidance ``rag.retrieve`` node.

    Args:
        _config: Unused; query text is derived from live metrics.

    Returns:
        Node callable writing ``retrieval_query``.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.build_retrieval_query(state)

    return _node


@register_node("domain.tuning.prepare_sizing_payload")
def prepare_sizing_payload_factory(config: dict[str, Any]):
    """Flatten metrics + history into string fields for the sizing prompt.

    Args:
        config: Node config. Forwards history knobs
            (``history_job_top_n``, ``history_similar_top_n``,
            ``history_candidate_limit``, ``history_prefer_statuses``,
            ``history_experience_top_k``, ``history_experience_corpus``,
            ``history_heuristic_fallback``) and optional ``resource_pressure``.

    Returns:
        Node callable writing prompt fields + ``sizing_hints_full``.
    """
    history_keys = (
        "history_job_top_n",
        "history_similar_top_n",
        "history_candidate_limit",
        "history_prefer_statuses",
        "history_experience_top_k",
        "history_experience_corpus",
        "history_heuristic_fallback",
    )
    history_config = {k: config[k] for k in history_keys if k in config}
    resource_pressure_config = config.get("resource_pressure")

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.prepare_sizing_payload(
            state,
            history_config=history_config or None,
            resource_pressure_config=resource_pressure_config
            if isinstance(resource_pressure_config, dict)
            else None,
        )

    return _node


@register_node("domain.tuning.parse_sizing")
def parse_sizing_factory(_config: dict[str, Any]):
    """Parse sizing LLM JSON, apply guardrails, set retry flags.

    Args:
        _config: Unused; clamp policy lives in helpers.

    Returns:
        Node callable writing ``sizing``, ``sizing_needs_retry``, etc.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.parse_sizing(state)

    return _node


@register_node("domain.tuning.validate_performance")
def validate_performance_factory(_config: dict[str, Any]):
    """Rule-based peak-load fitness check after sizing settles.

    Args:
        _config: Unused.

    Returns:
        Node callable writing ``performance_validation``.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.validate_performance(state)

    return _node


@register_node("domain.tuning.assess_risks")
def assess_risks_factory(_config: dict[str, Any]):
    """Capacity-change risk level from current vs recommended vCPU × workers.

    Args:
        _config: Unused.

    Returns:
        Node callable writing ``risk_assessment``.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.assess_risks(state)

    return _node


@register_node("domain.tuning.generate_recommendation")
def generate_recommendation_factory(_config: dict[str, Any]):
    """Assemble API-shaped ``recommendation`` + ``comparison`` + reason codes.

    Args:
        _config: Unused.

    Returns:
        Node callable writing ``recommendation``, ``comparison``, ``reason_codes``.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.generate_recommendation(state)

    return _node


@register_node("domain.tuning.prepare_explanation_payload")
def prepare_explanation_payload_factory(_config: dict[str, Any]):
    """Stringify fields for the optional explanation human prompt.

    Args:
        _config: Unused.

    Returns:
        Node callable writing ``recommendation_text``, ``risk_assessment_text``, etc.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.prepare_explanation_payload(state)

    return _node
