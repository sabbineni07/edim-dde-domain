"""Spark RCA graph business logic (pure state → state patches).

Business purpose
----------------
Each public function here is the body of a ``domain.rca.*`` LangGraph node
(see ``nodes.py``). Together they implement the product pipeline::

    SQL collectors (framework) → assemble_evidence → classify_failure
      → load_historical_context → build_web_search_query → web.search (builtin)
      → build_retrieval_query → rag.retrieve (runbooks)
      → prepare_llm_payload → synthesize (llm_chain)
      → parse_llm_json → validate_output → evaluate_output → END

    Session follow-ups (checkpoint-backed):
      converse   → prepare_explanation_payload → generate_explanation → END
      regenerate → prepare_llm_payload → synthesize → … → END

Authoritative signal is always the live ``evidence_pack``. History, runbooks,
and optional web search are **secondary** context lanes and must never block
the request when empty or when providers fail.

SQL collection itself lives in ``domain.sql.query`` nodes configured in
``spark_rca.agent.yaml``; this module only assembles / classifies / prepares /
validates around those rows.

Public entry points mirror node type ids without the ``domain.rca.`` prefix.
"""

from __future__ import annotations

from typing import Any

from edim_dde_domain.agents.spark_rca.helpers.classify import classify_failure_pack
from edim_dde_domain.agents.spark_rca.helpers.evidence_pack import build_evidence_pack
from edim_dde_domain.agents.spark_rca.helpers.experience_transform import (
    infer_failure_features,
)
from edim_dde_domain.agents.spark_rca.helpers.historical_context import (
    compose_historical_context,
)
from edim_dde_domain.agents.spark_rca.helpers.validate import validate_rca_llm_output
from edim_dde_domain.llm.json_util import dumps, parse_json_object


def _seed_from_rows(rows: list[Any], *keys: str) -> str | None:
    """Pick the first non-empty value for any of ``keys`` across SQL result rows.

    Used when the HTTP request omitted ``job_id`` / ``task_key`` but collectors
    returned them on telemetry rows.

    Args:
        rows: List of dict-like SQL rows.
        *keys: Candidate field names in priority order per row.

    Returns:
        First non-empty string value found, else ``None``.
    """
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in keys:
            val = row.get(key)
            if val not in (None, ""):
                return str(val)
    return None


def assemble_evidence(state: dict[str, Any]) -> dict[str, Any]:
    """Build ``evidence_pack`` from SQL section outputs (or keep override/stub).

    When the client already supplied a non-empty ``evidence_pack``, collectors
    are skipped by YAML ``skip_if_key`` and this node returns ``{}`` (no-op merge)
    so the override is preserved.

    Args:
        state: Graph state after optional SQL collect nodes. Expected keys when
            building from SQL: ``failure_anchors``, ``stage_pressure``,
            ``error_logs``, ``timeline_events``, ``sql_plans``, ``job_run_id``.

    Returns:
        Patch with ``evidence_pack`` and optionally seeded ``job_id`` /
        ``job_run_date`` / ``task_key``. Empty dict when override present.
    """
    existing = state.get("evidence_pack")
    if isinstance(existing, dict) and existing:
        return {}

    failure_anchors = list(state.get("failure_anchors") or [])
    sql_plans = list(state.get("sql_plans") or [])
    seed_rows = failure_anchors + sql_plans + list(state.get("timeline_events") or [])

    job_id = state.get("job_id") or _seed_from_rows(seed_rows, "job_id")
    job_run_date = state.get("job_run_date") or _seed_from_rows(
        seed_rows, "job_run_date"
    )
    task_key = state.get("task_key") or _seed_from_rows(seed_rows, "task_key")
    workspace_id = state.get("workspace_id") or _seed_from_rows(
        seed_rows, "workspace_id"
    )

    pack = build_evidence_pack(
        job_run_id=str(state.get("job_run_id") or "unknown-run"),
        job_id=job_id,
        job_run_date=job_run_date,
        task_key=task_key,
        workspace_id=workspace_id,
        failure_anchors=failure_anchors,
        stage_pressure=list(state.get("stage_pressure") or []),
        error_logs=list(state.get("error_logs") or []),
        timeline=list(state.get("timeline_events") or []),
        sql_plans=sql_plans,
    )
    out: dict[str, Any] = {"evidence_pack": pack}
    # Surface seeded ids onto state for API / later nodes
    if job_id and not state.get("job_id"):
        out["job_id"] = job_id
    if job_run_date and not state.get("job_run_date"):
        out["job_run_date"] = job_run_date
    if task_key and not state.get("task_key"):
        out["task_key"] = task_key
    return out


def classify_failure(
    state: dict[str, Any], *, signal_groups: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Config-seeded broad category hint from evidence pack.

    Args:
        state: Must include ``evidence_pack``; optional ``error_text`` is folded
            into a temporary view for regex matching only.
        signal_groups: YAML-configured ordered pattern groups (see classify.py).

    Returns:
        ``{\"classification_hint\": {...}}``.
    """
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}
    # Include optional request error_text without mutating the pack permanently
    view = dict(pack)
    if state.get("error_text"):
        view["_error_text"] = state.get("error_text")
    return {
        "classification_hint": classify_failure_pack(
            view, signal_groups=signal_groups
        )
    }


def build_retrieval_query(state: dict[str, Any]) -> dict[str, Any]:
    """Build a free-text query for **runbook** similarity search (not experiences).

    Experience queries are feature-based and live in ``historical_context``;
    polluting runbook search with outcome-card phrasing would mix lanes.

    Args:
        state: ``evidence_pack`` + ``classification_hint``.

    Returns:
        ``{\"retrieval_query\": \"...\"}`` for the subsequent ``rag.retrieve`` node.
    """
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}
    hint = state.get("classification_hint") or {}
    reason = str((pack.get("raw_anchors") or {}).get("failure_reason") or "")
    category = str(hint.get("category") or "")
    excerpts: list[str] = []
    for item in (pack.get("evidence") or [])[:5]:
        if isinstance(item, dict) and item.get("excerpt"):
            excerpts.append(str(item["excerpt"])[:400])
    parts = [p for p in [category, reason, *excerpts] if p and p.strip()]
    query = "\n".join(parts).strip() or category or "spark job failure"
    return {"retrieval_query": query}


def load_historical_context(
    state: dict[str, Any], *, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Compose experience + same-job history into ``historical_context``.

    Args:
        state: Live graph state.
        config: Node YAML knobs — ``enabled``, ``corpus``, ``top_k``,
            ``same_job_limit``, optional ``failure_signals``.

    Returns:
        ``{\"historical_context\": \"...\"}`` (may be the literal ``\"None\"``).
    """
    policy = config or {}
    failure_signals = policy.get("failure_signals")
    return {
        "historical_context": compose_historical_context(
            state,
            enabled=bool(policy.get("enabled", True)),
            corpus=str(policy.get("corpus") or "spark-rca-outcomes"),
            top_k=int(policy.get("top_k", 5)),
            same_job_limit=int(policy.get("same_job_limit", 3)),
            failure_signals_config=(
                dict(failure_signals) if isinstance(failure_signals, dict) else None
            ),
        )
    }


def build_web_search_query(
    state: dict[str, Any], *, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a PII-safe online query only when configured policy triggers.

    Raw log excerpts, IDs, table names, paths, SQL, and user text are never sent.
    The query consists only of bounded technical feature tokens already derived
    from the evidence pack, plus a fixed remediation preamble. Empty string
    disables the downstream ``web.search`` node effectively (provider no-ops).

    Args:
        state: ``classification_hint`` + ``evidence_pack``.
        config: YAML policy — ``enabled`` (default false), ``trigger``,
            ``confidence_below``.

    Returns:
        ``{\"web_search_query\": \"...\"}`` or empty string when skipped.

    Example:
        With ``enabled: false`` (default in agent YAML)::

            >>> build_web_search_query(state, config={\"enabled\": False})
            {'web_search_query': ''}
    """
    policy = config or {}
    if not bool(policy.get("enabled", False)):
        return {"web_search_query": ""}
    hint = state.get("classification_hint")
    if not isinstance(hint, dict):
        hint = {}
    confidence = float(hint.get("confidence") or 0.0)
    category = str(hint.get("category") or "unknown")
    trigger = str(policy.get("trigger") or "low_confidence_or_unknown")
    threshold = float(policy.get("confidence_below", 0.55))
    should_search = (
        trigger == "always"
        or category == "unknown"
        or confidence < threshold
    )
    if not should_search:
        return {"web_search_query": ""}
    pack = state.get("evidence_pack")
    if not isinstance(pack, dict):
        pack = {}
    features = infer_failure_features(
        evidence_pack=pack,
        classification_hint=hint,
    )
    safe_tokens = []
    for feature in features:
        if not feature.startswith("signal_"):
            continue
        token = feature.removeprefix("signal_")
        # Only exception/failure class-like tokens are safe for public egress.
        # Paths, table names, IDs, and ordinary words are intentionally dropped.
        if token.endswith(("error", "exception", "failure", "timeout")):
            safe_tokens.append(token)
        if len(safe_tokens) >= 8:
            break
    query = " ".join(
        [
            "Databricks Apache Spark job failure root cause remediation",
            category if category != "unknown" else "",
            *safe_tokens,
        ]
    ).strip()
    # Defense in depth: scrub residual PII patterns even from class-like tokens.
    try:
        from edim_dde_domain.security.pii import redact_text

        query = redact_text(query)
    except Exception:  # noqa: BLE001
        pass
    return {"web_search_query": query}


def _section_text(section: Any, empty_message: str) -> str:
    """Serialize a section dict for the human prompt, or an empty placeholder."""
    if not section:
        return empty_message
    if isinstance(section, dict) and not any(section.values()):
        return empty_message
    return dumps(section)


def prepare_llm_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Flatten evidence + classification into RCA human-prompt string fields.

    Keys ending in ``_text`` / ``_section`` are intentional so they do not
    overwrite structured state fields like ``classification_hint`` /
    ``evidence_pack`` when the graph merges the patch.

    Args:
        state: Post-retrieval state including optional ``runbook_context``,
            ``historical_context``, ``web_search_context``.

    Returns:
        Dict of string fields consumed by ``content/prompts/rca.human.md``.
    """
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}
    sections = pack.get("sections") or {}
    hint = state.get("classification_hint") or {}
    runbook_context = state.get("runbook_context") or state.get("retrieval_context")
    historical_context = state.get("historical_context")
    web_search_context = state.get("web_search_context")

    def _s(value: Any) -> str:
        return "(not provided)" if value is None or value == "" else str(value)

    return {
        "workspace_id": _s(state.get("workspace_id") or pack.get("workspace_id")),
        "job_id": _s(state.get("job_id") or pack.get("job_id")),
        "job_run_id": _s(state.get("job_run_id") or pack.get("job_run_id")),
        "job_run_date": _s(state.get("job_run_date") or pack.get("job_run_date")),
        "task_key": _s(state.get("task_key") or pack.get("task_key")),
        # Non-colliding keys so dict classification_hint / evidence_pack stay intact
        "classification_hint_text": dumps(hint) if hint else "(none)",
        "cluster_logs_section": _section_text(
            sections.get("logs"),
            "(no ERROR/WARN/exception excerpts in this evidence_pack)",
        ),
        "spark_metrics_section": _section_text(
            sections.get("stage_metrics"),
            "(no stage/task metric excerpts in this evidence_pack)",
        ),
        "query_plans_section": _section_text(
            sections.get("sql_plans"),
            "(no sql_text/physical_plan/sql_error attrs in this evidence_pack)",
        ),
        "evidence_pack_text": dumps(pack),
        "runbook_context": _s(runbook_context)
        if runbook_context
        else "(no runbook hits retrieved — retrieval disabled or empty index)",
        "historical_context": _s(historical_context)
        if historical_context and historical_context != "None"
        else "(no prior RCA history retrieved)",
        "web_search_context": _s(web_search_context)
        if web_search_context
        else "(web search disabled, not triggered, unavailable, or empty)",
    }


def prepare_explanation_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Stringify the completed RCA result for the explanation follow-up chain.

    Used by the session ``converse`` path so engineers can ask clarifying
    questions against the same evidence and diagnosis without re-running SQL.

    Args:
        state: Checkpointed state after initialize (``result``, ``evidence_pack``,
            optional ``conversation_context``, history / runbook context).

    Returns:
        Prompt field patch for ``content/prompts/explanation.human.md``.
    """
    result = state.get("result")
    if not isinstance(result, dict):
        result = {}
    pack = state.get("evidence_pack")
    if not isinstance(pack, dict):
        pack = {}
    history = str(state.get("historical_context") or "")
    if len(history) > 3000:
        history = history[:2980] + "\n…[truncated]"
    runbooks = str(state.get("runbook_context") or "")
    if len(runbooks) > 2000:
        runbooks = runbooks[:1980] + "\n…[truncated]"
    conversation = str(state.get("conversation_context") or "").strip()
    user_message = str(
        state.get("user_message") or state.get("message") or ""
    ).strip()
    return {
        "result_text": dumps(result) if result else "(no prior RCA result on session)",
        "evidence_pack_text": dumps(pack) if pack else "(no evidence_pack on session)",
        "classification_hint_text": dumps(state.get("classification_hint") or {})
        if state.get("classification_hint")
        else "(none)",
        "historical_context": history or "(no prior RCA history retrieved)",
        "runbook_context": runbooks
        or "(no runbook hits retrieved — retrieval disabled or empty index)",
        "conversation_context": conversation or "(no prior conversation messages)",
        "user_question": user_message or "(no follow-up question provided)",
    }


def parse_llm_json(state: dict[str, Any]) -> dict[str, Any]:
    """Parse synthesize ``llm_chain`` text into ``llm_raw`` dict for validate.

    On non-JSON model output, builds a soft stub from the classification hint so
    validate can still emit a contract-shaped response.

    Args:
        state: Contains ``llm_raw`` (str or dict) plus hint / pack for fallback.

    Returns:
        ``{\"llm_raw\": {…}}``.
    """
    parsed = parse_json_object(state.get("llm_raw"))
    if parsed:
        return {"llm_raw": parsed}
    # Soft fallback from classification when LLM returns non-JSON
    hint = state.get("classification_hint") or {}
    pack = state.get("evidence_pack") or {}
    reason = (pack.get("raw_anchors") or {}).get("failure_reason") or "failure"
    category = hint.get("category") or "unknown"
    return {
        "llm_raw": {
            "category": category,
            "summary": f"Likely {category}: {reason}",
            "confidence": float(hint.get("confidence") or 0.5),
            "recommended_actions": ["Re-run with additional logging"],
            "evidence_refs": [
                str(e.get("ref")) for e in (pack.get("evidence") or []) if e.get("ref")
            ],
        }
    }


def validate_output(state: dict[str, Any]) -> dict[str, Any]:
    """Clamp draft into a stable API response shape (legacy-rich fields retained).

    Args:
        state: Post-parse state with ``llm_raw``, pack, hint, optional web hits.

    Returns:
        ``{\"result\": RcaResponse-shaped dict}`` (quality attached later).
    """
    raw = state.get("llm_raw") or {}
    if not isinstance(raw, dict):
        raw = parse_json_object(raw) or {}
    hint = state.get("classification_hint") or {}
    if not isinstance(hint, dict):
        hint = {}
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}

    validated = validate_rca_llm_output(
        raw,
        evidence_pack=pack,
        classification_hint=hint,
        web_search_hits=[
            hit
            for hit in (state.get("web_search_hits") or [])
            if isinstance(hit, dict)
        ],
    )
    result = {
        "request_id": state.get("request_id"),
        "job_id": state.get("job_id") or pack.get("job_id"),
        "job_run_id": state.get("job_run_id") or pack.get("job_run_id"),
        "task_key": state.get("task_key") or pack.get("task_key"),
        "status": "completed",
        "job_status": validated.get("job_status"),
        "root_cause": validated.get("root_cause"),
        "recommended_actions": validated.get("recommended_actions") or [],
        "contributing_factors": validated.get("contributing_factors") or [],
        "evidence_analysis": validated.get("evidence_analysis") or {},
        "possible_causes": validated.get("possible_causes") or [],
        "context_assessment": validated.get("context_assessment") or {},
        "recommendations": validated.get("recommendations") or {},
        "timeline": validated.get("timeline") or [],
        "evidence": validated.get("evidence") or [],
        "evidence_backfilled": bool(validated.get("evidence_backfilled")),
        "classification_hint": hint,
        "evidence_pack": pack,
        "runbook_context": state.get("runbook_context"),
        "historical_context": state.get("historical_context"),
        "web_search_context": state.get("web_search_context"),
        "web_search_hits": state.get("web_search_hits") or [],
    }
    return {"result": result}


def evaluate_output(state: dict[str, Any]) -> dict[str, Any]:
    """Attach deterministic quality/confidence without replacing model confidence.

    Invokes the registered ``spark_rca.quality`` evaluator. Model
    ``root_cause.confidence`` stays as emitted; evaluator confidence is a
    separate pack-completeness metric under ``quality``.

    Args:
        state: Post-validate state with ``result`` and context strings.

    Returns:
        Updated ``result`` (with ``quality``) plus top-level ``quality`` mirror.
    """
    from edim_dde_ai.evaluation import evaluate

    result = dict(state.get("result") or {})
    quality = evaluate(
        "spark_rca.quality",
        inputs={"evidence_pack": state.get("evidence_pack") or {}},
        output=result,
        context={
            "runbook_context": state.get("runbook_context"),
            "historical_context": state.get("historical_context"),
            "web_search_context": state.get("web_search_context"),
        },
    )
    result["quality"] = quality.to_dict()
    return {"result": result, "quality": quality.to_dict()}
