# Utilization, pressure, and failure evidence

Utilization metrics describe resource pressure. They do not prove that a job
failed or identify a failure cause.

Evidence rules:
- CPU or memory percentages may support a pressure level and resource-shape
  decision.
- Claim OOM/out-of-memory only when explicit failure/error evidence contains that
  event. High memory utilization alone is not OOM.
- Apply the same boundary to throttling, spill, skew, disk exhaustion, network
  saturation, and similar events: require the corresponding metric, event, or log.
- Distinguish driver and worker signals. A driver-only bottleneck does not by
  itself support changing worker count.
- If failed-run logs are later supplied by an RCA flow, treat them as a separate
  evidence channel and preserve their provenance.
- Historical outcomes can corroborate a pressure/action pattern, but cannot create
  missing failure evidence for the current run.

Keywords: evidence boundary, utilization, resource pressure, failed run, error
logs, driver, worker, provenance, Databricks.
