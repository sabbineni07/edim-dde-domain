"""Generic ``domain.sql.query`` node — YAML SQL against a named source.

Business purpose
----------------
Declarative collector used by agent YAML: prepare + execute SQL via the
shared sources registry, write rows (or first row) into agent state. Supports
skip/override when callers already injected metrics or an evidence pack
(offline tests / API overrides).

Public API
----------
* ``sql_query_factory`` — ``@register_node("domain.sql.query")`` factory

YAML config keys
----------------
* ``source`` (required) — named source from ``sources.yaml``
* ``query`` (required) — SQL with ``:params`` / ``${ENV}`` FQNs
* ``params_from_state`` — allowlisted state keys for ``:name`` binds
* ``params`` — static binds
* ``result_mode`` — ``rows`` (default) or ``first_row``
* ``output_key`` — state key to write (default ``rows``)
* ``on_empty`` — ``error`` / ``empty`` (first_row defaults to ``error``)
* ``skip_if_key`` — skip SQL when another state key already holds data
* ``server_hostname`` / ``host`` / ``http_path`` — optional warehouse overlay
  (from agent ``bindings.sql-warehouse``); token still from named source auth
"""

from __future__ import annotations

from typing import Any

from dataclasses import replace

from edim_dde_ai import register_node

from edim_dde_domain.config import normalize_http_path, strip_hostname
from edim_dde_domain.errors import (
    DatabricksNotConfiguredError,
    DomainToolError,
    NoJobMetricsError,
)
from edim_dde_domain.sources import try_get_resolved_source
from edim_dde_domain.tools.sql import execute_sql, prepare_query


@register_node("domain.sql.query")
def sql_query_factory(config: dict[str, Any]):
    """Build a LangGraph node that runs parameterized SQL into state.

    Args:
        config: Node config from agent YAML (see module docstring for keys).

    Returns:
        Callable ``(state) -> partial_state`` that writes ``output_key``.

    Raises:
        DomainToolError: Invalid config shape at graph build time.
    """
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
    override_host = config.get("server_hostname") or config.get("host")
    override_path = config.get("http_path")

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        # Override / short-circuit: output already present (tests may inject metrics)
        existing = state.get(output_key)
        if existing not in (None, "", [], {}):
            return {}

        # Skip when another key already holds assembled data (e.g. evidence_pack)
        if skip_if_key and state.get(skip_if_key) not in (None, "", [], {}):
            return {}

        source = try_get_resolved_source(source_name)
        if source is None:
            raise DatabricksNotConfiguredError(
                f"Source {source_name!r} is not configured "
                "(set DATABRICKS_HOST / DATABRICKS_HTTP_PATH and auth via "
                "Apps user OAuth or `az login`)"
            )

        # Optional per-agent warehouse overlay (bindings.sql-warehouse).
        if (
            isinstance(override_host, str)
            and override_host.strip()
        ) or (
            isinstance(override_path, str)
            and override_path.strip()
        ):
            host = source.server_hostname
            path = source.http_path
            if isinstance(override_host, str) and override_host.strip():
                host = strip_hostname(override_host.strip())
            if isinstance(override_path, str) and override_path.strip():
                path = normalize_http_path(override_path.strip())
            source = replace(
                source,
                server_hostname=host,
                http_path=path,
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
