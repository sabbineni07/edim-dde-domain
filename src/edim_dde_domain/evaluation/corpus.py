"""Load versioned quality golden corpora (Quality Phase 2a).

Business purpose
----------------
Release-quality cases live under ``testdata/quality/<version>/`` with a
``manifest.yaml`` and per-agent JSON files. Offline pytest and the Foundry
harness share the same loader so rubric gates and live trials stay aligned.

Public API
----------
* ``QualityCase`` — one scored case
* ``QualityCorpus`` — manifest + cases
* ``default_corpus_root`` / ``load_quality_corpus``
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from edim_dde_ai.evaluation import EvaluationResult, evaluate


@dataclass(frozen=True)
class QualityCase:
    """One golden / harness case.

    Attributes:
        case_id: Stable id (matches filename stem and manifest entry).
        agent_id: ``cluster_tuning`` or ``spark_rca``.
        evaluator: Registry name (e.g. ``cluster_tuning.quality``).
        mode: ``score_output`` (offline fixture) or ``invoke_agent`` (live).
        description: Human summary.
        inputs: Evaluator / agent inputs.
        context: Optional evaluator context.
        output: Precomputed agent output for ``score_output`` mode.
        expectations: ``passed``, ``min_score``, optional dimension floors.
        tags: Free-form labels from the case file or manifest.
        invoke_input: Flat state for ``invoke_agent`` mode (optional).
    """

    case_id: str
    agent_id: str
    evaluator: str
    mode: str
    description: str
    inputs: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    expectations: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    invoke_input: dict[str, Any] | None = None

    def score(self) -> EvaluationResult:
        """Run the registered evaluator against ``output`` (offline gate)."""
        if self.output is None:
            raise ValueError(
                f"case {self.case_id}: mode=score_output requires an output fixture"
            )
        return evaluate(
            self.evaluator,
            inputs=self.inputs,
            output=self.output,
            context=self.context or None,
        )

    def check_expectations(self, result: EvaluationResult) -> list[str]:
        """Return human-readable expectation failures (empty = ok)."""
        failures: list[str] = []
        exp = self.expectations or {}
        if "passed" in exp and bool(result.passed) != bool(exp["passed"]):
            failures.append(
                f"passed={result.passed} expected={exp['passed']}"
            )
        min_score = exp.get("min_score")
        if min_score is not None and float(result.score) < float(min_score):
            failures.append(
                f"score={result.score:.3f} < min_score={min_score}"
            )
        for dim, floor in (exp.get("min_dimensions") or {}).items():
            actual = float((result.dimensions or {}).get(dim, 0.0))
            if actual < float(floor):
                failures.append(
                    f"dimension {dim}={actual:.3f} < {floor}"
                )
        return failures


@dataclass(frozen=True)
class QualityCorpus:
    """Loaded manifest + cases for one corpus version."""

    version: str
    root: Path
    default_trials: int
    cases: tuple[QualityCase, ...]
    raw_manifest: dict[str, Any]

    def cases_for(
        self, *, agents: list[str] | None = None, tags: list[str] | None = None
    ) -> list[QualityCase]:
        """Filter cases by agent id and/or tag intersection."""
        selected = list(self.cases)
        if agents:
            allow = {a.strip() for a in agents if a.strip()}
            selected = [c for c in selected if c.agent_id in allow]
        if tags:
            want = {t.strip() for t in tags if t.strip()}
            selected = [c for c in selected if want.intersection(c.tags)]
        return selected


def default_corpus_root(version: str = "v1") -> Path:
    """Return ``edim-dde-domain/testdata/quality/<version>`` next to the package."""
    # src/edim_dde_domain/evaluation/corpus.py → domain root → testdata
    domain_root = Path(__file__).resolve().parents[3]
    return domain_root / "testdata" / "quality" / version


def load_quality_corpus(
    root: Path | str | None = None, *, version: str = "v1"
) -> QualityCorpus:
    """Load manifest + case JSON files for a corpus version.

    Args:
        root: Explicit corpus directory (must contain ``manifest.yaml``).
        version: Used when ``root`` is omitted (``testdata/quality/<version>``).

    Returns:
        ``QualityCorpus`` with all listed cases loaded.

    Raises:
        FileNotFoundError: Missing manifest or case file.
        ValueError: Manifest / case shape errors.
    """
    corpus_root = Path(root) if root else default_corpus_root(version)
    manifest_path = corpus_root / "manifest.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"quality corpus manifest not found: {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path}: root must be a mapping")

    agents_cfg = raw.get("agents") or {}
    if not isinstance(agents_cfg, dict):
        raise ValueError(f"{manifest_path}: agents must be a mapping")

    case_entries = raw.get("cases") or []
    if not isinstance(case_entries, list) or not case_entries:
        raise ValueError(f"{manifest_path}: cases must be a non-empty list")

    loaded: list[QualityCase] = []
    for entry in case_entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{manifest_path}: each case entry must be a mapping")
        case_id = str(entry.get("id") or "").strip()
        agent_id = str(entry.get("agent") or "").strip()
        if not case_id or not agent_id:
            raise ValueError(f"{manifest_path}: case entries need id + agent")
        agent_meta = agents_cfg.get(agent_id) or {}
        if not isinstance(agent_meta, dict):
            raise ValueError(f"{manifest_path}: agents.{agent_id} must be a mapping")
        evaluator = str(agent_meta.get("evaluator") or "").strip()
        cases_dir = str(agent_meta.get("cases_dir") or agent_id).strip()
        if not evaluator:
            raise ValueError(
                f"{manifest_path}: agents.{agent_id}.evaluator is required"
            )
        case_path = corpus_root / cases_dir / f"{case_id}.json"
        if not case_path.is_file():
            raise FileNotFoundError(f"quality case file not found: {case_path}")
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{case_path}: root must be a JSON object")

        tags = tuple(
            str(t)
            for t in (entry.get("tags") or payload.get("tags") or [])
            if str(t).strip()
        )
        loaded.append(
            QualityCase(
                case_id=case_id,
                agent_id=agent_id,
                evaluator=evaluator,
                mode=str(payload.get("mode") or "score_output").strip(),
                description=str(payload.get("description") or "").strip(),
                inputs=dict(payload.get("inputs") or {}),
                context=dict(payload.get("context") or {}),
                output=(
                    dict(payload["output"])
                    if isinstance(payload.get("output"), dict)
                    else None
                ),
                expectations=dict(payload.get("expectations") or {}),
                tags=tags,
                invoke_input=(
                    dict(payload["invoke_input"])
                    if isinstance(payload.get("invoke_input"), dict)
                    else None
                ),
            )
        )

    return QualityCorpus(
        version=str(raw.get("version") or version),
        root=corpus_root,
        default_trials=int(raw.get("default_trials") or 3),
        cases=tuple(loaded),
        raw_manifest=raw,
    )


__all__ = [
    "QualityCase",
    "QualityCorpus",
    "default_corpus_root",
    "load_quality_corpus",
]
