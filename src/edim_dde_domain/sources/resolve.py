"""Resolve SourceSpec → ResolvedSource (${ENV} + runtime token).

Business purpose
----------------
Turn YAML ``SourceSpec`` (possibly with ``${ENV}`` placeholders) into a
connection-ready ``ResolvedSource``: normalize host/path, then mint a
Databricks access token via :func:`resolve_access_token`.

Public API
----------
* ``interpolate_env`` — substitute ``${VAR}`` (empty if unset; not SQL-safe)
* ``resolve_source`` — raise if host/path/token incomplete
* ``try_resolve_source`` — return ``None`` instead of raising not-configured
"""

from __future__ import annotations

import os
import re
from typing import Mapping, Optional

from edim_dde_domain.config import normalize_http_path, strip_hostname
from edim_dde_domain.errors import DatabricksNotConfiguredError
from edim_dde_domain.sources.auth import resolve_access_token
from edim_dde_domain.sources.models import ResolvedSource, SourceSpec

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def interpolate_env(text: str, environ: Optional[Mapping[str, str]] = None) -> str:
    """Replace ``${VAR}`` with environment values (empty string if unset).

    Matches ``${NAME}`` where ``NAME`` starts with a letter or ``_``, then
    letters, digits, or ``_``. Unlike SQL FQN interpolation, unset vars become
    ``""`` (callers detect incomplete host/path afterward).

    Args:
        text: Input string that may contain ``${VAR}`` placeholders.
        environ: Mapping to read; defaults to ``os.environ``.

    Returns:
        String with substitutions applied; invalid placeholder shapes unchanged.

    Examples::

        interpolate_env("host=${DATABRICKS_HOST}", {"DATABRICKS_HOST": "adb.example"})
        # → "host=adb.example"

        interpolate_env("${_FOO}", {"_FOO": "x"})           # → "x"
        interpolate_env("${MISSING}", {})                   # → ""
        interpolate_env("$DATABRICKS_HOST", {...})          # unchanged (no braces)
        interpolate_env("${123}", {...})                    # unchanged (invalid name)
        interpolate_env("${FOO-BAR}", {...})                # unchanged (``-`` not allowed)
    """
    env = environ if environ is not None else os.environ

    def repl(match: re.Match[str]) -> str:
        return str(env.get(match.group(1), "") or "")

    return _ENV_RE.sub(repl, text)


def resolve_source(
    spec: SourceSpec,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> ResolvedSource:
    """Resolve host/path/token for a source.

    Args:
        spec: Unresolved source from ``sources.yaml``.
        environ: Optional env mapping for ``${VAR}`` and host/path fallbacks.

    Returns:
        ``ResolvedSource`` with normalized hostname, HTTP path, and access token.

    Raises:
        DatabricksNotConfiguredError: Unsupported type, incomplete host/path,
            or token resolution failure.
    """
    env = environ if environ is not None else os.environ
    if spec.type != "databricks_sql":
        raise DatabricksNotConfiguredError(
            f"Unsupported source type {spec.type!r} for source {spec.name!r}"
        )

    host_raw = interpolate_env(spec.server_hostname, env).strip()
    if not host_raw:
        host_raw = (
            env.get("DATABRICKS_SERVER_HOSTNAME")
            or env.get("DATABRICKS_HOST")
            or ""
        ).strip()
    hostname = strip_hostname(host_raw)

    path_raw = interpolate_env(spec.http_path, env).strip()
    http_path = normalize_http_path(path_raw)

    if not (hostname and http_path):
        raise DatabricksNotConfiguredError(
            f"Source {spec.name!r} is not fully configured "
            f"(hostname={hostname!r}, http_path={http_path!r})."
        )

    token = resolve_access_token(source_name=spec.name)

    return ResolvedSource(
        name=spec.name,
        type=spec.type,
        server_hostname=hostname,
        http_path=http_path,
        access_token=token,
    )


def try_resolve_source(
    spec: SourceSpec,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> ResolvedSource | None:
    """Like ``resolve_source`` but returns ``None`` on not-configured errors.

    Args:
        spec: Unresolved source.
        environ: Optional env mapping.

    Returns:
        ``ResolvedSource`` or ``None``.
    """
    try:
        return resolve_source(spec, environ=environ)
    except DatabricksNotConfiguredError:
        return None
