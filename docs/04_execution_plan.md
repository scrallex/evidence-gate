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

## What remains

### Phase 4: agent and IDE packaging

Goal:
make the MCP surface trivial for a design partner to adopt.

Tasks:

1. Add copy-paste examples for Cursor, Cline, or any generic MCP client.
2. Add a one-command evaluator path such as Docker.
3. Publish a short walkthrough for a real auth or session change-impact demo.
4. Tighten setup docs so a design partner can run the system on a private repo quickly.
5. Consider mounting the same MCP surface alongside the HTTP API for simpler deployment.

Exit criteria:

- a reviewer can run the service without Python dependency archaeology
- an agent can request a decision and receive the same auditable contract
- the evaluator package is credible for guided partner review

### Phase 5: CI/CD and action gating

Goal:
move from answering questions about changes to blocking unsafe changes in the
delivery path itself.

Tasks:

1. Add `POST /v1/decide/action`.
2. Add GitHub Action and GitLab CI integration.
3. Define policy for merge blocking using blast radius plus missing evidence.
4. Return machine-readable failure reasons and human-readable PR comments.
5. Extend the audit surface so repeated checks can be reviewed over time.

Exit criteria:

- a pull request can be labeled `admit`, `abstain`, or `escalate`
- the system can explain missing tests, runbooks, or precedent clearly
- a repo owner can use the gate as a required or advisory check

### Phase 6: broader enterprise knowledge graph

Goal:
expand from local repository intelligence into institutional memory across the
systems engineering teams already use.

Tasks:

1. Add connectors for Jira tickets and change records.
2. Add connectors for PagerDuty or Slack incident history.
3. Add connectors for Confluence or architecture documentation stores.
4. Link code-change blast radius to external incident and decision evidence.
5. Recalibrate the decision policy on multi-source enterprise corpora.

Exit criteria:

- the gate can retrieve code, docs, tickets, and incident history together
- escalation paths point to prior operational evidence, not only repo artifacts
- the product story expands from code intelligence to institutional memory guardrail

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
- stronger enterprise connectors

## What to say no to

- polishing a UI before MCP and evaluator packaging exist
- adding broad enterprise claims without one strong workflow placement
- marketing language that outruns the current benchmark scope
- restoring stale planning docs as if they describe the current repo state
