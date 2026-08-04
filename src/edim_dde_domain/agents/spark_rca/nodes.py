"""Register spark RCA node types with edim-dde-ai."""

from __future__ import annotations

from typing import Any

from edim_dde_ai import register_node

from edim_dde_domain.agents.spark_rca import logic


@register_node("domain.rca.assemble_evidence")
def assemble_evidence_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.assemble_evidence(state)

    return _node


@register_node("domain.rca.classify_failure")
def classify_failure_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.classify_failure(state)

    return _node


@register_node("domain.rca.build_retrieval_query")
def build_retrieval_query_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.build_retrieval_query(state)

    return _node


@register_node("domain.rca.prepare_llm_payload")
def prepare_llm_payload_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.prepare_llm_payload(state)

    return _node


@register_node("domain.rca.parse_llm_json")
def parse_llm_json_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.parse_llm_json(state)

    return _node


@register_node("domain.rca.validate_output")
def validate_output_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.validate_output(state)

    return _node
