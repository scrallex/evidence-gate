# Execution Plan

## Product target

Ship a credible technical preview for `Evidence Gate: The Reliability Layer for
AI Agents`. The first benchmarked workflow remains engineering change
intelligence. The reviewer should be able to point the service at a real
codebase and get back:

- cited evidence spans
- blast radius
- prior PR or incident twins
- `admit | abstain | escalate`
- an auditable decision record

## What is already done

### Phase 0: product collapse

- consolidated the strongest SEP research threads into one product story
- narrowed the first workflow to engineering change intelligence
- defined the canonical decision contract

### Phase 1: service alpha

- built a FastAPI application surface in this repo
- implemented structural retrieval plus truth-pack verification
- added blast radius, audit logging, and persisted repo knowledge bases
- added knowledge-base ingest, status, deletion, prune, and maintenance endpoints
- added regression tests for the current API and retrieval behavior

## What remains

### Phase 2: prove value on one real corpus

Goal:
show repeatable usefulness on a real engineering repository.

Tasks:

1. Choose one target codebase with docs, PR history, and incident material.
2. Build a benchmark set of 25 to 50 real questions.
3. Label expected citations, acceptable abstentions, and bad failure modes.
4. Compare Evidence Gate against a plain baseline retrieval or chat workflow.
5. Tune thresholds from benchmark results instead of intuition.

Exit criteria:

- the system beats the baseline on citation quality and relevance
- abstentions are legible and not random
- the demo can be repeated on demand

### Phase 3: make the repo externally reviewable

Goal:
turn the alpha into something a prospective partner can run and inspect quickly.

Tasks:

1. Add a demo corpus or a reproducible setup guide for a target repo.
2. Add a concise quickstart with example requests and expected output.
3. Add basic packaging hygiene:
   - `.gitignore`
   - runtime-output handling
   - clean README
   - release-readiness doc
4. Add CI for tests and linting.
5. Add Docker or a similarly simple one-command local run path.

Exit criteria:

- a reviewer can boot the service without repo archaeology
- generated runtime artifacts are not mixed into source control
- the repo tells an honest, coherent story

### Phase 4: partner-ready technical preview

Goal:
make the system useful enough for a prospective design partner to try on their
own corpus.

Tasks:

1. Add MCP delivery so coding agents can consume the same contract.
2. Add benchmark reporting and a short evaluation report.
3. Add maintenance-run persistence to the audit surface.
4. Add a sample demo script for ingest plus change-impact walkthrough.
5. Tighten deployment and configuration docs.

Exit criteria:

- a prospective partner can review, run, and extend the system
- the value proposition is supported by evidence, not only narrative

## Commercial sequence

### First proof

Show one repository-specific auth or session change-impact demo.

### First external review

Send a technical preview package to a prospect that includes:

- repo link
- quickstart
- sample requests
- benchmark summary
- known limitations

### Expansion after proof

- action gating
- MCP-native workflows
- stronger corpus ingestion
- broader operational and incident intelligence

## What to say no to

- polishing a UI before the benchmarked demo exists
- adding broad enterprise claims without one strong workflow
- marketing language that outruns the current alpha
- restoring stale planning docs as if they describe the current repo state
