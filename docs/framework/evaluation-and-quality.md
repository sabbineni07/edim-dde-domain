# Evaluation, quality, and confidence

**Learning path:** D6 · [Guide home](../README.md)

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
    against accepted/applied outcomes is Phase 2 work (see backlog).

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

## 5. How to prove a prompt improved quality

Use the same **golden cases**, model/deployment, temperature, and retrieval
snapshot before and after:

1. Run each case multiple times when the model is non-deterministic.
2. Record overall and dimension scores, guardrail retries/clamps, latency and
   token/cost data.
3. Require no regression on contract/safety and an agreed lift in evidence,
   direction and history dimensions.
4. Human-review borderline cases and every changed recommendation.
5. Promote only after a live shadow/canary run confirms offline direction.

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

Unit tests are a **quality gate**, not proof of production quality. They catch
deterministic regressions. A calibrated production score requires labeled
outcomes (accepted/applied, post-change success, no regression) and periodic
human review.

## 6. Confidence limitations

Current confidence does **not** mean “probability the recommendation is
correct.” It means “the evaluator had enough inputs and checks to judge it.”
Future calibration can compare score bands with applied outcomes:

```text
predicted quality band → acceptance rate → applied success rate → performance regression rate
```

That work is tracked separately because it needs real production labels.
