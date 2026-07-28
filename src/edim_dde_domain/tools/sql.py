"""SQL helpers: named-param binding + execute against a ResolvedSource."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Mapping, Optional

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources.models import ResolvedSource
from edim_dde_domain.sources.resolve import interpolate_env

logger = logging.getLogger(__name__)

# :name binds (not PostgreSQL :: cast — we use CAST(... AS ...))
_NAMED_PARAM_RE = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


def _normalize_sql_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def rows_to_dicts(columns: list[str], rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {col: _normalize_sql_value(val) for col, val in zip(columns, row)} for row in rows
    ]


def bind_named_query(
    query: str,
    *,
    state: Mapping[str, Any],
    params_from_state: list[str],
    static_params: Optional[Mapping[str, Any]] = None,
) -> tuple[str, list[Any]]:
    """Convert ``:name`` placeholders to ``?`` and collect values in appearance order.

    Only names listed in ``params_from_state`` or ``static_params`` are allowed.
    """
    static = dict(static_params or {})
    allowed = set(params_from_state) | set(static)
    values: list[Any] = []

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in allowed:
            raise DomainToolError(
                f"SQL references :{name} but it is not in params_from_state "
                f"or params ({sorted(allowed)})"
            )
        if name in static:
            values.append(static[name])
        else:
            val = state.get(name)
            # Treat blank strings as NULL for optional SQL filters
            if val == "":
                val = None
            values.append(val)
        return "?"

    bound_sql = _NAMED_PARAM_RE.sub(repl, query)
    return bound_sql, values


def prepare_query(
    query: str,
    *,
    state: Mapping[str, Any],
    params_from_state: list[str],
    static_params: Optional[Mapping[str, Any]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> tuple[str, list[Any]]:
    """Interpolate ``${ENV}`` in SQL text, then bind ``:name`` params from state."""
    text = interpolate_env(query, environ)
    return bind_named_query(
        text,
        state=state,
        params_from_state=params_from_state,
        static_params=static_params,
    )


def execute_sql(
    query: str,
    params: Optional[list[Any]] = None,
    *,
    source: ResolvedSource,
) -> list[dict[str, Any]]:
    """Run a parameterized query against a resolved Databricks SQL source."""
    from databricks import sql

    with sql.connect(**source.connection_params()) as conn:
        with conn.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description] if cursor.description else []
            return rows_to_dicts(columns, rows)
