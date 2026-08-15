"""Compose feature-similar and entity-specific RCA history."""

from __future__ import annotations

from typing import Any

from edim_dde_ai.recommendations import get_recommendation_store
from edim_dde_ai.retrieval import search_corpus
from edim_dde_domain.agents.spark_rca.helpers.experience_transform import (
    build_experience_query,
    infer_failure_features,
)


def _experience_block(
    state: dict[str, Any], *, corpus: str, top_k: int
) -> str:
    pack = state.get("evidence_pack")
    hint = state.get("classification_hint")
    current_features = set(
        infer_failure_features(
            evidence_pack=pack if isinstance(pack, dict) else {},
            classification_hint=hint if isinstance(hint, dict) else {},
        )
    )
    strong_current = {
        feature
        for feature in current_features
        if feature.startswith(("hint_category_", "root_category_", "signal_"))
    }
    try:
        hits = search_corpus(
            build_experience_query(state),
            corpus=corpus,
            top_k=top_k,
            search_mode="hybrid",
        )
    except Exception:
        return ""
    # Tiny indexes may return the least-dissimilar document even when unrelated.
    # Require a shared category/signature feature unless semantic similarity is
    # independently very strong.
    hits = [
        hit
        for hit in hits
        if (
            strong_current
            & {
                str(feature)
                for feature in (hit.metadata or {}).get("feature_labels") or []
            }
        )
        or float(hit.score) >= 0.75
    ]
    if not hits:
        return ""
    lines = [
        f"### Similar past RCA outcomes (corpus={corpus}; feature similarity, not job_id)"
    ]
    for index, hit in enumerate(hits, start=1):
        metadata = hit.metadata or {}
        lines.append(
            f"[{index}] score={hit.score:.3f} status={metadata.get('status')} "
            f"job_id={metadata.get('job_id')} job_run_id={metadata.get('job_run_id')} "
            f"occurrences={metadata.get('occurrences', 1)}"
        )
        lines.append(hit.text)
    return "\n".join(lines)


def _same_job_block(state: dict[str, Any], *, limit: int) -> str:
    job_id = str(state.get("job_id") or "").strip()
    job_run_id = str(state.get("job_run_id") or "").strip()
    if not job_id and not job_run_id:
        return ""
    try:
        store = get_recommendation_store()
        if getattr(store, "name", "") == "none":
            return ""
        rows = store.list(
            job_id=job_id or None,
            agent_id="spark_rca",
            limit=max(limit * 3, limit),
        )
    except Exception:
        return ""
    current_request_id = state.get("request_id")
    rows = [
        row
        for row in rows
        if (not current_request_id or row.request_id != current_request_id)
        and (
            (job_run_id and row.job_run_id == job_run_id)
            or (job_id and row.job_id == job_id)
        )
    ][:limit]
    if not rows:
        return ""
    lines = ["### Prior RCA records for this job/run (exact entity history)"]
    for row in rows:
        root = (row.response or {}).get("root_cause") or {}
        lines.append(
            f"- id={row.recommendation_id} status={row.status} "
            f"job_run_id={row.job_run_id} category={root.get('category')} "
            f"signature={root.get('failure_signature')} "
            f"summary={str(root.get('summary') or '')[:300]}"
        )
    return "\n".join(lines)


def compose_historical_context(
    state: dict[str, Any],
    *,
    enabled: bool = True,
    corpus: str = "spark-rca-outcomes",
    top_k: int = 5,
    same_job_limit: int = 3,
) -> str:
    """Return separate similarity and exact-entity history lanes."""
    if not enabled:
        return "None"
    blocks = [
        _experience_block(state, corpus=corpus, top_k=max(1, top_k)),
        _same_job_block(state, limit=max(1, same_job_limit)),
    ]
    return "\n\n".join(block for block in blocks if block) or "None"
