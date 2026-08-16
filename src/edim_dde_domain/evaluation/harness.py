"""Unified Foundry quality harness (Quality Phase 2b).

Business purpose
----------------
Run the versioned golden corpus for **both** ``cluster_tuning`` and
``spark_rca`` under a real Foundry LLM (or offline score-only mode), repeat
trials, and persist scores / dimensions / latency / token metadata for
before/after prompt comparisons.

CLI
---
``python -m edim_dde_domain.evaluation.harness --corpus v1 --trials 3``

Public API
----------
* ``TrialResult`` / ``HarnessReport``
* ``run_harness`` / ``score_corpus_offline``
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edim_dde_ai.evaluation import EvaluationResult, evaluate

from edim_dde_domain.evaluation.corpus import (
    QualityCase,
    QualityCorpus,
    default_corpus_root,
    load_quality_corpus,
)


@dataclass
class TrialResult:
    """One trial of one case."""

    case_id: str
    agent_id: str
    trial: int
    mode: str
    passed: bool
    score: float
    confidence: float
    dimensions: dict[str, float] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    expectation_failures: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HarnessReport:
    """Aggregate harness output for one run."""

    corpus_version: str
    started_at: str
    finished_at: str
    trials: int
    agents: list[str]
    git_sha: str | None
    foundry_endpoint: str | None
    foundry_deployment: str | None
    results: list[TrialResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_version": self.corpus_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "trials": self.trials,
            "agents": self.agents,
            "git_sha": self.git_sha,
            "foundry_endpoint": self.foundry_endpoint,
            "foundry_deployment": self.foundry_deployment,
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> dict[str, Any]:
        by_case: dict[str, list[TrialResult]] = {}
        for row in self.results:
            by_case.setdefault(row.case_id, []).append(row)
        cases = {}
        for case_id, rows in by_case.items():
            ok = [r for r in rows if r.error is None]
            passed = [r for r in ok if r.passed and not r.expectation_failures]
            scores = [r.score for r in ok]
            cases[case_id] = {
                "agent_id": rows[0].agent_id if rows else None,
                "trials": len(rows),
                "errors": sum(1 for r in rows if r.error),
                "pass_count": len(passed),
                "pass_rate": (len(passed) / len(ok)) if ok else 0.0,
                "score_mean": (sum(scores) / len(scores)) if scores else None,
                "score_min": min(scores) if scores else None,
                "score_max": max(scores) if scores else None,
            }
        return {"cases": cases}


def score_corpus_offline(
    corpus: QualityCorpus,
    *,
    agents: list[str] | None = None,
) -> list[TrialResult]:
    """Score every ``score_output`` case once (no Foundry). Trial index = 1."""
    rows: list[TrialResult] = []
    for case in corpus.cases_for(agents=agents):
        rows.append(_score_case(case, trial=1, mode="score_output"))
    return rows


def run_harness(
    corpus: QualityCorpus,
    *,
    trials: int | None = None,
    agents: list[str] | None = None,
    live: bool = False,
    bootstrap: bool = True,
) -> HarnessReport:
    """Run the corpus: offline score fixtures, or live agent invoke + score.

    Args:
        corpus: Loaded quality corpus.
        trials: Repeats per case (default from manifest). Live mode only
            repeats; offline always runs once per case unless ``trials`` > 1
            (then fixtures are re-scored identically for report shape parity).
        agents: Optional agent filter.
        live: When true, ``invoke_agent`` / bootstrap Foundry path.
        bootstrap: Call ``bootstrap_agents()`` when live.

    Returns:
        ``HarnessReport`` ready to serialize.
    """
    n_trials = int(trials if trials is not None else corpus.default_trials)
    n_trials = max(1, n_trials)
    started = _utc_now()
    selected = corpus.cases_for(agents=agents)
    agent_ids = sorted({c.agent_id for c in selected})

    if live and bootstrap:
        from edim_dde_domain.bootstrap import bootstrap_agents

        bootstrap_agents()
        _ensure_foundry_provider()

    results: list[TrialResult] = []
    for case in selected:
        for trial in range(1, n_trials + 1):
            if live:
                results.append(_live_trial(case, trial=trial))
            else:
                results.append(
                    _score_case(case, trial=trial, mode="score_output")
                )

    return HarnessReport(
        corpus_version=corpus.version,
        started_at=started,
        finished_at=_utc_now(),
        trials=n_trials,
        agents=agent_ids,
        git_sha=os.environ.get("EDIM_GIT_SHA") or os.environ.get("GITHUB_SHA"),
        foundry_endpoint=_first_env(
            "EDIM_FOUNDRY_ENDPOINT",
            "AZURE_OPENAI_ENDPOINT",
        ),
        foundry_deployment=_first_env(
            "EDIM_FOUNDRY_DEPLOYMENT",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
        ),
        results=results,
    )


def _score_case(case: QualityCase, *, trial: int, mode: str) -> TrialResult:
    t0 = time.perf_counter()
    try:
        result = case.score()
        failures = case.check_expectations(result)
        return _from_eval(
            case,
            trial=trial,
            mode=mode,
            result=result,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            expectation_failures=failures,
        )
    except Exception as exc:  # noqa: BLE001 — harness must record failures
        return TrialResult(
            case_id=case.case_id,
            agent_id=case.agent_id,
            trial=trial,
            mode=mode,
            passed=False,
            score=0.0,
            confidence=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            error=f"{type(exc).__name__}: {exc}",
        )


def _live_trial(case: QualityCase, *, trial: int) -> TrialResult:
    """Invoke the agent (or score fixture when no invoke_input) then evaluate."""
    from edim_dde_ai import create_agent

    t0 = time.perf_counter()
    mode = "invoke_agent"
    try:
        if case.invoke_input is not None:
            out = create_agent(case.agent_id).invoke(dict(case.invoke_input))
            output, inputs, context = _extract_eval_payload(case, out)
            result = evaluate(
                case.evaluator,
                inputs=inputs,
                output=output,
                context=context,
            )
        elif case.output is not None:
            # Fixture-only case still allowed in live runs for regression shape.
            mode = "score_output"
            result = case.score()
        else:
            raise ValueError(
                f"case {case.case_id}: live mode needs invoke_input or output"
            )
        failures = case.check_expectations(result)
        return _from_eval(
            case,
            trial=trial,
            mode=mode,
            result=result,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            expectation_failures=failures,
            metadata={"live": True},
        )
    except Exception as exc:  # noqa: BLE001
        return TrialResult(
            case_id=case.case_id,
            agent_id=case.agent_id,
            trial=trial,
            mode=mode,
            passed=False,
            score=0.0,
            confidence=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            error=f"{type(exc).__name__}: {exc}",
            metadata={"live": True},
        )


def _extract_eval_payload(
    case: QualityCase, out: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Map agent invoke state into evaluator inputs/output/context."""
    if case.agent_id == "cluster_tuning":
        output = {
            "recommendation": out.get("recommendation") or out.get("result") or out
        }
        if "recommendation" in out:
            output = {"recommendation": out["recommendation"]}
        inputs = {"metrics": out.get("metrics") or case.inputs.get("metrics") or {}}
        context = {
            "historical_context": out.get("historical_context")
            or (case.context or {}).get("historical_context")
        }
        return output, inputs, context

    # spark_rca
    result = out.get("result") or out
    output = dict(result) if isinstance(result, dict) else {"result": result}
    inputs = {
        "evidence_pack": out.get("evidence_pack")
        or case.inputs.get("evidence_pack")
        or {}
    }
    context = {
        "web_search_context": out.get("web_search_context"),
    }
    return output, inputs, context


def _from_eval(
    case: QualityCase,
    *,
    trial: int,
    mode: str,
    result: EvaluationResult,
    latency_ms: float,
    expectation_failures: list[str],
    metadata: dict[str, Any] | None = None,
) -> TrialResult:
    meta = dict(result.metadata or {})
    if metadata:
        meta.update(metadata)
    return TrialResult(
        case_id=case.case_id,
        agent_id=case.agent_id,
        trial=trial,
        mode=mode,
        passed=bool(result.passed) and not expectation_failures,
        score=float(result.score),
        confidence=float(result.confidence),
        dimensions={k: float(v) for k, v in (result.dimensions or {}).items()},
        findings=list(result.findings or []),
        latency_ms=latency_ms,
        expectation_failures=list(expectation_failures),
        metadata=meta,
    )


def _ensure_foundry_provider() -> None:
    """Install Foundry LLM when env is present (no-op if already set)."""
    from edim_dde_ai.content import get_llm_provider, set_llm_provider

    try:
        current = get_llm_provider()
        if current is not None and getattr(current, "name", "") == "foundry":
            return
    except Exception:  # noqa: BLE001
        pass
    from edim_dde_domain.llm.foundry import FoundryLLMProvider

    set_llm_provider(FoundryLLMProvider())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_env(*keys: str) -> str | None:
    for key in keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return None


def main(argv: list[str] | None = None) -> int:
    """CLI entry for Quality Phase 2b harness."""
    parser = argparse.ArgumentParser(
        description="EDIM quality harness (tuning + RCA corpus)"
    )
    parser.add_argument(
        "--corpus",
        default="v1",
        help="Corpus version under testdata/quality/ (default: v1)",
    )
    parser.add_argument(
        "--corpus-root",
        default=None,
        help="Explicit corpus directory (overrides --corpus)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="Trials per case (default: manifest default_trials)",
    )
    parser.add_argument(
        "--agents",
        default="cluster_tuning,spark_rca",
        help="Comma-separated agent ids",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Invoke agents with Foundry (default: offline score fixtures)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write JSON report to this path",
    )
    args = parser.parse_args(argv)

    root = Path(args.corpus_root) if args.corpus_root else default_corpus_root(args.corpus)
    # Register evaluators without full agent graphs for offline mode.
    if not args.live:
        from edim_dde_domain.evaluation.cluster_tuning import (
            register_cluster_tuning_evaluator,
        )
        from edim_dde_domain.evaluation.spark_rca import register_spark_rca_evaluator

        register_cluster_tuning_evaluator()
        register_spark_rca_evaluator()

    corpus = load_quality_corpus(root)
    agents = [a.strip() for a in str(args.agents).split(",") if a.strip()]
    report = run_harness(
        corpus,
        trials=args.trials,
        agents=agents,
        live=bool(args.live),
        bootstrap=bool(args.live),
    )

    payload = report.to_dict()
    text = json.dumps(payload, indent=2, sort_keys=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
    else:
        print(text)

    # Non-zero when any trial failed expectations / errored.
    failed = [
        r
        for r in report.results
        if r.error or r.expectation_failures or not r.passed
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
