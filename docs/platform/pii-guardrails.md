# PII guardrails (BL-014)

**Learning path:** C3 · [Preface](../README.md)  
**← Previous:** [Key Vault bootstrap](key-vault-bootstrap.md) · **Next:** [Observability](observability.md) →

## Chapter summary

Basic expandable redaction so accidental PII does not reach logs or LangSmith. Current agents target telemetry, not customer PII, but patterns still apply as a safety net.

**Outcome:** you know default redaction labels and where to extend patterns.

---

**Context:** Current EDIM agents (`cluster_tuning`, `spark_rca`) operate on **telemetry** (cluster/job metrics and logs). They are **not expected** to process customer PII. We still apply **basic expandable redaction** so accidental PII does not reach logs or LangSmith.

---

## Default patterns (current)

| Label | Detects | Redaction |
|-------|---------|-----------|
| `ssn` | US SSN-like `###-##-####` / 9-digit groups | `[REDACTED:ssn]` |
| `credit_card` | 13–19 digit PAN-like sequences (Luhn not required yet) | `[REDACTED:credit_card]` |
| `account_number` | Phrases like `account number` / `acct` followed by digits | `[REDACTED:account_number]` |
| `member_id` | `member id` / `memberid` / `member#` followed by alphanumerics | `[REDACTED:member_id]` |

Patterns live in code as a **registry list** so new labels can be appended without redesign.

---

## Where redaction applies

1. Strings prepared for **logging** (including API `safe_logging` stacks at the HTTP boundary)
2. Payloads / metadata sent to **LangSmith** (when tracing is enabled)
3. Optional helper for domain code that serializes evidence packs

API exceptions are logged **once** with secrets (Bearer/JWT, `client_secret`, …) and PII redacted; HTTP response bodies do not include stacks. See [endpoints](../api/endpoints.md) and [request flow](../architecture/request-flow.md).

Redaction is **best-effort regex**. It is not a substitute for data-classification reviews or column-level controls in Unity Catalog.

---

## Expanding the list later

Add a pattern in `edim_dde_domain.security.pii` (or shared `edim_dde_ai` helper) with:

- `name` — stable label
- `regex` — compiled pattern
- `replacement` — default `[REDACTED:{name}]`

Document new labels in this page and add unit tests with sample strings.

---

## Data classification note

| Class | EDIM R1 expectation |
|-------|---------------------|
| Telemetry / metrics | Primary agent inputs (job ids, cluster ids, CPU, etc.) |
| PII / account identifiers | Should not appear; redacted if they do |
| Secrets | Never in prompts, logs, or traces — use Key Vault |

---

## Related

- [Key Vault bootstrap](key-vault-bootstrap.md)
- [Access & permissions](access-and-permissions.md)
- [Security baseline](security-baseline.md)
- [LangSmith setup](langsmith-setup.md)

## Summary

- Redact before logs and observability backends; expand patterns as needed.
- Pair with security baseline and LangSmith setup for ops.

**Next →** [Observability (C4)](observability.md)

<!-- edim-learning-nav -->
---

← [Key Vault bootstrap](key-vault-bootstrap.md) · [Preface](../README.md) · [Observability](observability.md) →
