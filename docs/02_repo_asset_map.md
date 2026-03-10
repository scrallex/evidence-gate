# Repo Asset Map

This repo already contains enough pieces to build a first `Evidence Gate` deliverable without
starting over. The key is to collapse them into one surface and ignore the unrelated branches.

## Assets to reuse

### 1. Structural retrieval and document indexing

Path: `structural-manifold-compression/`

Use for:

- structural document nodes
- sidecar signatures as a verification feature
- retrieval experiments and bounded reconstruction

What it already proves:

- structural retrieval is materially better than the current weak dense baseline in the locked
  benchmark
- sidecar signatures are more credible as verification than as primary ranking

### 2. Code intelligence and blast radius

Path: `structural-manifold-compression/SEP-mcp/`

Use for:

- repository ingestion
- search
- dependency tracing
- blast radius scoring
- MCP delivery for coding agents

What it already gives the product:

- the most concrete engineering workflow surface in the repo
- an existing MCP server pattern
- a strong "change impact" primitive for the first demo

### 3. Reality filter and citation pipeline

Path: `score/`

Use for:

- truth-pack ingestion
- span verification
- twin suggestion
- repaired answer flow
- benchmark harnesses for citation coverage and hallucination reduction

What it already gives the product:

- the strongest answer-verification semantics in the repo
- a practical receipts model for user-facing outputs

## Assets to keep out of the product path

These may stay in the repo, but they should not drive the first commercial deliverable:

- `trader/`
- `market_regime/`
- `sep_backtest/`
- `Laser/`
- trading-specific risk and execution modules under `scripts/trading*`

They can remain as source inspiration for recurrence, hazard, and telemetry, but not as the
product story.

## Consolidation target

The first product cut should unify the three useful surfaces above into one service:

1. Ingest code, docs, incidents, and PR history.
2. Retrieve structural evidence spans and structural twins.
3. Add blast radius for code-change questions.
4. Return one contract: `admit | abstain | escalate`.
5. Expose it through API and MCP before building a new UI.

## Real deliverable that fits the repo

The best near-term deliverable is not a general enterprise memory system. It is:

`Evidence Gate for engineering change intelligence`

That maps directly onto codebase analysis, runbook lookup, incident retrieval, and agent action
gating, all of which already have partial implementation in this repository.
