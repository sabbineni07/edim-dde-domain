## VM family selection (Databricks on Azure)

| Family | Use when |
|--------|----------|
| **D** | General-purpose; balanced CPU and memory |
| **E** | Memory-heavy workloads (high memory % vs CPU %) |
| **F** | CPU-bound workloads (high CPU %, lower memory pressure) |
| **L** | Storage-optimized (large shuffle/spill or storage-heavy) |

Compare every configured resource-pressure dimension. The table is an Azure SKU
mapping, not a list of workload scenarios.
Recommend worker **node_family** and **vcpus**; driver SKU is informational only.

Decision discipline:
- Keep the current family when CPU and memory are both healthy; right-size workers
  or vCPU tier before changing family.
- Prefer **E** only when memory is the supported limiting resource and the
  configured threshold permits a shape change.
- Prefer **F** only with CPU-pressure evidence and ample memory headroom.
- Prefer **L** only when an explicit storage dimension or shuffle/spill evidence exists; do not
  infer storage pressure from generic ETL workload labels.
- Underutilization is not evidence for E/F/L. A family change must cite the
  limiting resource.
- Historical experiences corroborate a family choice only when their resource
  pressure features and limiting resource match the current run.
