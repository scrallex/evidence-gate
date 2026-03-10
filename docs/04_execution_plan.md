# Execution Plan

## Tangible product target

Ship a working `Evidence Gate` service for engineering change intelligence. The first customer
experience should answer a concrete question about a real codebase and return:

- cited files and spans
- blast radius
- similar prior PRs or incidents
- `admit | abstain | escalate`

If that experience works, the broader product story is credible. If it does not, nothing else in
the research matters commercially.

## Phase 0: done in this workspace

- consolidate the highest-value research sources
- define the product wedge
- map the repo assets that can be reused

## Phase 1: collapse to one service

Target outcome:
one backend that combines structural retrieval, code intelligence, and verification.

Build steps:

1. Create a new application surface named `evidence-gate` instead of extending trading code.
2. Reuse ingestion and retrieval logic from `structural-manifold-compression/`.
3. Reuse blast radius and MCP patterns from `structural-manifold-compression/SEP-mcp/`.
4. Reuse truth-pack verification and twin flows from `score/`.
5. Standardize on one decision schema and one audit log format.

Exit criteria:

- one process can ingest a repo plus docs
- one API returns the decision contract
- one log record is written for every decision

## Phase 2: first benchmark and demo

Target outcome:
prove usefulness on one engineering corpus.

Build steps:

1. Assemble a demo corpus from a real repo with docs, PR notes, and incident notes.
2. Create 25 to 50 benchmark questions around change impact, runbook lookup, and incident reuse.
3. Label expected citations and acceptable abstentions.
4. Measure:
   - citation coverage
   - hallucination rate
   - abstention rate
   - time to useful answer
5. Tune hazard and recurrence thresholds against that benchmark.

Exit criteria:

- the system beats a plain baseline chat or weak RAG setup on citation quality
- abstentions are explainable rather than random
- the demo is stable enough to show repeatedly

## Phase 3: productize the action gate

Target outcome:
gate agent actions, not only answers.

Build steps:

1. Add action intents such as `edit_code`, `run_runbook_step`, and `recommend_change`.
2. Require evidence spans and twin support before actions are admitted.
3. Escalate weak actions into review packets instead of freeform model output.
4. Record every decision for calibration and audit.

Exit criteria:

- action gating works with the same contract as Q&A
- escalation packets are useful to a human reviewer

## Commercial sequence

### Wedge

Sell the product as a reliability layer for engineering teams using AI on internal corpora.

### First proof

Show the auth or session change-impact demo on a real repository.

### Expansion

After the first engineering workflow works:

- agent action gating
- support operations runbooks
- ticket and incident reuse
- broader enterprise knowledge workflows

## What to say no to

- broad platform rebuilds before the change-intelligence demo exists
- custom UI work before API and MCP are useful
- research branches that do not improve admission, citations, twins, or escalation
- attempts to revive trading as the product narrative

## Immediate next implementation tasks

1. Create a thin `evidence-gate` service skeleton in-repo.
2. Define the canonical decision models and audit models.
3. Build one ingestion path for repo files, docs, PR notes, and incidents.
4. Wire in blast radius for code questions.
5. Return citations and twin cases in one response.
6. Add threshold configuration and decision logging.
7. Build the first benchmark set and demo script.
