# Evidence Gate

`Evidence Gate: The Reliability Layer for AI Agents.`

It decides whether an AI system has enough structural evidence and precedent to
answer or act.

This repo is the alpha implementation of that reliability layer. Its first
benchmarked workflow is engineering change intelligence: ingest a target
repository into a structural knowledge base, retrieve cited evidence spans and
prior cases, compute blast radius, and return an `admit | abstain | escalate`
decision before a model or agent proceeds.

## What It Does Today

- ingests code, docs, tests, runbooks, PRs, and incidents into a persisted
  structural knowledge base
- answers change-impact and engineering evidence queries
- returns cited evidence spans, prior PR or incident twins, blast radius, and an
  `admit | abstain | escalate` decision
- writes decision audit records and manages knowledge-base lifecycle and retention
- exposes the same decision contract through an MCP server for agent and IDE workflows

## Why It Matters

The product wedge is not "repo chat." It is safer admission behavior.

In the checked-in 50-case FastAPI benchmark, `Evidence Gate structural` reaches
84.00% binary accuracy with a 0.00% false-admit rate. The baseline reaches
76.00% binary accuracy with a 48.00% false-admit rate.

## Current Status

This repo is now the implementation home for the alpha service, not only a
planning workspace.

It is suitable today for:

- technical review
- architecture discussion
- guided demos on a target repository
- design-partner evaluation with guided setup

It is not yet ready as a self-serve product or production deployment. The main
gaps are production hardening, broader CI adoption, partner validation on
private corpora, and wider enterprise-source ingestion.

## Quickstart

Install the package and test dependencies:

```bash
python -m pip install -e '.[dev]'
```

Run the API locally:

```bash
uvicorn evidence_gate.api.main:app --app-dir app --reload
```

Run the MCP server over stdio for Cursor, Cline, or any local MCP client:

```bash
evidence-gate-mcp
```

Run the MCP server over streamable HTTP:

```bash
evidence-gate-mcp --transport streamable-http --port 8001
```

Run the zero-to-value demo sandbox:

```bash
./scripts/run_demo_sandbox.sh
```

Run the Docker evaluator stack against a mounted repo:

```bash
EVIDENCE_GATE_REPO_MOUNT=/absolute/path/to/private-repo docker compose up -d --build
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

Run the checked-in FastAPI benchmark:

```bash
python scripts/run_fastapi_benchmark.py
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
- `POST /v1/decide/action`
- `GET /v1/decisions/{id}`

## MCP Surface

The repo now ships a first-cut MCP server with:

- tools for repository ingest, knowledge-base status, query decisions, change-impact decisions, action gating, and audit lookup
- a decision-contract schema resource, per-decision resources, and the raw audit ledger
- a prompt that tells an agent to gate risky code edits before proceeding

See `docs/07_mcp_server.md` for local `stdio` and remote `streamable-http`
configuration examples.

## Evaluator Kit

The repo now includes a design-partner evaluator path:

- `Dockerfile`: runs the FastAPI API on `8000` and the MCP streamable-http endpoint on `8001`
- `docker-compose.yml`: mounts persistent audit and knowledge-base state under `./data`
- `scripts/run_demo_sandbox.sh`: boots the stack, clones FastAPI, ingests it, and prints copy-paste test commands
- `docs/08_partner_evaluation_guide.md`: step-by-step instructions for mounting a private repo into the container

## Benchmark Proof

The repo now includes a reproducible benchmark against a real open-source corpus:

- `benchmarks/cases/fastapi_cases.json`: 50 admit/withhold benchmark queries
- `benchmarks/results/fastapi_structural_vs_baseline.md`: latest checked-in report
- `scripts/run_fastapi_benchmark.py`: rebuild the corpus and rerun the comparison

Current checked-in result:

- structural binary accuracy: 84.00%
- baseline binary accuracy: 76.00%
- structural false-admit rate: 0.00%
- baseline false-admit rate: 48.00%

The benchmark uses a curated FastAPI slice with code, tests, English docs,
deployment runbooks, and precedent PR summaries extracted from release notes.

## Roadmap

- Immediate: validate the evaluator kit on partner-shaped repos and harden CI adoption
- Medium term: tighten delivery-path policies and broaden GitHub or GitLab integration
- Long term: Jira, PagerDuty or Slack, and Confluence connectors for broader institutional memory

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
- `sources/`: minimal provenance notes only

Legacy exploratory research is intentionally not shipped in this public repo.
The public surface stays focused on the implementation, benchmark proof, and
partner-review materials.

## Start Here

- `docs/01_product_thesis.md`
- `docs/03_mvp_spec.md`
- `docs/04_execution_plan.md`
- `docs/05_repo_audit_and_delivery_gameplan.md`
- `docs/06_release_readiness_and_partner_path.md`
- `docs/07_mcp_server.md`
- `docs/08_partner_evaluation_guide.md`
