"""Generic ``domain.sql.query`` node — YAML SQL against a named source."""

from __future__ import annotations

import logging
from typing import Any

from edim_dde_ai import register_node

from edim_dde_domain.config import get_settings
from edim_dde_domain.errors import (
    DatabricksNotConfiguredError,
    DomainToolError,
    NoJobMetricsError,
)
from edim_dde_domain.sources import try_get_resolved_source
from edim_dde_domain.tools.sql import execute_sql, prepare_query

logger = logging.getLogger(__name__)

# Offline defaults when source is not configured and stubs are allowed.
_STUB_BY_OUTPUT_KEY: dict[str, Any] = {
    "metrics": {
        "azure_worker_vm_size": "Standard_E8s_v3",
        "max_worker_nodes_provisioned": 16,
        "avg_worker_nodes_consumed": 4.0,
        "peak_worker_cpu_utilization_pct": 28.0,
        "peak_worker_memory_utilization_pct": 35.0,
    },
}


@register_node("domain.sql.query")
def sql_query_factory(config: dict[str, Any]):
    source_name = config.get("source")
    query = config.get("query")
    if not isinstance(source_name, str) or not source_name.strip():
        raise DomainToolError("domain.sql.query requires config.source")
    if not isinstance(query, str) or not query.strip():
        raise DomainToolError("domain.sql.query requires config.query")

    params_from_state = config.get("params_from_state") or []
    if not isinstance(params_from_state, list):
        raise DomainToolError("params_from_state must be a list of state keys")
    params_from_state = [str(p) for p in params_from_state]

    static_params = config.get("params") or {}
    if static_params is None:
        static_params = {}
    if not isinstance(static_params, dict):
        raise DomainToolError("params must be a mapping if present")

    result_mode = str(config.get("result_mode") or "rows").strip().lower()
    if result_mode not in ("rows", "first_row"):
        raise DomainToolError("result_mode must be 'rows' or 'first_row'")

    output_key = str(config.get("output_key") or "rows")
    on_empty = str(config.get("on_empty") or ("error" if result_mode == "first_row" else "empty"))
    skip_if_key = config.get("skip_if_key")
    skip_if_key = str(skip_if_key) if skip_if_key else None

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        # Override / short-circuit: output already present
        existing = state.get(output_key)
        if existing not in (None, "", [], {}):
            return {}

        # Skip when another key already holds assembled data (e.g. evidence_pack)
        if skip_if_key and state.get(skip_if_key) not in (None, "", [], {}):
            return {}

        source = try_get_resolved_source(source_name)
        if source is None:
            cfg = get_settings()
            if cfg.allow_stub:
                stub = _STUB_BY_OUTPUT_KEY.get(output_key)
                if stub is not None:
                    logger.info(
                        "sql_query_stub",
                        extra={"source": source_name, "output_key": output_key},
                    )
                    return {output_key: dict(stub) if isinstance(stub, dict) else stub}
                # Empty collect for optional multi-query graphs (RCA sections)
                logger.info(
                    "sql_query_stub_empty",
                    extra={"source": source_name, "output_key": output_key},
                )
                return {output_key: {} if result_mode == "first_row" else []}
            raise DatabricksNotConfiguredError(
                f"Source {source_name!r} is not configured and "
                "EDIM_DOMAIN_ALLOW_STUB is false"
            )

        bound_sql, values = prepare_query(
            query,
            state=state,
            params_from_state=params_from_state,
            static_params=static_params,
        )
        rows = execute_sql(bound_sql, values, source=source)

        if result_mode == "first_row":
            if not rows:
                if on_empty == "error":
                    raise NoJobMetricsError(
                        str(state.get("job_id") or ""),
                        cluster_id=state.get("cluster_id"),
                        job_run_id=state.get("job_run_id"),
                    )
                return {output_key: {}}
            return {output_key: rows[0]}

        return {output_key: rows}

    return _node
