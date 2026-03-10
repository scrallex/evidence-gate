# MVP Spec

## Working name

`Evidence Gate`

## Category

Reliability layer for LLM answers and agent actions.

## Target user

Engineering teams using LLMs over internal code, docs, tickets, PRs, and incident history.

## User problem

Most RAG and agent systems retrieve text but do not decide well when evidence is weak, stale, or
structurally mismatched. They answer anyway, or they take action without enough precedent.

## Core promise

Before the model answers or acts, Evidence Gate decides whether the request is structurally
supported.

## Primary workflow

Engineering change intelligence.

Example request:

"If we change auth/session handling, what files, tests, docs, runbooks, and prior incidents are
impacted?"

## Decision contract

```json
{
  "decision": "admit | abstain | escalate",
  "hazard": 0.18,
  "recurrence": 4,
  "confidence": 0.82,
  "evidence_spans": [
    {"source": "docs/auth.md", "score": 0.91},
    {"source": "src/session.ts", "score": 0.88}
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
- `abstain`: evidence is insufficient, so the system should refuse to synthesize a confident answer
- `escalate`: near matches exist, but a human or a stronger review step is needed

## MVP scope

- repo and doc ingestion
- verified Q&A with citations
- code-change impact workflow
- twin retrieval across PRs, incidents, and docs
- configurable thresholds for hazard and admission
- API and MCP server first

## Initial endpoints

### `POST /v1/decide/query`

Question answering over code and operational documentation.

### `POST /v1/decide/change-impact`

Change-intelligence workflow for code modifications and architecture questions.

### `POST /v1/decide/action`

Gate agent actions such as edit proposals, runbook steps, or operator suggestions.

### `GET /v1/decisions/{id}`

Return the full audit record for calibration and review.

## Minimum demo corpus

One real engineering repository plus:

- architecture docs
- runbooks
- merged PR summaries
- incident notes or postmortems

## Success metrics

- lower hallucination rate on benchmarked engineering questions
- calibrated abstention rather than answer-forcing
- faster engineering investigations
- fewer irrelevant context tokens sent to the model
- higher user trust in citations, twins, and escalation behavior

## Non-goals

- training a new foundation model
- leading with compression claims
- shipping a broad chat UI first
- pitching trading or physics as the product narrative
