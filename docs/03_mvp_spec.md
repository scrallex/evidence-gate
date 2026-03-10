# MVP Spec

## Working name

`Evidence Gate`

## Category

Reliability layer for engineering answers and agent-adjacent change analysis.

## Target user

Engineering teams using AI over internal code, docs, runbooks, PRs, and incident
history.

## User problem

Most AI systems over internal corpora retrieve text but do not decide well when
evidence is weak, stale, or structurally mismatched. They answer anyway instead
of showing the user whether the request is well-supported.

## Core promise

Before an answer or recommendation is returned, Evidence Gate decides whether the
request is structurally supported.

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

## MVP scope

### Implemented alpha scope

- repository and document ingestion into a persisted knowledge base
- structural evidence retrieval with truth-pack verification
- change-impact and engineering query workflows
- twin retrieval across PRs and incidents
- blast radius for code-oriented questions
- audit logging for decisions
- lifecycle and maintenance controls for persisted knowledge bases

### Explicitly deferred

- action gating endpoints
- MCP server surface
- benchmark corpus and formal evaluation harness
- packaging beyond local developer usage
- production auth, multi-tenant controls, and deployment hardening

## Implemented endpoints

- `GET /health`
- `POST /v1/knowledge-bases/ingest`
- `GET /v1/knowledge-bases`
- `GET /v1/knowledge-bases/status`
- `DELETE /v1/knowledge-bases`
- `POST /v1/knowledge-bases/prune`
- `GET /v1/knowledge-bases/maintenance/status`
- `POST /v1/knowledge-bases/maintenance/run`
- `POST /v1/decide/query`
- `POST /v1/decide/change-impact`
- `GET /v1/decisions/{id}`

## Next contract extension

The next API addition after the benchmark and demo package should be:

- `POST /v1/decide/action`

That should reuse the same `admit | abstain | escalate` contract rather than
introducing a separate action-specific response shape.

## Minimum useful demo corpus

One real engineering repository plus:

- architecture docs
- runbooks
- merged PR summaries
- incident notes or postmortems

## Success metrics

- stronger citation quality than weak baseline retrieval
- calibrated abstention instead of answer-forcing
- faster engineering investigations on change-impact questions
- higher reviewer trust in citations, twins, and escalation behavior

## Non-goals

- training a new model
- leading with compression as the product narrative
- broad chat UI before the workflow proves value
- claiming production readiness before benchmarked proof exists
