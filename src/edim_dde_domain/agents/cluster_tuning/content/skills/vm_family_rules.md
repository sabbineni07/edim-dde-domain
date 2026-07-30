## VM family selection (Databricks on Azure)

| Family | Use when |
|--------|----------|
| **D** | General-purpose; balanced CPU and memory |
| **E** | Memory-heavy workloads (high memory % vs CPU %) |
| **F** | CPU-bound workloads (high CPU %, lower memory pressure) |
| **L** | Storage-optimized (large shuffle/spill or storage-heavy) |

Compare **driver and worker** avg/peak CPU and memory utilization from job_run_ingest.
Recommend worker **node_family** and **vcpus**; driver SKU is informational only.
