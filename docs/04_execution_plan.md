# Execution Plan

## Product target

Ship a credible technical preview for `Evidence Gate: The Reliability Layer for
AI Agents.` The first benchmarked workflow remains engineering change
intelligence. A reviewer should be able to point the service at a real codebase
and get back:

- cited evidence spans
- blast radius
- prior PR or incident twins
- `admit | abstain | escalate`
- an auditable decision record

## What is already done

### Phase 0: product collapse

- consolidated the strongest research threads into one product story
- narrowed the first workflow to engineering change intelligence
- defined the canonical decision contract

### Phase 1: service alpha

- built a FastAPI application surface in this repo
- implemented structural retrieval plus truth-pack verification
- added blast radius, audit logging, and persisted repo knowledge bases
- added knowledge-base ingest, status, deletion, prune, and maintenance endpoints
- added regression tests for the current API and retrieval behavior

### Phase 2: first public proof

- built a reproducible FastAPI benchmark over 50 admit/withhold cases
- checked in the benchmark corpus, runner, and human-readable report
- showed 84.00% structural binary accuracy versus 76.00% for the baseline
- showed a 0.00% structural false-admit rate versus 48.00% for the baseline

### Phase 3: first MCP workflow placement

- added an MCP server exposing ingest, query, and change-impact flows
- added MCP resources for the decision schema and persisted decision records
- added a prompt for pre-change gating before risky edits
- covered the MCP surface with a real stdio integration test

### Phase 4: evaluator kit and partner setup

- added a Docker image that runs the API on `8000` and MCP streamable-http on `8001`
- added a Compose stack with persistent audit and knowledge-base storage under `data/`
- added a demo sandbox script that clones FastAPI, starts the stack, and ingests the corpus
- added a partner evaluation guide for mounting a private repo into the container

## What remains

### Phase 5: agent and IDE hardening

Goal:
validate the MCP and evaluator surface across real client environments.

Tasks:

1. Validate the copy-paste examples for Cursor, Cline, or other generic MCP clients.
2. Keep the Docker evaluator path current.
3. Publish a short walkthrough for a real auth or session change-impact demo.
4. Tighten setup docs from partner feedback.
5. Consider mounting the same MCP surface alongside the HTTP API for simpler deployment.

Exit criteria:

- a reviewer can run the service without Python dependency archaeology
- an agent can request a decision and receive the same auditable contract
- the evaluator package is credible for guided partner review

### Phase 6: CI/CD and action gating

Goal:
move from answering questions about changes to blocking unsafe changes in the
delivery path itself.

Tasks:

1. Validate the new `POST /v1/decide/action` policy on real CI workflows.
2. Extend the GitHub Action wrapper and add GitLab CI integration.
3. Define policy for merge blocking using blast radius plus missing evidence.
4. Return machine-readable failure reasons and human-readable PR comments.
5. Extend the audit surface so repeated checks can be reviewed over time.

Exit criteria:

- a pull request can be labeled `admit`, `abstain`, or `escalate`
- the system can explain missing tests, runbooks, or precedent clearly
- a repo owner can use the gate as a required or advisory check

### Phase 7: broader enterprise knowledge graph

Goal:
expand from local repository intelligence into institutional memory across the
systems engineering teams already use.

Tasks:

1. Operationalize the live Jira export ingestor in CI and partner evaluation flows.
2. Operationalize the live PagerDuty and Slack incident ingestors in CI and partner evaluation flows.
3. Operationalize the live Confluence export ingestor for architecture corpora.
4. Link code-change blast radius to external incident and decision evidence.
5. Recalibrate the decision policy on multi-source enterprise corpora.

Exit criteria:

- the gate can retrieve code, docs, tickets, and incident history together
- escalation paths point to prior operational evidence, not only repo artifacts
- the product story expands from code intelligence to institutional memory guardrail

### Phase 8: native graph ingestion horizon

Goal:
stop asking Evidence Gate to reverse-engineer every language ecosystem with
lightweight parsers when the repository can often emit a native code graph
itself.

Tasks:

1. Add an LSIF ingest stub so repositories can provide language-server-derived symbol and reference graphs.
2. Add a SCIP ingest stub so repositories can reuse native indexers instead of Evidence Gate guessing imports.
3. Map LSIF or SCIP graph nodes back to Evidence Gate evidence spans, blast-radius inputs, and twin-case citations.
4. Benchmark graph-assisted retrieval on dynamic JavaScript or TypeScript repos such as Vite against the current heuristic parser.
5. Define fallback rules so the gate remains fail-safe when no graph export is available.

Exit criteria:

- Evidence Gate can ingest a native repo graph without replacing the rest of the decision contract
- dynamic repos recover throughput without sacrificing the current 0.00% false-allow posture
- the long-term parser story shifts from bespoke language heuristics to standard graph ingestion

## Commercial sequence

### Immediate proof

Send a benchmarked technical preview that includes:

- repo link
- concise quickstart
- FastAPI benchmark summary
- sample change-impact requests
- known limitations

### First workflow placement

Land Evidence Gate inside one coding-agent or IDE workflow through MCP.

### First delivery-path placement

Use the same contract to gate pull requests or automation actions in CI.

### Expansion after proof

- action gating beyond change-impact questions
- broader operational and incident intelligence
- stronger partner-ready enterprise ingestion and sync paths

## What to say no to

- polishing a UI before MCP and evaluator packaging exist
- adding broad enterprise claims without one strong workflow placement
- marketing language that outruns the current benchmark scope
- restoring stale planning docs as if they describe the current repo state
