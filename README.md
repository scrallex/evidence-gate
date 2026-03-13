# Evidence Gate

`Evidence Gate: The Reliability Layer for AI Agents.`

It decides whether an AI system has enough structural evidence and precedent to
answer or act, and when it blocks an agent it returns the missing evidence
needed for the next repair attempt.

This repo is the alpha implementation of that reliability layer. Its first
benchmarked workflow is engineering change intelligence: ingest a target
repository plus optional local incident evidence into a structural knowledge
base, retrieve cited evidence spans and prior cases, compute blast radius, and
return an `admit | abstain | escalate` decision before a model or agent
proceeds.

## What It Does Today

- ingests repository content plus optional local exports from incidents, Jira,
  PagerDuty, Slack, and Confluence into a persisted structural knowledge base
- can materialize live read-only GitHub, Jira, and PagerDuty exports at ingest
  time through token-backed helper scripts and the composite GitHub Action
- ingests optional LSIF or SCIP sidecars from `.evidence-gate/graphs` to improve
  blast radius and retrieval on dynamic or non-Python repos
- answers change-impact and engineering evidence queries
- returns cited evidence spans, prior PR or incident twins, blast radius, and an
  `admit | abstain | escalate` decision
- turns blocked action decisions into repair hints through `missing_evidence`
  so agents can retry with the required tests or file changes
- writes decision audit records and manages knowledge-base lifecycle and retention
- exposes a stakeholder dashboard that turns audit history into a Risk Avoided
  feed and an Agent Healing Rate view
- exposes the same decision contract through an MCP server and a composite
  GitHub Action for agent, IDE, and CI workflows

## Why It Matters

The product wedge is not "AI PR review." It is safer admission behavior plus a
compiler-like healing loop for agents.

AI PR reviewers mostly tell a human what looks risky after the code already
exists. Evidence Gate is trying to do something narrower and more operational:
block the agent attempt, emit machine-readable `missing_evidence`, and force
the next retry to add the missing test, runbook context, or supported file path
before a human ever has to review the patch.

The repo now also carries a checked-in dogfood example of standards
enforcement on its own MCP workflow: under a `require_runbook_evidence` policy,
the integration diff blocked until `runbooks/mcp_agent_troubleshooting.md`
existed, then admitted on retry.

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
- CI guardrail previews on a target repository with explicit safety thresholds

It is not yet ready as a self-serve product or production deployment. The main
gaps are production hardening, broader CI adoption, partner validation on
private corpora, prebuilt CI packaging, and hosted sync beyond mounted export data.

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

Run the shell-friendly bridge for agents that do not speak MCP directly:

```bash
python scripts/run_agent_gate.py \
  --repo-path /absolute/path/to/repo \
  --action-summary "Review the auth/session change before editing code." \
  --changed-path src/session.py
```

Run the stakeholder dashboard:

```bash
cd dashboard
npm install
npm run dev
```

The dashboard expects the FastAPI service at `http://127.0.0.1:8000` by default.
Set `EVIDENCE_GATE_API_BASE_URL` if your API is running somewhere else.

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

Build a mixed-source knowledge base with local external exports:

```bash
curl -X POST http://127.0.0.1:8000/v1/knowledge-bases/ingest \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/path/to/repo",
    "external_sources": [
      {"type": "pagerduty", "path": "/path/to/pagerduty"},
      {"type": "jira", "path": "/path/to/jira"},
      {"type": "github", "path": "/path/to/github_prs"},
      {"type": "confluence", "path": "/path/to/confluence"}
    ]
  }'
```

Fetch live read-only connector exports for the last 30 days:

```bash
GITHUB_TOKEN=... \
GITHUB_REPOSITORY=owner/repo \
JIRA_BASE_URL=https://company.atlassian.net \
JIRA_API_TOKEN=... \
JIRA_USER_EMAIL=you@company.com \
PAGERDUTY_TOKEN=... \
python scripts/fetch_live_exports.py --output-root /tmp/evidence-gate-live
```

The script prints a JSON `external_sources` array that can be passed straight
into `/v1/knowledge-bases/ingest`. The composite GitHub Action now does this
automatically for GitHub pull requests when `github_token` is supplied, and it
can also fetch Jira and PagerDuty context when those tokens are configured.

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

Run the extended value-proof suite:

```bash
python scripts/run_value_proof_benchmarks.py
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
- `GET /v1/dashboard/overview`

## MCP Surface

The repo ships an MCP server with:

- tools for repository ingest, automatic repository preparation, optional mixed-source ingest,
  query decisions, change-impact decisions, raw action gating, and a higher-level
  gate-plus-healing workflow that returns retry guidance for blocked changes
- a decision-contract schema resource, per-decision resources, and the raw audit ledger
- prompts for both change review and the full fail-explain-repair-retry loop

For agents that do not natively consume MCP, `scripts/run_agent_gate.py` exposes
the same gate-plus-retry contract as plain JSON for SWE-agent-style tool bundles
or other shell-based workflows.

See `docs/07_mcp_server.md` for local `stdio` and remote `streamable-http`
configuration examples, and `docs/09_agent_skills.md` for Codex-oriented skill
guidance.

## Stakeholder Dashboard

The repo now includes a small Next.js dashboard in [`dashboard/`](/sep/evidence-gate/dashboard)
for VP Engineering, CTO, and CISO style review workflows.

It reads `GET /v1/dashboard/overview` and shows:

- `Risk Avoided`: blocked PR or agent actions, their blast radius, and the Jira,
  Slack, PagerDuty, or incident signals that contributed to the block
- `Agent Healing Rate`: how often blocked action sequences later came back as
  allowed after a retry

This view is intentionally separate from the terminal and MCP workflow. It is
for communicating prevented downtime and avoided review debt to stakeholders who
do not live inside the IDE.

## Evaluator Kit

The repo now includes a design-partner evaluator path:

- `Dockerfile`: runs the FastAPI API on `8000` and the MCP streamable-http endpoint on `8001`
- `docker-compose.yml`: mounts persistent audit and knowledge-base state under `./data`
- `scripts/run_demo_sandbox.sh`: boots the stack, clones FastAPI, ingests it, and prints copy-paste test commands
- `docs/08_partner_evaluation_guide.md`: step-by-step instructions for mounting a private repo into the container

The composite GitHub Action can now self-fetch recent GitHub pull request
precedent from the checked-out repository when `github_token` is supplied, and
it can optionally fetch Jira or PagerDuty context when those tokens are
configured. You can still pass explicit `external_sources`, but mounted export
directories are no longer required for the default PR guardrail path.

For repositories that can emit native code graphs, place LSIF or SCIP sidecars
under `.evidence-gate/graphs`. Evidence Gate will ingest those graphs to
augment blast radius and retrieval while preserving the existing decision
contract and heuristic fallback behavior.

## Benchmark Proof

The repo now includes a reproducible benchmark against a real open-source corpus:

- `benchmarks/cases/fastapi_cases.json`: 50 admit/withhold benchmark queries
- `benchmarks/results/fastapi_structural_vs_baseline.md`: latest checked-in report
- `scripts/run_fastapi_benchmark.py`: rebuild the corpus and rerun the comparison
- `benchmarks/results/value_proof_benchmarks.md`: fast proof suite with poisoned-corpus, mixed-source, compact SWE-bench, and multi-corpus findings
- `scripts/run_value_proof_benchmarks.py`: rerun the fast extended proof suite
- `benchmarks/results/swebench_lite_full_replay.md`: standalone 300-instance SWE-bench Lite replay report
- `benchmarks/results/swebench_lite_full_replay.json`: raw per-instance full-replay results
- `scripts/run_swebench_full_replay.py`: rerun the full 300-instance replay

Current checked-in result:

- structural binary accuracy: 84.00%
- baseline binary accuracy: 76.00%
- structural false-admit rate: 0.00%
- baseline false-admit rate: 48.00%

The benchmark uses a curated FastAPI slice with code, tests, English docs,
deployment runbooks, and precedent PR summaries extracted from release notes.

The broader proof suite now adds four more signals:

- poisoned corpus: 12.50% structural false-admit versus 87.50% for the lexical baseline
- mixed-source incident blocking: 80.00% incremental block rate when external incident evidence is available
- full SWE-bench Lite replay: 32.67% initial gold-path allow, 50.67% healed gold-path allow, 18.00 points of admit lift, and 1.00% wrong-file false-allow across 300 official tasks
- multi-corpus generalization pilot: 12 curated cases across Redis, React, and Vite with 75.00% gold-path allow and 0.00% wrong-file false-allow

The fast `value_proof_benchmarks` artifact still keeps a compact SWE-bench slice
for runtime, but the standalone full-replay report is now the representative
dataset-scale evidence for the healing-loop claim.

The current evidence therefore supports a strong false-admit and safety claim,
an initial compiler-for-agents claim when the agent consumes `missing_evidence`
and retries, and a cross-language design-partner story across Python, C,
JavaScript, and TypeScript. The stronger statement is now specific: the gate
improves admit rate on the full SWE-bench Lite replay while still rejecting
99.00% of wrong-file decoys. It still does not support a universal throughput
claim, and it still does not prove final autonomous task pass-rate uplift
against a live framework such as OpenHands or SWE-agent.

## Roadmap

- Immediate: validate the evaluator kit on partner-shaped repos and harden CI adoption
- Medium term: publish prebuilt CI images, tighten delivery-path policies, and broaden GitHub or GitLab integration
- Long term: hosted source sync, broader multi-source benchmarks, and production deployment hardening

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
- `docs/09_agent_skills.md`
- `docs/10_value_proof.md`
