"""Domain node type registrations (shared across agents).

Business purpose
----------------
Import side-effect package for LangGraph node factories that are not owned by
a single agent (e.g. ``domain.sql.query``). Bootstrap imports
``edim_dde_domain.nodes.sql_query`` so ``@register_node`` runs at startup.

Public API
----------
* Submodule ``sql_query`` — registers ``domain.sql.query``
"""
