"""Outcome correlation for Quality Phase 2c.

Business purpose
----------------
Join deterministic evaluator scores/confidence (persisted on recommendation
``response.quality``) with RecommendationStore lifecycle statuses
(``accepted`` / ``applied`` / ``rejected`` / …). This is the first calibration
loop toward “production confidence” — not an LLM judge.

Optional scaffolding in ``RecommendationRecord.extra["outcome"]``:
* ``human_label``, ``labeled_by``, ``labeled_at``
* ``rerun_success``, ``rerun_job_run_id``, ``measured_at``

Public API
----------
* ``quality_snapshot`` — extract score band fields from a store record
* ``correlate_recommendation_outcomes`` — band × status contingency report
* ``merge_outcome_extra`` — helper to attach labels / rerun flags into ``extra``
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from edim_dde_ai.recommendations.models import RecommendationRecord


OUTCOME_STATUSES = frozenset({"accepted", "applied", "rejected", "superseded", "proposed"})


@dataclass(frozen=True)
class QualitySnapshot:
    """Normalized quality fields from a recommendation response."""

    score: float | None
    confidence: float | None
    passed: bool | None
    quality_label: str | None
    evaluator: str | None
    dimensions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BandStatusCell:
    """Counts for one (quality_label or band, status) cell."""

    count: int = 0
    scores: list[float] = field(default_factory=list)

    def add(self, score: float | None) -> None:
        self.count += 1
        if score is not None:
            self.scores.append(float(score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "score_mean": (
                sum(self.scores) / len(self.scores) if self.scores else None
            ),
        }


@dataclass
class CorrelationReport:
    """Contingency of quality bands vs lifecycle statuses."""

    agent_id: str | None
    total_records: int
    with_quality: int
    without_quality: int
    by_band_status: dict[str, dict[str, dict[str, Any]]] = field(
        default_factory=dict
    )
    acceptance_by_band: dict[str, dict[str, Any]] = field(default_factory=dict)
    human_labeled: int = 0
    rerun_measured: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "generated_at": self.generated_at,
            "total_records": self.total_records,
            "with_quality": self.with_quality,
            "without_quality": self.without_quality,
            "human_labeled": self.human_labeled,
            "rerun_measured": self.rerun_measured,
            "by_band_status": self.by_band_status,
            "acceptance_by_band": self.acceptance_by_band,
        }


def quality_snapshot(record: RecommendationRecord) -> QualitySnapshot | None:
    """Extract ``response.quality`` when present on a store row."""
    response = record.response or {}
    raw = response.get("quality")
    if not isinstance(raw, dict) or not raw:
        return None
    dims_raw = raw.get("dimensions") or {}
    dimensions = {
        str(k): float(v)
        for k, v in dims_raw.items()
        if isinstance(v, (int, float))
    }
    score = raw.get("score")
    confidence = raw.get("confidence")
    return QualitySnapshot(
        score=float(score) if isinstance(score, (int, float)) else None,
        confidence=(
            float(confidence) if isinstance(confidence, (int, float)) else None
        ),
        passed=bool(raw["passed"]) if "passed" in raw else None,
        quality_label=(
            str(raw.get("quality_label"))
            if raw.get("quality_label") is not None
            else _label_from_score(
                float(score) if isinstance(score, (int, float)) else None
            )
        ),
        evaluator=str(raw["evaluator"]) if raw.get("evaluator") else None,
        dimensions=dimensions,
    )


def _label_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.85:
        return "high"
    if score >= 0.75:
        return "medium"
    return "low"


def correlate_recommendation_outcomes(
    records: Iterable[RecommendationRecord],
    *,
    agent_id: str | None = None,
) -> CorrelationReport:
    """Build band × status counts from recommendation history rows.

    Args:
        records: Store rows (already filtered or full list).
        agent_id: Optional label for the report (filtering is caller's job).

    Returns:
        ``CorrelationReport`` suitable for JSON serialization.
    """
    cells: dict[str, dict[str, BandStatusCell]] = defaultdict(
        lambda: defaultdict(BandStatusCell)
    )
    total = 0
    with_q = 0
    without_q = 0
    human_labeled = 0
    rerun_measured = 0

    for record in records:
        total += 1
        outcome = (record.extra or {}).get("outcome") or {}
        if isinstance(outcome, dict):
            if outcome.get("human_label"):
                human_labeled += 1
            if "rerun_success" in outcome:
                rerun_measured += 1

        snap = quality_snapshot(record)
        if snap is None:
            without_q += 1
            continue
        with_q += 1
        band = snap.quality_label or "unknown"
        status = str(record.status or "proposed").strip().lower()
        cells[band][status].add(snap.score)

    by_band_status = {
        band: {status: cell.to_dict() for status, cell in statuses.items()}
        for band, statuses in cells.items()
    }

    acceptance_by_band: dict[str, dict[str, Any]] = {}
    for band, statuses in cells.items():
        accepted = statuses.get("accepted", BandStatusCell()).count
        applied = statuses.get("applied", BandStatusCell()).count
        rejected = statuses.get("rejected", BandStatusCell()).count
        proposed = statuses.get("proposed", BandStatusCell()).count
        decided = accepted + applied + rejected
        positive = accepted + applied
        acceptance_by_band[band] = {
            "proposed": proposed,
            "accepted": accepted,
            "applied": applied,
            "rejected": rejected,
            "acceptance_rate": (positive / decided) if decided else None,
            "applied_rate": (applied / decided) if decided else None,
        }

    return CorrelationReport(
        agent_id=agent_id,
        total_records=total,
        with_quality=with_q,
        without_quality=without_q,
        by_band_status=by_band_status,
        acceptance_by_band=acceptance_by_band,
        human_labeled=human_labeled,
        rerun_measured=rerun_measured,
    )


def merge_outcome_extra(
    extra: dict[str, Any] | None,
    *,
    human_label: str | None = None,
    labeled_by: str | None = None,
    rerun_success: bool | None = None,
    rerun_job_run_id: str | None = None,
) -> dict[str, Any]:
    """Merge outcome scaffolding into ``RecommendationRecord.extra``.

    Does not mutate the input dict; returns a new mapping.
    """
    out = dict(extra or {})
    outcome = dict(out.get("outcome") or {})
    now = datetime.now(timezone.utc).isoformat()
    if human_label is not None:
        outcome["human_label"] = str(human_label).strip()
        outcome["labeled_at"] = now
        if labeled_by:
            outcome["labeled_by"] = str(labeled_by).strip()
    if rerun_success is not None:
        outcome["rerun_success"] = bool(rerun_success)
        outcome["measured_at"] = now
        if rerun_job_run_id:
            outcome["rerun_job_run_id"] = str(rerun_job_run_id).strip()
    if outcome:
        out["outcome"] = outcome
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI: correlate store quality bands vs accepted/applied statuses."""
    import argparse
    import json
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description=(
            "Correlate response.quality bands with RecommendationStore statuses "
            "(Quality Phase 2c)"
        )
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="Filter agent_id (cluster_tuning | spark_rca)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max rows to scan from the store (default 200)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write JSON report to this path (default: stdout)",
    )
    parser.add_argument(
        "--configure-store",
        action="store_true",
        help="Call configure_recommendation_store_from_env before listing",
    )
    args = parser.parse_args(argv)

    if args.configure_store or os.environ.get("EDIM_RECOMMENDATION_STORE"):
        from edim_dde_ai import configure_recommendation_store_from_env

        configure_recommendation_store_from_env()

    from edim_dde_ai.recommendations import get_recommendation_store

    store = get_recommendation_store()
    records = store.list(agent_id=args.agent, limit=max(1, int(args.limit)))
    report = correlate_recommendation_outcomes(records, agent_id=args.agent)
    text = json.dumps(report.to_dict(), indent=2)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {path}")
    else:
        print(text)
    return 0


__all__ = [
    "OUTCOME_STATUSES",
    "QualitySnapshot",
    "BandStatusCell",
    "CorrelationReport",
    "quality_snapshot",
    "correlate_recommendation_outcomes",
    "merge_outcome_extra",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
