# Bundled agents

Shipped inside `edim-dde-domain` under `agents/`:

| `agent_id` | Purpose | Highlights |
|------------|---------|------------|
| `cluster_tuning` | Job cluster sizing recommendations | SQL metrics → sizing LLM → guardrails → resource optimization % |
| `spark_rca` | Spark job root-cause analysis | SQL telemetry sections → evidence pack → classify → RCA LLM |

Both follow [agent package layout](../build-agents/agent-package-layout.md) (`helpers/`, `content/`).

**Overrides for offline runs**

- Tuning: pass `metrics` in invoke/API body  
- RCA: pass `evidence_pack`  

HTTP contracts: [endpoints](../api/endpoints.md).
