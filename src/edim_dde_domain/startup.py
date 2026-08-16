"""Runtime environment checks for API / host startup (product P1).

Business purpose
----------------
Fail-soft (default) or fail-fast validation of Foundry + Databricks SQL env
**without** contacting remote services. Default mode **warns** so ``/health``
and offline tests still work (Lazy Foundry). Set ``EDIM_STRICT_STARTUP=1`` to
fail fast when Foundry is incomplete; with strict mode also set
``EDIM_REQUIRE_SQL=1`` to require warehouse host/path.

Public API
----------
* ``StartupCheckResult`` — collected warnings / errors
* ``inspect_runtime_env`` — report gaps as warnings only
* ``validate_runtime_env`` — log + optionally raise on strict failures
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from edim_dde_domain.config import DomainSettings, get_settings

logger = logging.getLogger(__name__)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class StartupCheckResult:
    """Collected warnings / errors from env inspection.

    Attributes:
        warnings: Non-fatal gaps (always populated by ``inspect_runtime_env``).
        errors: Fatal gaps when strict mode promotes missing Foundry/SQL.
    """

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no fatal ``errors`` were recorded."""
        return not self.errors


def inspect_runtime_env(
    settings: Optional[DomainSettings] = None,
) -> StartupCheckResult:
    """Inspect warehouse + Foundry env without contacting remote services.

    Always reports gaps as ``warnings``. Callers that need fail-fast should use
    ``validate_runtime_env(..., strict=True)``.

    Args:
        settings: Optional pre-built settings; defaults to ``get_settings()``.

    Returns:
        ``StartupCheckResult`` with warnings (and empty errors).
    """
    cfg = settings or get_settings()
    result = StartupCheckResult()

    if not cfg.foundry_configured():
        result.warnings.append(
            "AZURE_OPENAI_ENDPOINT is unset — agent llm_chain calls will return "
            "503 FOUNDRY_LLM_NOT_CONFIGURED until Foundry is configured"
        )
    elif not (cfg.azure_openai_deployment_name or "").strip():
        result.warnings.append(
            "AZURE_OPENAI_DEPLOYMENT_NAME is empty; defaulting to gpt-4o at invoke time"
        )

    if not cfg.sql_configured():
        result.warnings.append(
            "DATABRICKS_HOST / DATABRICKS_HTTP_PATH incomplete — live SQL collect "
            "will fail unless requests pass metrics / evidence_pack overrides"
        )
    else:
        if not cfg.cluster_metrics_configured():
            result.warnings.append(
                "DATABRICKS_JOB_CLUSTER_METRICS_TABLE unset — cluster_tuning "
                "SQL collect needs it (or a metrics override)"
            )
        if not cfg.spark_tables_configured():
            result.warnings.append(
                "DATABRICKS_SPARK_*_TABLE unset — spark_rca SQL collect needs "
                "them (or an evidence_pack override)"
            )

    return result


def validate_runtime_env(
    settings: Optional[DomainSettings] = None,
    *,
    strict: Optional[bool] = None,
) -> StartupCheckResult:
    """Log warnings; raise ``RuntimeError`` when strict and required env missing.

    ``strict`` defaults to ``EDIM_STRICT_STARTUP`` truthy.

    Args:
        settings: Optional pre-built settings; defaults to ``get_settings()``.
        strict: Override for ``EDIM_STRICT_STARTUP``; ``None`` reads the env.

    Returns:
        The inspected result (warnings always logged).

    Raises:
        RuntimeError: When strict mode finds missing Foundry (and optionally SQL).
    """
    if strict is None:
        strict = _truthy("EDIM_STRICT_STARTUP")

    cfg = settings or get_settings()
    result = inspect_runtime_env(cfg)

    if strict:
        if not cfg.foundry_configured():
            result.errors.append(
                "AZURE_OPENAI_ENDPOINT is required when EDIM_STRICT_STARTUP=1"
            )
        if _truthy("EDIM_REQUIRE_SQL") and not cfg.sql_configured():
            result.errors.append(
                "DATABRICKS_HOST / DATABRICKS_HTTP_PATH required when "
                "EDIM_STRICT_STARTUP=1 and EDIM_REQUIRE_SQL=1"
            )

    for w in result.warnings:
        logger.warning("startup_env: %s", w)
    for e in result.errors:
        logger.error("startup_env: %s", e)

    if result.errors:
        raise RuntimeError(
            "EDIM_STRICT_STARTUP is enabled and runtime env is incomplete:\n- "
            + "\n- ".join(result.errors)
        )
    return result
