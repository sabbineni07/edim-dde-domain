"""Tests for sources + named SQL binding + domain.sql.query."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from edim_dde_ai import create_agent
from edim_dde_domain import bootstrap_agents
from edim_dde_domain.errors import DomainToolError, NoJobMetricsError
from edim_dde_domain.sources import clear_sources, get_source_spec, load_sources
from edim_dde_domain.sources.models import ResolvedSource
from edim_dde_domain.sources.resolve import interpolate_env, resolve_source
from edim_dde_domain.tools.sql import bind_named_query, prepare_query


@pytest.fixture(autouse=True)
def _sources():
    clear_sources()
    load_sources()
    yield
    clear_sources()


def test_load_default_sources():
    spec = get_source_spec("edim_sql_wh")
    assert spec.type == "databricks_sql"
    assert "DATABRICKS" in spec.server_hostname or spec.server_hostname.startswith("${")


def test_interpolate_env():
    assert interpolate_env("host=${MYHOST}", {"MYHOST": "adb.example"}) == "host=adb.example"


def test_resolve_source_from_env():
    spec = get_source_spec("edim_sql_wh")
    resolved = resolve_source(
        spec,
        environ={
            "DATABRICKS_HOST": "adb-test.azuredatabricks.net",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
            "DATABRICKS_TOKEN": "dapi-x",
        },
    )
    assert resolved.server_hostname == "adb-test.azuredatabricks.net"
    assert resolved.http_path.startswith("/sql/")
    assert resolved.access_token == "dapi-x"


def test_default_auth_mode_is_auto():
    assert get_source_spec("edim_sql_wh").auth_mode == "auto"


@patch("edim_dde_domain.sources.auth.get_azure_databricks_token", return_value="aad-token")
def test_auto_falls_back_to_azure_credential(mock_aad: MagicMock):
    spec = get_source_spec("edim_sql_wh")
    resolved = resolve_source(
        spec,
        environ={
            "DATABRICKS_HOST": "adb-test.azuredatabricks.net",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
            # no DATABRICKS_TOKEN
        },
    )
    assert resolved.access_token == "aad-token"
    mock_aad.assert_called_once()


def test_env_token_mode_requires_token():
    from edim_dde_domain.errors import DatabricksNotConfiguredError
    from edim_dde_domain.sources.models import SourceSpec

    spec = SourceSpec(
        name="strict",
        type="databricks_sql",
        server_hostname="adb-test.azuredatabricks.net",
        http_path="/sql/1.0/warehouses/abc",
        auth_mode="env_token",
        token_env="DATABRICKS_TOKEN",
    )
    with pytest.raises(DatabricksNotConfiguredError, match="env_token"):
        resolve_source(
            spec,
            environ={
                "DATABRICKS_HOST": "adb-test.azuredatabricks.net",
                "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
            },
        )


@patch("edim_dde_domain.sources.auth.get_azure_databricks_token", return_value="aad-only")
def test_azure_credential_mode_ignores_env_token(mock_aad: MagicMock):
    from edim_dde_domain.sources.models import SourceSpec

    spec = SourceSpec(
        name="aad",
        type="databricks_sql",
        server_hostname="adb-test.azuredatabricks.net",
        http_path="/sql/1.0/warehouses/abc",
        auth_mode="azure_credential",
    )
    resolved = resolve_source(
        spec,
        environ={
            "DATABRICKS_TOKEN": "dapi-ignored",
            "DATABRICKS_HOST": "adb-test.azuredatabricks.net",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
        },
    )
    assert resolved.access_token == "aad-only"
    mock_aad.assert_called_once()


def test_bind_named_query_order():
    sql, values = bind_named_query(
        "SELECT 1 WHERE a = :job_id AND b = :cluster_id AND a2 = :job_id",
        state={"job_id": "j1", "cluster_id": "c1"},
        params_from_state=["job_id", "cluster_id"],
    )
    assert sql.count("?") == 3
    assert values == ["j1", "c1", "j1"]


def test_bind_rejects_unknown_param():
    with pytest.raises(DomainToolError, match=":evil"):
        bind_named_query(
            "SELECT :evil",
            state={},
            params_from_state=["job_id"],
        )


def test_prepare_query_env_and_blank_to_none():
    sql, values = prepare_query(
        "SELECT * FROM ${T} WHERE id = :job_id AND d = :job_run_date",
        state={"job_id": "j1", "job_run_date": ""},
        params_from_state=["job_id", "job_run_date"],
        environ={"T": "cat.sch.tbl"},
    )
    assert "cat.sch.tbl" in sql
    assert values == ["j1", None]


def test_cluster_tuning_metrics_override():
    bootstrap_agents()
    agent = create_agent("cluster_tuning")
    out = agent.invoke(
        {
            "job_id": "j-1",
            "cluster_id": "c-1",
            "include_explanation": True,
            "metrics": {
                "azure_worker_vm_size": "Standard_E8s_v3",
                "max_worker_nodes_provisioned": 16,
                "peak_worker_cpu_utilization_pct": 20,
                "peak_worker_memory_utilization_pct": 25,
            },
        }
    )
    assert out["recommendation"]["recommended_max_workers"] < 16
    assert out["explanation"]


@patch("edim_dde_domain.nodes.sql_query.execute_sql")
@patch("edim_dde_domain.nodes.sql_query.try_get_resolved_source")
def test_sql_query_first_row_empty_errors(mock_src: MagicMock, mock_exec: MagicMock):
    mock_src.return_value = ResolvedSource(
        name="edim_sql_wh",
        type="databricks_sql",
        server_hostname="h",
        http_path="/sql/1.0/warehouses/x",
        access_token="t",
    )
    mock_exec.return_value = []
    bootstrap_agents()
    agent = create_agent("cluster_tuning")
    with pytest.raises(NoJobMetricsError):
        agent.invoke(
            {
                "job_id": "missing",
                "cluster_id": "c-1",
                # force SQL path: no metrics override; stub bypassed because source resolves
            }
        )
