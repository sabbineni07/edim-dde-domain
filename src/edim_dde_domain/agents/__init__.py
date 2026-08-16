"""Domain product agents (YAML graphs + nodes + analysis logic).

Business purpose
----------------
Package namespace for bundled agents. Each subdirectory (e.g. ``cluster_tuning``,
``spark_rca``) owns its ``*.agent.yaml``, LangGraph node factories, pure logic
modules, helpers, prompts/skills, and knowledge content.

Bootstrap (``edim_dde_domain.bootstrap``) imports agent node modules so
``@register_node`` factories register with the framework before
``create_agent`` builds graphs.

Public layout
-------------
* ``cluster_tuning`` — job/cluster sizing recommendations
* ``spark_rca`` — Spark job-failure root-cause analysis
"""
