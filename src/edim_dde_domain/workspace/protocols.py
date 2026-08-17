"""WorkspaceResolver strategy protocol.

Business purpose
----------------
Strategy seam for picking warehouse + UC FQNs among workspaces **inside** the
process ``EDIM_ENV``. Implementations must fail closed on unknown ids and on
any mapping that would leave the process env (hard rule: no cross-env I/O).

Public API
----------
* ``WorkspaceResolver`` — Protocol for resolve / list / default_id
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from edim_dde_domain.workspace.models import WorkspaceDataset


@runtime_checkable
class WorkspaceResolver(Protocol):
    """Resolve a within-env workspace/dataset for SQL collection.

    Implementations:
    * Catalog-backed resolver (``workspaces.yaml`` filtered to ``EDIM_ENV``)
    * Process-env fallback (single synthetic workspace from ``DATABRICKS_*``)
    """

    @property
    def edim_env(self) -> str:
        """Process EDIM environment this resolver is bound to."""

    def default_workspace_id(self) -> str:
        """Id used when the caller omits ``workspace_id``."""

    def list_workspace_ids(self) -> list[str]:
        """Sorted workspace ids registered for the process env."""

    def resolve(self, workspace_id: Optional[str] = None) -> WorkspaceDataset:
        """Return the dataset for ``workspace_id`` or the default.

        Args:
            workspace_id: Requested workspace; ``None`` / blank → default.

        Returns:
            ``WorkspaceDataset`` whose ``edim_env`` matches the process env.

        Raises:
            DomainToolError: Unknown id, incomplete mapping, or env boundary
                violation (fail closed).
        """
