"""Unit tests for within-env workspace / dataset resolver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.nodes.sql_query import sql_query_factory
from edim_dde_domain.sources import clear_sources, load_sources
from edim_dde_domain.sources.models import ResolvedSource
from edim_dde_domain.workspace import (
    clear_workspace_resolver,
    load_workspace_resolver,
    resolve_workspace_dataset,
)
from edim_dde_domain.workspace.catalog import parse_workspaces_mapping
from edim_dde_domain.workspace.models import WorkspaceDataset
from edim_dde_domain.workspace.resolver import (
    CatalogWorkspaceResolver,
    ProcessEnvWorkspaceResolver,
    build_workspace_resolver,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_workspace_resolver()
    clear_sources()
    yield
    clear_workspace_resolver()
    clear_sources()


def test_parse_skips_cross_env_entries():
    data = {
        "workspaces": {
            "dev_1": {
                "env": "dev",
                "server_hostname": "adb-dev.example.com",
                "http_path": "/sql/1.0/warehouses/aaa",
                "tables": {
                    "job_cluster_metrics": "dev_cat.sch.job_cluster_metrics",
                },
            },
            "prod_1": {
                "env": "prod",
                "server_hostname": "adb-prod.example.com",
                "http_path": "/sql/1.0/warehouses/bbb",
                "tables": {
                    "job_cluster_metrics": "prod_cat.sch.job_cluster_metrics",
                },
            },
        }
    }
    parsed = parse_workspaces_mapping(data, edim_env="dev")
    assert set(parsed) == {"dev_1"}
    assert "prod_1" not in parsed
    assert parsed["dev_1"].edim_env == "dev"


def test_parse_requires_env_field():
    with pytest.raises(DomainToolError, match="env is required"):
        parse_workspaces_mapping(
            {"workspaces": {"dev_1": {"tables": {}}}},
            edim_env="dev",
        )


def test_parse_rejects_bad_fqn():
    with pytest.raises(DomainToolError, match="identifier"):
        parse_workspaces_mapping(
            {
                "workspaces": {
                    "dev_1": {
                        "env": "dev",
                        "tables": {
                            "job_cluster_metrics": "SELECT * FROM evil",
                        },
                    }
                }
            },
            edim_env="dev",
        )


def test_parse_rejects_unknown_table_key():
    with pytest.raises(DomainToolError, match="unknown key"):
        parse_workspaces_mapping(
            {
                "workspaces": {
                    "dev_1": {
                        "env": "dev",
                        "tables": {"mystery_table": "a.b.c"},
                    }
                }
            },
            edim_env="dev",
        )


def test_catalog_resolve_and_default():
    datasets = {
        "dev_1": WorkspaceDataset(
            workspace_id="dev_1",
            edim_env="dev",
            server_hostname="adb-1.example.com",
            http_path="/sql/1.0/warehouses/1",
            tables={"spark_logs": "c.s.logs"},
        ),
        "dev_2": WorkspaceDataset(
            workspace_id="dev_2",
            edim_env="dev",
            server_hostname="adb-2.example.com",
            http_path="/sql/1.0/warehouses/2",
            tables={"spark_logs": "c.s.logs2"},
        ),
    }
    resolver = CatalogWorkspaceResolver(
        datasets, edim_env="dev", default_workspace_id="dev_1"
    )
    assert resolver.resolve(None).workspace_id == "dev_1"
    assert resolver.resolve("dev_2").server_hostname == "adb-2.example.com"
    with pytest.raises(DomainToolError, match="Unknown workspace_id"):
        resolver.resolve("prod_1")


def test_catalog_rejects_cross_env_dataset_at_construct():
    with pytest.raises(DomainToolError, match="never cross env"):
        CatalogWorkspaceResolver(
            {
                "sneaky": WorkspaceDataset(
                    workspace_id="sneaky",
                    edim_env="prod",
                    tables={},
                )
            },
            edim_env="dev",
        )


def test_process_env_fallback():
    resolver = ProcessEnvWorkspaceResolver(
        edim_env="dev",
        environ={
            "DATABRICKS_HOST": "adb.example.com",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/xyz",
            "DATABRICKS_JOB_CLUSTER_METRICS_TABLE": "c.s.metrics",
        },
    )
    ds = resolver.resolve(None)
    assert ds.workspace_id == "default"
    assert ds.server_hostname == "adb.example.com"
    assert ds.as_sql_environ()["DATABRICKS_JOB_CLUSTER_METRICS_TABLE"] == "c.s.metrics"
    with pytest.raises(DomainToolError, match="Unknown workspace_id"):
        resolver.resolve("dev_1")


def test_build_prefers_catalog_when_present():
    datasets = {
        "dev_1": WorkspaceDataset(
            workspace_id="dev_1",
            edim_env="dev",
            tables={"spark_metrics": "a.b.c"},
        )
    }
    resolver = build_workspace_resolver(datasets, edim_env="dev")
    assert isinstance(resolver, CatalogWorkspaceResolver)
    assert resolver.resolve(None).workspace_id == "dev_1"


def test_load_workspace_resolver_from_yaml(tmp_path: Path):
    path = tmp_path / "workspaces.yaml"
    path.write_text(
        yaml.dump(
            {
                "workspaces": {
                    "dev_1": {
                        "env": "dev",
                        "server_hostname": "adb-dev1.example.com",
                        "http_path": "/sql/1.0/warehouses/d1",
                        "tables": {
                            "job_cluster_metrics": "dev1.sch.metrics",
                            "spark_metrics": "dev1.sch.spark_metrics",
                            "spark_logs": "dev1.sch.spark_logs",
                        },
                    },
                    "prod_1": {
                        "env": "prod",
                        "server_hostname": "adb-prod.example.com",
                        "http_path": "/sql/1.0/warehouses/p1",
                        "tables": {
                            "job_cluster_metrics": "prod.sch.metrics",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    ids = load_workspace_resolver(
        path,
        edim_env="dev",
        environ={"EDIM_ENV": "dev", "EDIM_DEFAULT_WORKSPACE_ID": "dev_1"},
    )
    assert ids == ["dev_1"]
    ds = resolve_workspace_dataset("dev_1")
    assert ds.tables["job_cluster_metrics"] == "dev1.sch.metrics"
    with pytest.raises(DomainToolError, match="Unknown workspace_id"):
        resolve_workspace_dataset("prod_1")


def test_sql_query_applies_workspace_overlay(tmp_path: Path):
    path = tmp_path / "workspaces.yaml"
    path.write_text(
        yaml.dump(
            {
                "workspaces": {
                    "dev_1": {
                        "env": "dev",
                        "server_hostname": "adb-ws.example.com",
                        "http_path": "/sql/1.0/warehouses/ws1",
                        "tables": {
                            "job_cluster_metrics": "ws.sch.job_cluster_metrics",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_workspace_resolver(path, edim_env="dev", environ={"EDIM_ENV": "dev"})
    load_sources()

    node = sql_query_factory(
        {
            "source": "edim_sql_wh",
            "query": "SELECT 1 FROM ${DATABRICKS_JOB_CLUSTER_METRICS_TABLE}",
            "params_from_state": [],
            "result_mode": "rows",
            "output_key": "rows",
        }
    )

    captured: dict = {}

    def fake_execute(sql, values, *, source):
        captured["sql"] = sql
        captured["source"] = source
        return [{"ok": 1}]

    base = ResolvedSource(
        name="edim_sql_wh",
        type="databricks_sql",
        server_hostname="adb-default.example.com",
        http_path="/sql/1.0/warehouses/default",
        access_token="tok",
    )

    with (
        patch(
            "edim_dde_domain.nodes.sql_query.try_get_resolved_source",
            return_value=base,
        ),
        patch(
            "edim_dde_domain.nodes.sql_query.execute_sql",
            side_effect=fake_execute,
        ),
    ):
        out = node({"workspace_id": "dev_1"})

    assert out == {"rows": [{"ok": 1}]}
    assert "ws.sch.job_cluster_metrics" in captured["sql"]
    assert captured["source"].server_hostname == "adb-ws.example.com"
    assert captured["source"].http_path == "/sql/1.0/warehouses/ws1"


def test_bindings_sql_warehouse_beat_workspace(tmp_path: Path):
    path = tmp_path / "workspaces.yaml"
    path.write_text(
        yaml.dump(
            {
                "workspaces": {
                    "dev_1": {
                        "env": "dev",
                        "server_hostname": "adb-ws.example.com",
                        "http_path": "/sql/1.0/warehouses/ws1",
                        "tables": {
                            "spark_logs": "ws.sch.logs",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_workspace_resolver(path, edim_env="dev", environ={"EDIM_ENV": "dev"})

    node = sql_query_factory(
        {
            "source": "edim_sql_wh",
            "query": "SELECT 1 FROM ${DATABRICKS_SPARK_LOGS_TABLE}",
            "server_hostname": "adb-binding.example.com",
            "http_path": "/sql/1.0/warehouses/bound",
            "result_mode": "rows",
            "output_key": "rows",
        }
    )

    captured: dict = {}

    def fake_execute(sql, values, *, source):
        captured["source"] = source
        captured["sql"] = sql
        return []

    base = ResolvedSource(
        name="edim_sql_wh",
        type="databricks_sql",
        server_hostname="adb-default.example.com",
        http_path="/sql/1.0/warehouses/default",
        access_token="tok",
    )

    with (
        patch(
            "edim_dde_domain.nodes.sql_query.try_get_resolved_source",
            return_value=base,
        ),
        patch(
            "edim_dde_domain.nodes.sql_query.execute_sql",
            side_effect=fake_execute,
        ),
    ):
        node({"workspace_id": "dev_1"})

    assert captured["source"].server_hostname == "adb-binding.example.com"
    assert "ws.sch.logs" in captured["sql"]
