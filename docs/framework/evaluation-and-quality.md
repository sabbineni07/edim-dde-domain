# Evaluation, quality, and confidence

**Learning path:** D7 · [Guide home](../README.md)
**← Previous:** [Orchestration](orchestration-topology.md) · **Next:** [Sources and SQL](../domain/sources-and-sql.md) →

## 1. Three different questions

Do not collapse these into one “confidence” number:

| Question | EDIM mechanism |
|----------|----------------|
| Is the output structurally/legal valid? | parser + guardrails + schema |
| Is it a good recommendation for the evidence? | `Evaluator` rubric |
| How trustworthy is the evaluation itself? | `EvaluationResult.confidence` |

An LLM saying “I am 95% confident” is not calibrated evidence. EDIM confidence
is based on **input completeness and deterministic rubric coverage**, not model
self-report.

## 2. Framework surface

`edim_dde_ai.evaluation` provides:

- `Evaluator` Strategy protocol
- `EvaluationResult(score, confidence, passed, dimensions, findings, metadata)`
- registry: `register_evaluator`, `get_evaluator`, `list_evaluators`, `evaluate`

```python
from edim_dde_ai.evaluation import evaluate

result = evaluate(
    "cluster_tuning.quality",
    inputs={"metrics": metrics},
    output=agent_state,
    context={"historical_context": agent_state.get("historical_context")},
)
print(result.to_dict())
```

The seam supports deterministic rubrics today and an LLM-as-judge or
MLflow/LangSmith evaluator later without changing callers.

??? note "In depth (optional) — agent authors — writing a new Evaluator"

    Use this when adding a quality gate for another agent (or a second tuning
    rubric). Operators only need §1–3 and §4's golden-case checklist.

    **Framework contract.** Implement `Evaluator` (`name` + `evaluate(inputs,
    output, context) → EvaluationResult`). Register at domain bootstrap with
    `register_evaluator(...)`. Callers always use `evaluate("…")` so swapping a
    deterministic rubric for an LLM judge later does not change CI wiring.

    **What belongs in each field.**

    | Field | Meaning |
    |-------|---------|
    | `score` | Weighted rubric quality in `[0, 1]` |
    | `confidence` | How complete/reliable the *evaluator's* evidence was — never the LLM's self-report |
    | `passed` | Gate for CI (e.g. score ≥ threshold **and** contract dimension = 1.0) |
    | `dimensions` | Named partial scores for diagnosis |
    | `findings` | Human-readable failure reasons |
    | `metadata` | Threshold, confidence definition, policy version |

    **Recipe.**

    1. Add `edim_dde_domain/evaluation/<agent>.py` with a class implementing the
       protocol.
    2. Prefer **config-driven direction checks** (pass policy via constructor or
       `context`) over hard-coded scenario `if/else` — see
       `ClusterTuningQualityEvaluator` + YAML `resource_pressure`.
    3. Register from `bootstrap._register_evaluators()`.
    4. Add golden cases under `tests/test_<agent>_quality.py` that lock the axes
       you care about (not a closed scenario enum).
    5. Document the rubric dimensions in this guide (or a short agent-local
       subsection).

    **Confidence definition to copy.** Start with
    `0.7 × critical-input completeness + 0.3 × rubric-dimension coverage` and
    document it in `metadata["confidence_definition"]`. Calibrating that number
    against accepted/applied outcomes is Phase 2c work (see backlog; after corpus
    + Foundry harness).

## 3. Cluster-tuning rubric

`ClusterTuningQualityEvaluator` scores five dimensions:

| Dimension | Weight | Examples |
|-----------|--------|----------|
| Contract | 25% | legal family/vCPU/workers; auto-termination=0 |
| Evidence | 20% | cites live metrics; all five analysis headings |
| Direction | 25% | worker direction agrees with capacity pressure; family changes require a configured limiting-resource shape mismatch |
| History | 15% | addresses present history; says none/irrelevant when absent |
| Safety | 15% | no invented dollars; failure claims require explicit event/error evidence |

Default pass: score ≥ **0.75** and contract score = 1.0.

Confidence:

```text
0.70 × critical-metric completeness
+ 0.30 × deterministic-rubric coverage
```

Critical metrics: worker SKU, provisioned max workers, peak worker CPU, peak
worker memory.

## 4. Spark-RCA rubric

`SparkRcaQualityEvaluator` is attached to every successful RCA graph result:

| Dimension | Weight | Examples |
|-----------|--------|----------|
| Contract | 20% | valid broad category, summary, signature, actions, bounded model confidence |
| Evidence | 25% | cited refs exist in the supplied pack; evidence channels are analyzed |
| Diagnosis | 20% | diagnosis overlaps current-run signals; high-confidence rule conflicts are flagged |
| Actions | 15% | concrete fixes/checks rather than only “check logs” |
| Context | 10% | retrieved runbooks/history/web are explicitly corroborated, conflicted, or not used |
| Safety | 10% | web URLs were actually supplied; external context does not replace current evidence |

Default pass requires score ≥ **0.75**, contract = 1.0, evidence ≥ 0.75,
actions ≥ 0.66, and safety = 1.0.

`root_cause.confidence` / `model_confidence` remains the model/rule estimate.
`quality.confidence` is:

```text
0.70 × evidence-pack channel completeness
+ 0.30 × deterministic-rubric coverage
```

The two values answer different questions and must not be averaged.

### Evidence citations vs. backfilled preview

The **Evidence** dimension grades the model's *own* citations, not what the UI
happens to display.

- `validate_output` puts only the model's valid `evidence_refs` into
  `result.evidence`. It **never silently substitutes** pack rows for missing
  citations — a fabricated citation would falsely imply the model grounded its
  diagnosis in that row.
- When the model cites nothing resolvable but the pack has rows, up to three
  rows are attached as a **labeled preview** (`backfilled: true` per item and
  `evidence_backfilled: true` on the result) purely so the client panel is not
  empty. These rows are *not* asserted to support the summary or actions.
- The evaluator excludes `backfilled` rows when computing `used_refs`. So a
  response whose evidence is entirely backfilled scores as "no citations
  present" and adds the finding **`Model did not cite available evidence`**
  (with `(only pack preview backfilled)` appended). This keeps the Evidence
  score honest and prevents the preview from masking a model that skipped
  citations.

Consumers that need "did the model actually cite something?" should check
`evidence_backfilled == false` and/or filter `evidence` on `backfilled == false`
rather than treating a non-empty `evidence` list as proof of grounding.

## 5. How to prove a prompt improved quality

### 5a. Versioned golden corpus (Quality Phase 2a)

Release cases live under `edim-dde-domain/testdata/quality/v1/`:

```text
testdata/quality/v1/
  manifest.yaml                 # version, agents, case ids, default_trials
  cluster_tuning/<case_id>.json
  spark_rca/<case_id>.json
```

Each JSON case has `inputs` / `output` / `expectations` for offline scoring with
`cluster_tuning.quality` or `spark_rca.quality`. Both agents share one manifest.

```python
from edim_dde_domain.evaluation import load_quality_corpus, score_corpus_offline
from edim_dde_domain.evaluation.cluster_tuning import register_cluster_tuning_evaluator
from edim_dde_domain.evaluation.spark_rca import register_spark_rca_evaluator

register_cluster_tuning_evaluator()
register_spark_rca_evaluator()
corpus = load_quality_corpus(version="v1")
rows = score_corpus_offline(corpus)
assert all(r.passed and not r.expectation_failures for r in rows)
```

Pytest gate: `tests/test_quality_corpus.py`.

### 5b. Where evidence / metrics come from (prod vs smoke)

Do not confuse the **quality harness** with **production runtime**. Neither
`evidence_pack` (RCA) nor `metrics` (cluster tuning) is “always from JSON” or
“always from Databricks” — the source depends on how the agent was invoked.

| Source | When it happens | SQL collectors |
|--------|-----------------|----------------|
| **Built live from Databricks UC** | Prod / API / Apps: request has `job_run_id` or `job_id`+`cluster_id` and **does not** send a pack/metrics override | Run — assemble from warehouse telemetry |
| **Sent in the HTTP / invoke state** | Client (or engineer) includes `evidence_pack` or `metrics` in the body | **Skipped** (`skip_if_key`) — rest of graph (RAG, Foundry, validate, quality) still runs |
| **Case JSON under `testdata/quality/`** | Offline corpus gate, fixture-only harness rows, and most smoke `invoke_input` packs | N/A offline; skipped when pack/metrics are in `invoke_input` |

```text
PROD (typical)
  POST { job_run_id }  →  SQL × N  →  real evidence_pack / metrics  →  Foundry  →  response
                           (+ RecommendationStore save)

HARNESS / SMOKE
  case JSON  →  either:
    score_output:     frozen output → rubric only (no Foundry, no SQL)
    invoke_input:     pack/metrics from JSON → graph + Foundry (SQL skipped)
                      (omit pack/metrics + real ids → full live SQL like prod)
```

**What “live” means in the harness:** `--live` + `invoke_input` makes the
**Foundry completion** realtime. The **inputs** still usually come from the case
JSON unless you omit the override and pass a real warehouse-backed id. Fixture
cases without `invoke_input` stay `mode: score_output` even under `--live`
(re-grade golden JSON only).

Agent walkthroughs: [Spark RCA — input](../domain/spark-rca-agent.md#2-input-http--agent-state) ·
[Cluster tuning — input](../domain/cluster-tuning-agent.md#2-input-http--agent-state).
API dry vs warehouse live: [Live & dry smoke test](../contribute/live-smoke-test.md).

### 5c. Unified Foundry harness (Quality Phase 2b)

One runner covers **both** agents. Offline (default) re-scores fixtures; `--live`
bootstraps agents and can invoke when cases include `invoke_input`.
```bash
# Offline — deterministic fixtures, no Foundry
python -m edim_dde_domain.evaluation.harness --corpus v1 --trials 1

# Live — Foundry (requires .env); repeats N trials per case
python -m edim_dde_domain.evaluation.harness --corpus v1 --trials 3 --live \
  --out /tmp/quality-v1-report.json
```

The JSON report includes per-trial `score`, `dimensions`, `passed`, `latency_ms`,
optional token metadata from the evaluator, plus `git_sha` / Foundry
endpoint/deployment when set in env. Use the same corpus version and trial count
before and after a prompt change; require no regression on contract/safety and
an agreed lift on evidence / direction / history / diagnosis axes.

**v1 cases today** ship as `mode: score_output` (frozen `output` fixtures). Adding
`invoke_input` to a case is what turns `--live` into a real agent+Foundry trial
(see deep dive below). A case may keep **both**: `output` for offline CI, and
`invoke_input` for live trials.

??? note "In depth (optional) — engineers — live harness with `invoke_input`"

    Use this when you need to understand **what `--live` actually does**, how
    state flows through the agent graph, and how the harness maps the result
    back into the same rubric used offline.

    #### Offline vs live (same corpus, different middle)

    ```text
    ┌──────────────────────── OFFLINE (default) ────────────────────────┐
    │  case.inputs + case.output  →  evaluate(rubric)  →  TrialResult   │
    │  No graph · no Foundry · no Search · no SQL                       │
    └───────────────────────────────────────────────────────────────────┘

    ┌──────────────────────── LIVE (--live + invoke_input) ─────────────┐
    │  case.invoke_input                                                │
    │       → create_agent(id).invoke(state)   ← full LangGraph         │
    │       → map state → (inputs, output, context)                     │
    │       → evaluate(same rubric)  →  TrialResult                     │
    └───────────────────────────────────────────────────────────────────┘
    ```

    ```mermaid
    flowchart TD
      CLI["CLI: harness --live --trials N"] --> Boot[bootstrap_agents + Foundry]
      Boot --> Loop[For each case × trial]
      Loop --> Has{invoke_input present?}
      Has -->|no| Fix[score case.output<br/>mode=score_output]
      Has -->|yes| Inv["create_agent.invoke(invoke_input)"]
      Inv --> Graph[Agent graph runs]
      Graph --> Map[_extract_eval_payload]
      Map --> Eval[evaluate evaluator name]
      Fix --> Eval
      Eval --> Exp[check expectations]
      Exp --> Row[TrialResult]
      Row --> Rep[HarnessReport JSON]
    ```

    #### Case JSON shape for live

    Keep offline fixtures; add a flat agent state under `invoke_input`:

    ```json
    {
      "case_id": "rca_executor_oom_live",
      "agent_id": "spark_rca",
      "mode": "invoke_agent",
      "inputs": { "evidence_pack": { "...": "used by offline score + as eval fallback" } },
      "output": { "...": "frozen good answer for offline CI only" },
      "invoke_input": {
        "job_run_id": "jr-harness-1",
        "job_id": "j-harness-1",
        "evidence_pack": {
          "raw_anchors": { "failure_reason": "Executor OutOfMemoryError: Java heap space" },
          "evidence": [{ "ref": "logs:error:1", "excerpt": "Executor OutOfMemoryError: Java heap space" }]
        }
      },
      "expectations": { "passed": true, "min_score": 0.75 }
    }
    ```

    Copyable example (not in the scored manifest):  
    `testdata/quality/v1/examples/rca_executor_oom_invoke.example.json`

    | Field | Offline | Live with `invoke_input` |
    |-------|---------|---------------------------|
    | `inputs` / `output` | Scored directly | `output` ignored for scoring; `inputs` can fill gaps if state omits pack/metrics |
    | `invoke_input` | Ignored | Passed to `create_agent(...).invoke(...)` |
    | `expectations` | Applied | Applied to the **live** evaluation result |

    **Why pass `evidence_pack` / `metrics` in `invoke_input`?**  
    Those fields are the same overrides used on the HTTP API. SQL collectors use
    `skip_if_key: evidence_pack` (RCA) or skip when `metrics` is already present
    (tuning). That lets the live harness exercise LLM + RAG + validate + quality
    **without** a live Databricks warehouse. The pack/metrics still come from the
    **case JSON** in that mode — only the model answer is realtime.

    **Prod is different:** a normal `POST /api/v1/rca/analyze` with a real
    `job_run_id` and **no** `evidence_pack` builds the pack from UC SQL, then
    calls Foundry. Omit the override in `invoke_input` (and supply a real id) to
    approximate that full path from the harness (needs warehouse creds).

    See [§5b Where evidence / metrics come from](#5b-where-evidence--metrics-come-from-prod-vs-smoke).

    #### Live trial — harness I/O at each step

    | Step | Code | Input | Output |
    |------|------|-------|--------|
    | 1. Bootstrap | `bootstrap_agents()`, Foundry provider | `.env` | Agents registered, LLM ready |
    | 2. Invoke | `create_agent(agent_id).invoke(invoke_input)` | Flat state | Final graph state |
    | 3. Map | `_extract_eval_payload` | Final state | Rubric `inputs` / `output` / `context` |
    | 4. Score | `evaluate(evaluator, …)` | Mapped triple | `EvaluationResult` |
    | 5. Gate | `check_expectations` | Result + case expectations | Failures list |
    | 6. Row | `TrialResult` | Above + `latency_ms` | `mode=invoke_agent`, `metadata.live=true` |

    **Mapping rules (step 3):**

    | Agent | Rubric `inputs` | Rubric `output` | Rubric `context` |
    |-------|-----------------|-----------------|------------------|
    | `cluster_tuning` | `{ metrics }` from state (else case.inputs) | `{ recommendation }` from state | `{ historical_context }` |
    | `spark_rca` | `{ evidence_pack }` from state (else case.inputs) | `result` dict (root_cause, actions, …) | `{ web_search_context }` |

    #### Inside `create_agent("spark_rca").invoke(...)` (graph deep dive)

    With `evidence_pack` already in state, SQL nodes no-op (`skip_if_key`), then
    the analysis path runs:

    ```mermaid
    flowchart LR
      S[invoke_input state] --> A[assemble_evidence]
      A --> C[rule_classify]
      C --> Q[build_retrieval_query]
      Q --> H[load_historical_context]
      H --> W[web.search optional]
      W --> R[rag.retrieve<br/>bindings.search applies here]
      R --> P[prepare_llm_payload]
      P --> L[llm_chain<br/>bindings.llm + Foundry]
      L --> J[parse_llm_json]
      J --> V[validate_output]
      V --> E[evaluate_output<br/>spark_rca.quality on graph]
      E --> F[final state.result]
    ```

    | Graph hop | State in (notable) | State out (notable) |
    |-----------|--------------------|---------------------|
    | SQL collectors | `job_run_id` / pack override | Skipped when `evidence_pack` set |
    | `assemble_evidence` | Pack or SQL sections | Canonical `evidence_pack` |
    | `rule_classify` | Pack | `classification_hint` |
    | `build_retrieval_query` | Hint + pack | `retrieval_query` string |
    | `load_historical_context` | job / pack features | `historical_context` text |
    | `rag.retrieve` | `retrieval_query` | `retrieval_hits`, runbook context (**Search binding**) |
    | `prepare_llm_payload` | Pack + contexts | Prompt-ready keys |
    | `llm_chain` | Messages | `llm_raw` (**LLM binding** / Foundry) |
    | `parse` / `validate` | Raw JSON | Structured `result` + citations |
    | `evaluate_output` | Pack + result | `result.quality` (graph-attached rubric) |

    The harness **re-scores** with the same registry evaluator after invoke so
    offline and live reports share one schema. RCA’s in-graph `evaluate_output`
    is a useful runtime signal; the harness row is the release artifact.

    #### Inside `create_agent("cluster_tuning").invoke(...)` (short)

    ```text
    metrics override or SQL → normalize → build_retrieval_query
      → rag.retrieve (guidance; bindings.search)
      → prepare_sizing_payload → llm_chain (Foundry; bindings.llm)
      → parse → validate_performance → assess_risks → generate_recommendation
      → optional explanation llm_chain
    ```

    Harness then scores `recommendation` + `metrics` with `cluster_tuning.quality`
    (tuning has no in-graph evaluate node today).

    #### Example live CLI

    ```bash
    # Point --corpus-root at a folder whose manifest lists invoke_input cases,
    # or temporarily add invoke_input to a v1 case JSON.
    python -m edim_dde_domain.evaluation.harness --corpus v1 --trials 3 --live \
      --agents spark_rca --out /tmp/rca-live.json
    ```

    Expect `results[].mode` = `invoke_agent` when `invoke_input` was used, and
    `score_output` for fixture-only cases still in the same run.

### 5d. Golden axes (what cases should cover)

Golden cases should cover the reasoning axes, not a fixed scenario enum:

- low pressure + high capacity headroom: conservative worker/tier reduction
- high worker-capacity pressure: do not reduce the ceiling without compensating evidence
- a supported limiting-resource shape mismatch
- moderate pressure/no supported bottleneck: avoid churn
- high memory pressure without failure evidence: discuss pressure but do not claim OOM
- explicit failed-run/error evidence when failure claims are evaluated
- a custom YAML threshold and an additional dimension
- relevant repeated applied experience
- conflicting historical experience
- no history / missing metrics
- RCA: grounded SQL / resource failures with cited refs and concrete actions

Unit tests and the offline corpus are a **quality gate**, not proof of production
quality. They catch deterministic regressions. Calibrating score bands against
accepted/applied outcomes is **Quality Phase 2c** (deferred until 2a+2b land).

## 6. Confidence limitations

Current confidence does **not** mean “probability the recommendation is
correct.” It means “the evaluator had enough inputs and checks to judge it.”
Future calibration (Phase 2c) can compare score bands with applied outcomes:

```text
predicted quality band → acceptance rate → applied success rate → performance regression rate
```

That work is tracked separately because it needs real production labels.
