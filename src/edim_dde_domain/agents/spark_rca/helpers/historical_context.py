"""Compose secondary historical context for the Spark RCA LLM prompt.

Business purpose
----------------
Live ``evidence_pack`` is always authoritative. This module builds an optional
**secondary** prompt block with two independent lanes:

1. **Experience similarity (B′)** — hybrid search over ``spark-rca-outcomes``
   using open failure features (see ``experience_transform``). Cross-job.
2. **Exact entity shelf (B)** — ``RecommendationStore.list(agent_id=spark_rca)``
   filtered to the same ``job_id`` / ``job_run_id``. Includes ``proposed``.

Runbooks stay in a separate prompt field (``runbook_context``); this module does
not merge playbooks into the history string.

Failure modes
-------------
Any retrieval / store error is swallowed → empty lane. If both lanes are empty,
callers receive the literal ``\"None\"`` so the prompt stays well-formed and the
request never fails for missing history.

Public API
----------
* ``compose_historical_context`` — entry used by ``logic.load_historical_context``

YAML knobs (on ``domain.rca.load_historical_context``) typically include
``enabled``, ``corpus``, ``top_k``, ``same_job_limit``.
"""

from __future__ import annotations

from typing import Any

from edim_dde_ai.recommendations import get_recommendation_store
from edim_dde_ai.retrieval import search_corpus
from edim_dde_domain.agents.spark_rca.helpers.experience_transform import (
    build_experience_query,
    infer_failure_features,
)


def _experience_block(
    state: dict[str, Any],
    *,
    corpus: str,
    top_k: int,
    failure_signals_config: dict[str, Any] | None = None,
) -> str:
    """Retrieve and format feature-similar past RCA experience cards.

    Tiny indexes can return weakly related neighbors. We therefore require either:

    * shared strong feature labels (category / ``signal_`` / exception / plan), or
    * an independently high similarity score (≥ 0.75).

    Args:
        state: Live graph state (evidence_pack, classification_hint).
        corpus: Outcomes corpus name (default ``spark-rca-outcomes``).
        top_k: Max hits to request from the retrieval provider.
        failure_signals_config: Optional YAML extractors for query features.

    Returns:
        Markdown-ish block string, or ``\"\"`` when nothing useful matches.
    """
    pack = state.get("evidence_pack")
    hint = state.get("classification_hint")
    current_features = set(
        infer_failure_features(
            evidence_pack=pack if isinstance(pack, dict) else {},
            classification_hint=hint if isinstance(hint, dict) else {},
            failure_signals_config=failure_signals_config,
        )
    )
    # Category + signature tokens are the only features we treat as "strong"
    # enough to justify a low-score hit from a cold / tiny index.
    strong_current = {
        feature
        for feature in current_features
        if feature.startswith(
            (
                "hint_category_",
                "root_category_",
                "signal_",
                "exception_class_",
                "plan_op_",
            )
        )
    }
    try:
        hits = search_corpus(
            build_experience_query(
                state, failure_signals_config=failure_signals_config
            ),
            corpus=corpus,
            top_k=top_k,
            search_mode="hybrid",
        )
    except Exception:
        # History is secondary — never fail the RCA request for retrieval errors.
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
    """List prior RCA store rows for the same job and/or job run.

    Unlike the experience corpus, this shelf includes ``proposed`` diagnoses so
    engineers see what the agent already suggested for this entity.

    Args:
        state: Must carry ``job_id`` and/or ``job_run_id`` (and optional
            ``request_id`` to skip the in-flight row).
        limit: Max rows to render after filtering.

    Returns:
        Markdown list block, or ``\"\"`` when store is ``none`` / empty / errors.
    """
    job_id = str(state.get("job_id") or "").strip()
    job_run_id = str(state.get("job_run_id") or "").strip()
    if not job_id and not job_run_id:
        return ""
    try:
        store = get_recommendation_store()
        if getattr(store, "name", "") == "none":
            return ""
        # Over-fetch then filter: store list may only key on job_id today.
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
    failure_signals_config: dict[str, Any] | None = None,
) -> str:
    """Return separate similarity and exact-entity history lanes for the prompt.

    Args:
        state: Live RCA graph state.
        enabled: When false, skip all work and return ``\"None\"``.
        corpus: Experience corpus (must exist in ``config/corpora.yaml``).
        top_k: Max experience hits after filtering.
        same_job_limit: Max exact entity rows to show.
        failure_signals_config: Optional YAML signal extractors for experience query.

    Returns:
        Combined history text, or ``\"None\"`` when disabled / empty.
    """
    if not enabled:
        return "None"
    blocks = [
        _experience_block(
            state,
            corpus=corpus,
            top_k=max(1, top_k),
            failure_signals_config=failure_signals_config,
        ),
        _same_job_block(state, limit=max(1, same_job_limit)),
    ]
    return "\n\n".join(block for block in blocks if block) or "None"
