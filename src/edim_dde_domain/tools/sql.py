"""SQL helpers: named-param binding + execute against a ResolvedSource.

Business purpose
----------------
Safe SQL for YAML collectors: interpolate ``${ENV}`` only when values look
like Unity Catalog FQNs, bind ``:name`` placeholders from state/static params
to ``?``, and run against a resolved Databricks SQL warehouse.

Public API
----------
* ``rows_to_dicts`` — cursor rows → list of dicts (dates → ISO)
* ``bind_named_query`` — ``:name`` → ``?`` + ordered values
* ``interpolate_sql_env`` — fail-closed ``${VAR}`` FQN substitution
* ``prepare_query`` — env interpolate then named bind
* ``execute_sql`` — run against ``ResolvedSource``
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime
from typing import Any, Mapping, Optional

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources.models import ResolvedSource

logger = logging.getLogger(__name__)

# :name binds (not PostgreSQL :: cast — we use CAST(... AS ...))
_NAMED_PARAM_RE = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")

# Same ${VAR} shape as sources.resolve.interpolate_env
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Unity Catalog / schema.table FQNs only (no spaces, quotes, or SQL punctuation)
_SQL_FQN_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){1,2}$"
)


def _normalize_sql_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def rows_to_dicts(columns: list[str], rows: list[Any]) -> list[dict[str, Any]]:
    """Zip column names with row tuples into dicts; ISO-format date/datetime.

    Args:
        columns: Column names from cursor description.
        rows: Sequence of row tuples/sequences.

    Returns:
        List of ``{column: value}`` dicts.
    """
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
    Blank string state values become ``None`` (SQL NULL) for optional filters.

    Args:
        query: SQL text with ``:param`` markers (not ``::`` casts).
        state: Agent state mapping for dynamic params.
        params_from_state: Allowlisted state keys.
        static_params: Constant binds from YAML ``params:``.

    Returns:
        ``(bound_sql, values)`` ready for the connector.

    Raises:
        DomainToolError: Query references a name not in the allowlist.
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


def interpolate_sql_env(
    text: str,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Replace ``${VAR}`` in SQL with env values validated as table/view FQNs.

    Each substituted value must match ``catalog.schema.table`` or
    ``schema.table`` (letters, digits, underscore only). Unset/empty or
    unsafe values raise ``DomainToolError`` (fail closed).

    Args:
        text: SQL that may contain ``${TABLE_ENV}`` placeholders.
        environ: Env mapping; defaults to ``os.environ``.

    Returns:
        SQL with FQNs substituted.

    Raises:
        DomainToolError: Unset, empty, or non-FQN substitution value.
    """
    env = environ if environ is not None else os.environ

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        value = str(env.get(name, "") or "").strip()
        if not value:
            raise DomainToolError(
                f"SQL env ${{{name}}} is unset or empty; "
                "set a catalog.schema[.table] FQN"
            )
        if not _SQL_FQN_RE.fullmatch(value):
            raise DomainToolError(
                f"SQL env ${{{name}}} must be a catalog.schema[.table] "
                f"identifier (got {value!r})"
            )
        return value

    return _ENV_RE.sub(repl, text)


def prepare_query(
    query: str,
    *,
    state: Mapping[str, Any],
    params_from_state: list[str],
    static_params: Optional[Mapping[str, Any]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> tuple[str, list[Any]]:
    """Interpolate validated ``${ENV}`` FQNs in SQL, then bind ``:name`` params.

    Args:
        query: Raw SQL from agent YAML.
        state: Agent state for dynamic binds.
        params_from_state: Allowlisted state keys.
        static_params: Constant YAML params.
        environ: Optional env for FQN interpolation.

    Returns:
        ``(bound_sql, values)``.
    """
    text = interpolate_sql_env(query, environ)
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
    """Run a parameterized query against a resolved Databricks SQL source.

    Args:
        query: SQL with ``?`` placeholders (after ``prepare_query``).
        params: Positional bind values, or ``None`` / empty for no binds.
        source: Connection-ready source from the registry.

    Returns:
        List of row dicts (dates/datetimes ISO-formatted).

    Raises:
        DomainToolError: Connector / auth / network failure (message includes
            Apps troubleshooting hints).
    """
    from databricks import sql

    try:
        with sql.connect(**source.connection_params()) as conn:
            with conn.cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                columns = (
                    [d[0] for d in cursor.description] if cursor.description else []
                )
                return rows_to_dicts(columns, rows)
    except DomainToolError:
        raise
    except Exception as exc:
        # Connector often wraps 401/scope/network as a generic RequestError
        raise DomainToolError(
            f"Databricks SQL failed for source {source.name!r} "
            f"(host={source.server_hostname!r}, http_path={source.http_path!r}): "
            f"{type(exc).__name__}: {exc}. "
            "On Apps: ensure User authorization includes scope `sql`, warehouse "
            "resource is bound, caller receives X-Forwarded-Access-Token, and the "
            "user has CAN USE + UC SELECT. "
            f"Underlying: {exc!r}"
        ) from exc
