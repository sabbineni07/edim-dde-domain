"""LangGraph node factories for the Spark RCA agent (``domain.rca.*``).

Business purpose
----------------
This module is the **registration glue** between ``spark_rca.agent.yaml`` and
``logic.py``. Each ``@register_node`` factory:

1. Captures YAML config at graph-build time (closures).
2. Returns a callable ``(state) -> patch`` that the framework invokes at runtime.

No business logic lives here — keep factories thin so engineers read ``logic.py``
(and helpers) for behavior.

Registered type ids
-------------------
* ``domain.rca.assemble_evidence``
* ``domain.rca.classify_failure`` — passes ``signal_groups`` from YAML
* ``domain.rca.build_retrieval_query`` — runbooks only
* ``domain.rca.load_historical_context`` — experience + store shelf
* ``domain.rca.build_web_search_query`` — opt-in sanitized egress query
* ``domain.rca.prepare_llm_payload``
* ``domain.rca.parse_llm_json``
* ``domain.rca.validate_output``
* ``domain.rca.evaluate_output``

Importing this module (via domain bootstrap) is enough to register the nodes.
"""

from __future__ import annotations

from typing import Any

from edim_dde_ai import register_node

from edim_dde_domain.agents.spark_rca import logic


@register_node("domain.rca.assemble_evidence")
def assemble_evidence_factory(_config: dict[str, Any]):
    """Build evidence_pack from SQL collector outputs (or keep client override).

    Args:
        _config: Unused; assembly has no YAML knobs today.

    Returns:
        Node callable merging ``evidence_pack`` (and optional seeded ids).
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.assemble_evidence(state)

    return _node


@register_node("domain.rca.classify_failure")
def classify_failure_factory(config: dict[str, Any]):
    """Seed ``classification_hint`` from YAML-ordered ``signal_groups``.

    Args:
        config: Node config; reads ``signal_groups`` list of pattern dicts.

    Returns:
        Node callable writing ``classification_hint``.
    """
    signal_groups = [
        dict(group)
        for group in (config.get("signal_groups") or [])
        if isinstance(group, dict)
    ]

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.classify_failure(state, signal_groups=signal_groups)

    return _node


@register_node("domain.rca.build_retrieval_query")
def build_retrieval_query_factory(_config: dict[str, Any]):
    """Prepare ``retrieval_query`` for the runbooks ``rag.retrieve`` node."""

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.build_retrieval_query(state)

    return _node


@register_node("domain.rca.load_historical_context")
def load_historical_context_factory(config: dict[str, Any]):
    """Compose secondary history (experiences + same-job store shelf).

    Args:
        config: Forwarded as-is to ``logic.load_historical_context``
            (``enabled``, ``corpus``, ``top_k``, ``same_job_limit``).
    """
    history_config = dict(config)

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.load_historical_context(state, config=history_config)

    return _node


@register_node("domain.rca.build_web_search_query")
def build_web_search_query_factory(config: dict[str, Any]):
    """Build sanitized ``web_search_query`` when YAML policy enables search.

    Args:
        config: ``enabled``, ``trigger``, ``confidence_below``, etc.
    """
    web_config = dict(config)

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.build_web_search_query(state, config=web_config)

    return _node


@register_node("domain.rca.prepare_llm_payload")
def prepare_llm_payload_factory(_config: dict[str, Any]):
    """Flatten state into string fields for ``rca.human.md`` placeholders."""

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.prepare_llm_payload(state)

    return _node


@register_node("domain.rca.parse_llm_json")
def parse_llm_json_factory(_config: dict[str, Any]):
    """Parse synthesize text into ``llm_raw`` dict (soft fallback on failure)."""

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.parse_llm_json(state)

    return _node


@register_node("domain.rca.validate_output")
def validate_output_factory(_config: dict[str, Any]):
    """Clamp LLM JSON into the stable ``result`` / API contract shape."""

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.validate_output(state)

    return _node


@register_node("domain.rca.evaluate_output")
def evaluate_output_factory(_config: dict[str, Any]):
    """Attach deterministic ``spark_rca.quality`` scores to ``result``."""

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.evaluate_output(state)

    return _node
