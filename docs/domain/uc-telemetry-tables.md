# UC telemetry tables & attributes (E3d)

**Learning path:** E3d · [Guide home](../README.md)  
**← Previous:** [Spark RCA walkthrough](spark-rca-agent.md) · **Next:** [External add-ons](external-addons.md) →

Agents read **Unity Catalog** Delta tables through the SQL warehouse. FQNs are env-driven (never hard-coded catalog names in YAML).

| Env var | Agent | Typical name |
|---------|-------|--------------|
| `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` | `cluster_tuning` | `catalog.schema.job_cluster_metrics` |
| `DATABRICKS_SPARK_METRICS_TABLE` | `spark_rca` | `catalog.schema.spark_metrics` |
| `DATABRICKS_SPARK_LOGS_TABLE` | `spark_rca` | `catalog.schema.spark_logs` |

Column lists below match the **SELECT lists** in the agent YAML (authoritative for the runtime). If your physical table uses different names, add views or align the YAML.

---

## Job cluster metrics {#job-cluster-metrics}

**Used by:** `cluster_tuning` · `collect_metrics` · one row (`ORDER BY job_run_date DESC LIMIT 1`).

### Identity & job context

| Attribute | Meaning |
|-----------|---------|
| `job_run_date` | Calendar date of the run (partition / filter key) |
| `workspace_id` | Databricks workspace id |
| `workspace_name` | Human-readable workspace |
| `job_id` | Job definition id (required filter) |
| `job_run_id` | Specific run id |
| `cluster_id` | Job cluster / all-purpose cluster id |
| `job_type` | Job type label from telemetry |
| `job_name` | Display name |
| `dbr_version` | Databricks Runtime version string |

### Timing

| Attribute | Meaning |
|-----------|---------|
| `job_run_start_time_utc` | Run start (UTC) |
| `job_run_end_time_utc` | Run end (UTC) |
| `job_run_duration_seconds` | Wall-clock duration |

### Driver

| Attribute | Meaning |
|-----------|---------|
| `azure_driver_vm_size` | Driver Azure VM SKU (e.g. `Standard_E8s_v3`) |
| `driver_node_count` | Number of driver nodes (usually 1) |
| `driver_vcpus_consumed` | Driver vCPU consumption metric |
| `driver_memory_gb_consumed` | Driver memory consumption (GB) |
| `avg_driver_cpu_utilization_pct` | Average driver CPU % |
| `avg_driver_memory_utilization_pct` | Average driver memory % |
| `peak_driver_cpu_utilization_pct` | Peak driver CPU % |

### Workers — provisioned vs consumed

| Attribute | Meaning |
|-----------|---------|
| `azure_worker_vm_size` | Worker SKU (defaults to `Standard_E8s_v3` in SQL if null) |
| `max_worker_nodes_provisioned` | Autoscale / fixed max workers provisioned |
| `total_worker_vcpus_provisioned` | Aggregate worker vCPUs provisioned |
| `total_worker_memory_gb_provisioned` | Aggregate worker memory provisioned (GB) |
| `avg_worker_nodes_consumed` | Average workers actually used |
| `p99_worker_nodes_consumed` | P99 workers used (sizing floor input) |
| `avg_worker_vcpus_consumed` | Average worker vCPUs consumed |
| `avg_worker_memory_gb_consumed` | Average worker memory consumed (GB) |
| `avg_worker_vcpus_utilized` | Average utilized worker vCPUs |
| `avg_worker_memory_gb_utilized` | Average utilized worker memory (GB) |

### Workers — utilization & efficiency

| Attribute | Meaning |
|-----------|---------|
| `avg_worker_cpu_utilization_pct` | Average worker CPU % |
| `avg_worker_memory_utilization_pct` | Average worker memory % |
| `peak_worker_cpu_utilization_pct` | Peak worker CPU % (sizing + performance validation) |
| `peak_worker_memory_utilization_pct` | Peak worker memory % |
| `worker_node_provisioning_efficiency_pct` | How efficiently provisioned nodes were used |
| `worker_cpu_utilization_efficiency_pct` | CPU efficiency score |
| `worker_memory_utilization_efficiency_pct` | Memory efficiency score |

### Workload volume

| Attribute | Meaning |
|-----------|---------|
| `processed_bytes` | Bytes processed by the job run |
| `processed_row_count` | Rows processed |

**How sizing uses them:** hints target ~90% util with ~10% buffer on the limiting resource; guardrails enforce worker floors from `p99` / policy; performance validation compares recommended vs current **vCPU × max_workers**.

---

## Spark metrics and logs {#spark-metrics-logs}

### Spark metrics table

**Used by:** `spark_rca` collectors (anchors, SQL plans, timeline, stage pressure).

Common attributes selected in YAML:

| Attribute | Meaning |
|-----------|---------|
| `event_id` | Unique event id |
| `event_ts` | Event timestamp |
| `event_type` | Discriminator (see below) |
| `job_id` / `job_run_id` / `job_run_date` | Job identity |
| `task_key` | Task within the job |
| `spark_app_id` | Spark application id |
| `status` | Status string (e.g. failed / success) |
| `successful` | Boolean success flag |
| `failure_reason` | Failure text when present |
| `attributes` | JSON/string blob of extra event attributes (plans, stage stats, …) |

**`event_type` values the agent filters on:**

| `event_type` | Collector | Role |
|--------------|-----------|------|
| `pipeline_end` (failed) | failure_anchors | Primary failure signal |
| `spark_sql_query_error` | sql_plans | Failed SQL |
| `spark_sql_query_observed` | sql_plans / timeline | Observed SQL |
| `pipeline_start` / `pipeline_end` | timeline | Pipeline bounds |
| `spark_job_start` / `spark_job_completed` | timeline / stage_pressure | Spark job lifecycle |
| `spark_stage_start` / `spark_stage_completed` | timeline / stage_pressure | Stage lifecycle |
| `spark_stage_task_summary` | stage_pressure | Task-level pressure |

### Spark logs table

**Used by:** `collect_error_logs`.

| Attribute | Meaning |
|-----------|---------|
| `log_timestamp` | Log line time |
| `log_level` | Level (`ERROR`, `WARNING`, …) |
| `logger_name` | Logger / class name |
| `message` | Log message body |
| `exception` | Stack / exception text when present |
| `job_id` / `job_run_id` / `job_run_date` / `task_key` / `spark_app_id` | Correlation keys |

Filter: `ERROR`/`WARNING` **or** non-null `exception`.

---

## Grants & ops checklist

1. Warehouse can `SELECT` the three FQNs as the **calling identity** (Apps user or your `az login` principal).
2. Env vars set to full `catalog.schema.table` names.
3. Smoke: dry overrides first, then live ids — [Live smoke](../contribute/live-smoke-test.md).

---

← [Spark RCA walkthrough](spark-rca-agent.md) · [Guide home](../README.md) · [External add-ons](external-addons.md) →
