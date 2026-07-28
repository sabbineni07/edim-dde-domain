"""Resolve SourceSpec → ResolvedSource (${ENV} + token)."""

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
    """Replace ``${VAR}`` with environment values (empty string if unset)."""
    env = environ if environ is not None else os.environ

    def repl(match: re.Match[str]) -> str:
        return str(env.get(match.group(1), "") or "")

    return _ENV_RE.sub(repl, text)


def resolve_source(
    spec: SourceSpec,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> ResolvedSource:
    """Resolve host/path/token for a source. Raises if incomplete."""
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

    token = resolve_access_token(
        auth_mode=spec.auth_mode,
        token_env=spec.token_env,
        environ=env,
        source_name=spec.name,
    )

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
    try:
        return resolve_source(spec, environ=environ)
    except DatabricksNotConfiguredError:
        return None
