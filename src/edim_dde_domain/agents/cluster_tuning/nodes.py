"""Register cluster tuning node types with edim-dde-ai."""

from __future__ import annotations

from typing import Any

from edim_dde_ai import register_node

from edim_dde_domain.agents.cluster_tuning import logic


@register_node("domain.tuning.normalize_metrics")
def normalize_metrics_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.normalize_metrics(state)

    return _node


@register_node("domain.tuning.run_sizing")
def run_sizing_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.run_sizing(state)

    return _node


@register_node("domain.tuning.assess_risks")
def assess_risks_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.assess_risks(state)

    return _node


@register_node("domain.tuning.generate_recommendation")
def generate_recommendation_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.generate_recommendation(state)

    return _node


@register_node("domain.tuning.generate_explanation")
def generate_explanation_factory(_config: dict[str, Any]):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return logic.generate_explanation(state)

    return _node
