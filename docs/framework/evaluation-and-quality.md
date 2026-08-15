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

## 4. How to prove a prompt improved quality

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

## 5. Confidence limitations

Current confidence does **not** mean “probability the recommendation is
correct.” It means “the evaluator had enough inputs and checks to judge it.”
Future calibration can compare score bands with applied outcomes:

```text
predicted quality band → acceptance rate → applied success rate → performance regression rate
```

That work is tracked separately because it needs real production labels.
