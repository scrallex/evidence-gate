# Repo Asset Map

This repo no longer needs a "collapse multiple projects" story. The core
`Evidence Gate` product surface is already here. The remaining deliverable work
is packaging, integration, and proof presentation.

## Core assets to reuse

### 1. Decision contract and API surface

Path: `app/evidence_gate/api/`, `app/evidence_gate/decision/`

Use for:

- `admit | abstain | escalate` response contract
- query and change-impact endpoints
- persisted audit records
- knowledge-base lifecycle controls

What it already proves:

- the product has a concrete service boundary
- outputs are rigid and auditable rather than chat-shaped
- decisions can be stored and reviewed after the fact

### 2. Structural retrieval and verification

Path: `app/evidence_gate/retrieval/`, `app/evidence_gate/structural/`,
`app/evidence_gate/verification/`

Use for:

- repository ingestion into a local structural knowledge base
- structural ranking over code, docs, tests, runbooks, PRs, and incidents
- truth-pack style verification on retrieved evidence
- twin-case retrieval for escalation paths

What it already proves:

- the gate is not generic semantic RAG
- verification and precedent are first-class product behavior
- abstention can be driven by structural support instead of answer-forcing

### 3. Blast radius and engineering change intelligence

Path: `app/evidence_gate/blast_radius/`

Use for:

- AST dependency analysis
- impacted path expansion
- code, test, doc, and runbook counts
- change-impact reasoning for engineering workflows

What it already proves:

- the first workflow is operational and code-aware
- impact can be quantified instead of described vaguely
- the service can gate engineering changes, not only answer questions

### 4. Benchmark and regression proof

Path: `benchmarks/`, `scripts/run_fastapi_benchmark.py`, `tests/`

Use for:

- reproducible benchmark cases and reports
- structural versus baseline retrieval-and-decision comparison
- regression coverage for API, retrieval, and cache behavior

What it already proves:

- the repo has one concrete public proof surface today
- on the checked-in 50-case FastAPI slice, structural retrieval reaches 84.00%
  binary accuracy with a 0.00% false-admit rate
- the baseline reaches 76.00% binary accuracy with a 48.00% false-admit rate

### 5. Reviewer-facing materials

Path: `README.md`, `docs/`, `sources/`

Use for:

- product framing
- MVP contract
- execution sequencing
- partner-review and release-readiness notes

What it already proves:

- the repo can be reviewed without a private research archive
- the public story is implementation-first and benchmark-backed
- the current alpha can be presented honestly without hiding its limits

## Assets to keep out of the public product story

- exploratory research archives and private whitepapers
- runtime knowledge bases and audit logs under `~/.evidence-gate/` or `var/`
- generated cache artifacts and ad hoc reruns that are not the canonical proof

## Consolidation target

The code consolidation is already done. The next consolidation is around
delivery:

1. One benchmarked API surface.
2. One repeatable evaluator kit.
3. One MCP surface for agent workflows.
4. One CI/CD gating path for pull requests.
5. One honest public story about current limits.

## Real deliverable that fits the repo

The near-term deliverable should stay narrow:

`Evidence Gate: The Reliability Layer for AI Agents.`

The first benchmarked workflow under that story is engineering change
intelligence. The immediate package worth building from this repo is a
benchmarked technical preview with:

- the API and audit contract
- the checked-in FastAPI benchmark report
- a one-command local evaluator path such as Docker
- MCP delivery for IDE and agent use
- a sample change-impact walkthrough on a real repository
