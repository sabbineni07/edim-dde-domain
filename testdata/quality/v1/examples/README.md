# Quality corpus examples (not scored by default)

Files here are **reference shapes** for engineers. They are **not** listed in
`../manifest.yaml`, so offline CI / default harness runs ignore them.

| File | Purpose |
|------|---------|
| `rca_executor_oom_invoke.example.json` | Same OOM axis as v1, plus `invoke_input` for `--live` |

To try live:

1. Copy the example into `../spark_rca/` (or merge `invoke_input` into an existing case).
2. Add a manifest entry (or reuse an existing id after merge).
3. Run:

```bash
python -m edim_dde_domain.evaluation.harness --corpus v1 --trials 1 --live \
  --agents spark_rca --out /tmp/rca-live.json
```

See the engineer guide: `docs/framework/evaluation-and-quality.md` §5b
(optional deep dive — live harness with `invoke_input`).
