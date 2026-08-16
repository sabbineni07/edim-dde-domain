"""Domain tool exception hierarchy.

Business purpose
----------------
Typed failures for SQL / source / collect paths so API hosts can map to
stable HTTP codes (e.g. 503 not configured, 404 no metrics) without parsing
message strings.

Public API
----------
* ``DomainToolError`` — base for all domain data-collection failures
* ``DatabricksNotConfiguredError`` — warehouse / host / path / auth missing
* ``NoJobMetricsError`` — live SQL returned zero rows for a job/cluster/run
"""

from __future__ import annotations


class DomainToolError(RuntimeError):
    """Base error for domain data-collection tools.

    Raised by SQL binding, source resolution, bootstrap, and node factories
    when configuration or query setup is invalid (not necessarily Databricks
    connectivity).
    """


class DatabricksNotConfiguredError(DomainToolError):
    """SQL warehouse / host / path / auth not configured.

    Typical causes: unset ``DATABRICKS_HOST`` / ``DATABRICKS_HTTP_PATH``,
    missing Apps ``X-Forwarded-Access-Token``, or failed
    ``DefaultAzureCredential`` token fetch.
    """


class NoJobMetricsError(DomainToolError):
    """Real SQL fetch returned no rows for the requested job/cluster/run.

    Carries the identifiers used in the query so API layers can surface them
    in error payloads without re-parsing the message.

    Args:
        job_id: Job identifier from agent state (may be empty string).
        cluster_id: Optional cluster id filter.
        job_run_id: Optional run id filter.
    """

    def __init__(
        self,
        job_id: str,
        *,
        cluster_id: str | None = None,
        job_run_id: str | None = None,
    ) -> None:
        self.job_id = job_id
        self.cluster_id = cluster_id
        self.job_run_id = job_run_id
        parts = [f"job_id={job_id!r}"]
        if cluster_id:
            parts.append(f"cluster_id={cluster_id!r}")
        if job_run_id:
            parts.append(f"job_run_id={job_run_id!r}")
        super().__init__("No job cluster metrics found for " + ", ".join(parts))
