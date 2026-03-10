# Evidence Gate

`Evidence Gate` decides whether an AI system has enough structural evidence and
precedent to answer or act.

This repo is the alpha implementation of that reliability layer, currently
focused on engineering change intelligence. It ingests a target repository into
a structural knowledge base, retrieves cited evidence spans and prior cases,
computes blast radius, and returns an `admit | abstain | escalate` decision
before a model or agent proceeds.

## What It Does Today

- ingests a repository into a persisted structural knowledge base
- answers change-impact and engineering evidence queries
- returns cited evidence spans, prior PR or incident twins, blast radius, and an
  `admit | abstain | escalate` decision
- writes decision audit records and manages knowledge-base lifecycle and retention

## Current Status

This repo is now the implementation home for the alpha service, not only a
planning workspace.

It is suitable today for:

- technical review
- architecture discussion
- guided demos on a target repository

It is not yet ready as a self-serve product or production deployment. The main
gaps are benchmarked proof, packaging, MCP delivery, and a polished pilot kit.

## Quickstart

Run the API locally:

```bash
uvicorn evidence_gate.api.main:app --app-dir app --reload
```

Build a repository knowledge base:

```bash
curl -X POST http://127.0.0.1:8000/v1/knowledge-bases/ingest \
  -H "content-type: application/json" \
  -d '{"repo_path": "/path/to/repo"}'
```

Ask a change-impact question:

```bash
curl -X POST http://127.0.0.1:8000/v1/decide/change-impact \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/path/to/repo",
    "change_summary": "If we change auth/session handling, what is impacted?",
    "changed_paths": ["src/session.py"]
  }'
```

Run tests:

```bash
pytest -q
```

## API Surface

- `GET /health`
- `POST /v1/knowledge-bases/ingest`
- `GET /v1/knowledge-bases`
- `GET /v1/knowledge-bases/status?repo_path=...`
- `DELETE /v1/knowledge-bases?repo_path=...`
- `POST /v1/knowledge-bases/prune`
- `GET /v1/knowledge-bases/maintenance/status`
- `POST /v1/knowledge-bases/maintenance/run`
- `POST /v1/decide/query`
- `POST /v1/decide/change-impact`
- `GET /v1/decisions/{id}`

Persisted runtime state lives outside the repo under `~/.evidence-gate/` by
default and is intentionally not part of the tracked source surface. Use
`EVIDENCE_GATE_AUDIT_ROOT` or `EVIDENCE_GATE_KB_ROOT` if you explicitly want
in-repo paths such as `var/`.

Key environment controls:

- `EVIDENCE_GATE_AUDIT_ROOT`
- `EVIDENCE_GATE_KB_ROOT`
- `EVIDENCE_GATE_KB_PRUNE_ON_STARTUP`
- `EVIDENCE_GATE_KB_MAX_AGE_HOURS`
- `EVIDENCE_GATE_KB_MAX_CACHE_ENTRIES`

## Repository Map

- `app/`: FastAPI service, retrieval, verification, blast radius, and audit code
- `tests/`: API and retrieval regression coverage
- `docs/`: product thesis, MVP contract, execution plan, and release-readiness path
- `sources/`: source index plus archived background research and provenance

Raw research papers and extracted legacy source material now live under
`sources/archive/` and are intentionally kept out of the repo's market-facing
story.

## Start Here

- `docs/01_product_thesis.md`
- `docs/03_mvp_spec.md`
- `docs/04_execution_plan.md`
- `docs/05_repo_audit_and_delivery_gameplan.md`
- `docs/06_release_readiness_and_partner_path.md`
