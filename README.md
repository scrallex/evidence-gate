# Evidence Gate Workspace

This directory consolidates the strongest SEP research threads into a single product program:
`Evidence Gate`, a structural reliability layer for LLM answers and agent actions.

The current goal is not to preserve every prior thesis. The goal is to turn the highest-value
work into one buildable product surface:

- structural retrieval
- twin or recurrence matching
- hazard-gated verification
- explicit `admit | abstain | escalate` decisions

Start here:

- `docs/01_product_thesis.md`
- `docs/03_mvp_spec.md`
- `docs/04_execution_plan.md`
- `docs/05_repo_audit_and_delivery_gameplan.md`
- `docs/02_repo_asset_map.md`
- `sources/SOURCE_INDEX.md`

## First Service Slice

The repo now includes an initial `Evidence Gate` alpha service under `app/`.

Run it locally with:

```bash
uvicorn evidence_gate.api.main:app --app-dir app --reload
```

Structural repo knowledge bases are now persisted under `var/knowledge_bases` by default.
Set `EVIDENCE_GATE_KB_ROOT` to relocate that cache.

Key endpoints:

- `GET /health`
- `GET /v1/knowledge-bases`
- `GET /v1/knowledge-bases/status?repo_path=...`
- `POST /v1/knowledge-bases/ingest`
- `POST /v1/decide/query`
- `POST /v1/decide/change-impact`
- `GET /v1/decisions/{id}`

The source bundle can be refreshed with:

```bash
./scripts/sync_sources.sh
```

That script copies the phase-1 source documents into `sources/raw/` and extracts searchable text
into `sources/extracted/`.
