# MVP Spec

## Working name

`Evidence Gate`

## Category

Reliability layer for AI agents, with engineering change intelligence as the
first benchmarked workflow.

## Target user

AI platform teams, developer tooling teams, and enterprise engineering orgs
using AI over internal code, docs, runbooks, PRs, and incident history.

## User problem

Most AI systems over internal corpora retrieve text but do not decide well when
evidence is weak, stale, or structurally mismatched. They answer anyway instead
of showing whether the request is actually well-supported.

## Core promise

Before an answer or recommendation is returned, Evidence Gate decides whether
the request is structurally supported by evidence and precedent in the target
corpus.

## Primary workflow

Engineering change intelligence.

Example request:

"If we change auth or session handling, what files, tests, docs, runbooks, and
prior incidents are impacted?"

## Decision contract

```json
{
  "decision": "admit | abstain | escalate",
  "hazard": 0.18,
  "recurrence": 4,
  "confidence": 0.82,
  "evidence_spans": [
    {"source": "docs/auth.md", "score": 0.91},
    {"source": "src/session.py", "score": 0.88}
  ],
  "twin_cases": [
    {"id": "pr_1842", "similarity": 0.86},
    {"id": "incident_2025_09_17", "similarity": 0.79}
  ],
  "blast_radius": {
    "files": 9,
    "tests": 3,
    "docs": 2,
    "runbooks": 1
  },
  "missing_evidence": [
    "No recent runbook entry for session rollback",
    "No passing test tied to token refresh flow"
  ],
  "answer_or_action": "..."
}
```

## Outcome semantics

- `admit`: evidence and precedent are strong enough to answer or recommend action
- `abstain`: evidence is insufficient, so the system should refuse a confident answer
- `escalate`: near matches exist, but a stronger review step is needed

## Current alpha proof

The repo includes a reproducible FastAPI retrieval-and-decision benchmark over
50 admit/withhold cases. The checked-in report shows:

- structural binary accuracy: 84.00%
- baseline binary accuracy: 76.00%
- structural false-admit rate: 0.00%
- baseline false-admit rate: 48.00%

That matters because the product wedge is not only answering more often. It is
admitting only when evidence is structurally supported.

## MVP scope

### Implemented alpha scope

- repository ingestion plus optional local external incident corpora into a persisted knowledge base
- structural evidence retrieval with truth-pack verification
- change-impact and engineering query workflows
- action-gating workflow with allow or block enforcement on top of the same decision engine
- twin retrieval across PRs and incidents
- blast radius for code-oriented questions
- audit logging for decisions
- lifecycle and maintenance controls for persisted knowledge bases
- reproducible benchmark harness and checked-in evaluation report
- MCP server surface for IDE and agent workflows over `stdio` and `streamable-http`
- Docker evaluator kit plus demo sandbox script for design-partner setup

### Explicitly deferred

- CI packaging and required-check integrations
- multi-tenant auth, production controls, and deployment hardening
- hosted sync to Jira, PagerDuty, Slack, and Confluence APIs beyond mounted export ingestion
- multi-corpus evaluation beyond the checked-in FastAPI slice

## Implemented endpoints

- `GET /health`
- `POST /v1/knowledge-bases/ingest` with optional `external_sources`
- `GET /v1/knowledge-bases`
- `GET /v1/knowledge-bases/status`
- `DELETE /v1/knowledge-bases`
- `POST /v1/knowledge-bases/prune`
- `GET /v1/knowledge-bases/maintenance/status`
- `POST /v1/knowledge-bases/maintenance/run`
- `POST /v1/decide/query`
- `POST /v1/decide/change-impact`
- `POST /v1/decide/action`
- `GET /v1/decisions/{id}`

## Implemented MCP surfaces

- `evidence_gate_ingest_repository` with optional `external_sources`
- `evidence_gate_list_knowledge_bases`
- `evidence_gate_get_knowledge_base_status`
- `evidence_gate_decide_query`
- `evidence_gate_decide_change_impact`
- `evidence_gate_decide_action`
- `evidence_gate_get_decision`
- `evidence_gate_list_recent_decisions`
- `evidence-gate://schemas/decision-record`
- `evidence-gate://decisions/{decision_id}`
- `evidence-gate://audit/decisions.jsonl`
- `evidence_gate_review_change`

## Next contract extension

The next delivery extension after the evaluator kit and action endpoint should be:

- required-check wrappers for GitHub and GitLab

That should reuse the same `admit | abstain | escalate` contract rather than
introducing a separate CI-specific response shape.

## Minimum useful demo corpus

One real engineering repository plus:

- architecture docs
- runbooks
- merged PR summaries
- incident notes or postmortems

## Success metrics

- low false-admit rate on benchmarked change-intelligence cases
- stronger citation quality than weak baseline retrieval
- calibrated abstention instead of answer-forcing
- faster engineering investigations on change-impact questions
- higher reviewer trust in citations, twins, and escalation behavior
- at least one documented follow-on proof suite beyond the initial FastAPI slice

## Non-goals

- training a new model
- leading with compression as the product narrative
- broad chat UI before the workflow proves value
- claiming production readiness before partner-ready packaging exists
