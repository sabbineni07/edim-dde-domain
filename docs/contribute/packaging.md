# Packaging (H6)

**Learning path:** H6 · [Preface](../README.md)  
**← Previous:** [Windows smoke](windows-smoke-checklist.md) · **Next:** [Documentation style](documentation-style.md) →

## Chapter summary

How the three EDIM packages are **versioned** and how they will be published. Local development still uses editable installs (`requirements.txt` `-e ../…`). A private index is **not** required to run R1.

**Outcome:** you know when to bump versions, rebuild vendor wheels, and (later) publish to Artifactory / Azure Artifacts.

---

## 1. Packages and versions

All three packages are at **`1.0.0`** (R1). Keep them aligned when you cut a release.

| Package | Version source | Runtime depends on |
|---------|----------------|-------------------|
| `edim-dde-ai` | `src/edim_dde_ai/version.py` (Hatch dynamic) | langgraph, langchain-core, PyYAML |
| `edim-dde-domain` | `pyproject.toml` + `edim_dde_domain` | **ai** (local: editable) + pydantic/yaml |
| `edim-dde-api` | `pyproject.toml` + `edim_dde_api.__version__` | **domain** + **ai** (local: editable) + FastAPI |

Intended **published** graph (when the index exists):

```text
edim-dde-api  →  edim-dde-domain  →  edim-dde-ai
```

Until then, `edim-dde-api/requirements.txt` and `pip install -e ".[dev]"` with sibling checkouts remain the supported path. Do **not** add unpublished names as hard `pyproject` dependencies — `pip install edim-dde-domain` from PyPI would fail.

---

## 2. Local install (developers)

```bash
cd edim-dde-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
```

`requirements.txt` already has `-e ../edim-dde-ai[…]` and `-e ../edim-dde-domain[…]`.

---

## 3. Build wheels (when you are ready to publish)

From each package root (needs `pip install build`):

```bash
cd edim-dde-ai && python3 -m build
cd ../edim-dde-domain && python3 -m build
cd ../edim-dde-api && python3 -m build
```

Artifacts land in `dist/*.whl`. Extras that pull optional backends:

| Extra | Package |
|-------|---------|
| `[observability]` `[mlflow]` `[postgres]` `[cosmos]` `[redis]` `[faiss]` `[azure-search]` | `edim-dde-ai` |
| `[databricks]` `[azure]` `[keyvault]` `[llm]` | `edim-dde-domain` |

`edim-dde-ai` Hatch config already includes `src/edim_dde_ai`. Domain Hatch **includes YAML/content** (`*.yaml`, prompts) so wheels ship agent packs.

---

## 4. Private index (deferred ops)

Pin versions in the **Apps / CI** `requirements.txt` once wheels are on Artifactory or Azure Artifacts. See [Deploy & hosting](../api/deploy-and-hosting.md) §5.3b. Vendor/`vendor/` is a temporary Apps workaround — stop relying on it when the index is live.

Checklist when the index is ready:

1. Upload `edim-dde-ai==1.0.0` (or next bump)
2. Add `edim-dde-ai>=1.0.0` to domain `pyproject.toml` `dependencies`
3. Upload domain wheel; add `edim-dde-domain>=1.0.0` to api `pyproject.toml`
4. Replace `-e ../` in Apps requirements with index pins
5. Record the bump in each package `CHANGELOG.md`

---

## 5. Slim domain extras (later)

Optional split `[rca]` / `[tuning]` so hosts that only load external plugins need not ship product YAML. **Not done in this pass** — re-review when a second consumer exists.

---

## Related

- [Deploy & hosting](../api/deploy-and-hosting.md) — Apps packaging A–D
- Workspace `BACKLOG.md` — packaging checkboxes
- `edim-dde-ai/CHANGELOG.md` — framework notes

<!-- edim-learning-nav -->
---

← [Windows smoke](windows-smoke-checklist.md) · [Documentation style](documentation-style.md) →
