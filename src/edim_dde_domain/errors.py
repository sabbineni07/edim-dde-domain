"""Domain tool errors."""

from __future__ import annotations


class DomainToolError(RuntimeError):
    """Base error for domain data-collection tools."""


class DatabricksNotConfiguredError(DomainToolError):
    """SQL warehouse / host / path / auth not configured."""


class NoJobMetricsError(DomainToolError):
    """Real SQL fetch returned no rows for the requested job/cluster/run."""

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
