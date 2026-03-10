# Repo Audit and Delivery Gameplan

## Executive Read

This repository is a product-formation workspace, not an implementation repo.
It already contains a coherent thesis, MVP shape, and source bundle for
`Evidence Gate`, but it does not yet contain the application code needed to
ship the product.

The most valuable tangible to deliver next is:

`Evidence Gate Alpha for engineering change intelligence`

That alpha should answer one concrete engineering question on one real codebase
and return:

- cited evidence spans
- blast radius
- twin cases
- `admit | abstain | escalate`
- an auditable decision log

If that works repeatedly, the product story is credible. If it does not, the
research remains a thesis rather than a sellable surface.

## Audit Summary

### What this repo does well

- Frames one sharp product wedge instead of many research branches.
- Narrows the first workflow to engineering change intelligence.
- Defines a concrete response contract in `docs/03_mvp_spec.md`.
- Preserves the highest-value source documents and extracted text.
- Captures the key negative lesson from the trading work: a gate must own the
  decision path, not sit beside it.

### What is actually in this repo

- `README.md`
- four core planning docs in `docs/`
- one source index in `sources/SOURCE_INDEX.md`
- ten imported source documents in `sources/raw/`
- ten extracted source texts in `sources/extracted/`
- one local sync script in `scripts/sync_sources.sh`

### What is missing here

- no application package
- no API server
- no MCP server
- no canonical schemas or models
- no benchmark set
- no demo corpus
- no tests
- no CI
- no packaging or deployment path

### Primary audit finding

The documents imply that the reusable implementation pieces are already "in the
repo", but they are not in this repo. They exist as sibling directories in the
parent workspace:

- `../structural-manifold-compression`
- `../structural-manifold-compression/SEP-mcp`
- `../score`

That means the first real execution task is not "wire the pieces together" in
place. It is to decide how to import or extract the minimum useful slices from
those sibling repos into this product surface.

### Secondary audit findings

1. The product framing is stronger than the implementation reality.
2. `structural-manifold-compression` has stronger evidence for retrieval than
   for compression, so compression should not lead the commercial story.
3. `SEP-mcp` appears strongest on blast radius and code search; its chaos score
   is supporting context, not the core value driver.
4. `score` is useful for truth-pack, verification, and twin flows, but its own
   README says the heavy native manifold logic still needs to be ported or
   wrapped from SEP core.
5. `scripts/sync_sources.sh` is machine-specific and not portable because it
   copies from hard-coded desktop paths.

## Source-Derived Product Rules

These are the durable constraints supported by the docs and source bundle:

1. Structural retrieval is the wedge.
2. Recurrence is the admission primitive.
3. Twin retrieval turns rejection into escalation.
4. Evaluation and calibration are part of the product, not research garnish.
5. The gate must own the answer or action contract.
6. Blast radius is a first-class output for the engineering workflow.
7. Abstention must be calibrated so the product remains usable.

## Best Tangible To Deliver

The right first tangible is not a broad AI reliability platform and not a new
UI. It is a demo-grade backend plus MCP surface for one workflow:

`If we change auth or session handling, what code, tests, docs, runbooks, and prior incidents are impacted, and is there enough evidence to recommend the change confidently?`

### Deliverable definition

Ship an `Evidence Gate Alpha` that:

- ingests one engineering corpus
- indexes code, docs, PR notes, and incidents
- answers change-impact questions
- verifies evidence spans
- surfaces twin cases
- computes blast radius
- returns `admit | abstain | escalate`
- writes one audit record per decision

### Non-goals for this alpha

- broad chat UI
- generic enterprise memory
- compression-led marketing
- reviving trading as the external story
- action gating before the answer/change-impact path is stable

## Reuse Map

Use only the smallest slices that directly serve the alpha.

| Need | Source | Reuse target |
|---|---|---|
| Structural corpus build and retrieval | `../structural-manifold-compression/demo/` | corpus ingestion, manifold generation, retrieval primitives |
| Structural node and verification ideas | `../structural-manifold-compression` | evidence ranking and sidecar-style verification |
| Blast radius and MCP patterns | `../structural-manifold-compression/SEP-mcp` | repo ingest, code search, AST dependency tracing, MCP wrapper |
| Truth-pack and span verification | `../score/scripts/reality_filter_*` | evidence verification, receipts, decision logging |
| Twin retrieval and query benches | `../score/scripts/sbi_*` | twin lookup and benchmark harness |

### Files worth extracting first

- `../structural-manifold-compression/demo/build_corpus.py`
- `../structural-manifold-compression/demo/generate_manifold.py`
- `../structural-manifold-compression/demo/retrieval.py`
- `../structural-manifold-compression/SEP-mcp/mcp_server.py`
- `../structural-manifold-compression/SEP-mcp/src/manifold/ast_deps.py`
- `../score/scripts/reality_filter_pack.py`
- `../score/scripts/reality_filter_service.py`
- `../score/scripts/sbi_build_queries.py`
- `../score/scripts/sbi_bench.py`

## Recommended Product Home

Turn this repository into the actual integration home for `Evidence Gate`.

Do not keep using it only as a planning folder. That would preserve clarity but
delay value. The next code added here should become the canonical service
surface.

Recommended top-level additions:

- `app/evidence_gate/`
- `app/evidence_gate/api/`
- `app/evidence_gate/decision/`
- `app/evidence_gate/ingest/`
- `app/evidence_gate/retrieval/`
- `app/evidence_gate/verification/`
- `app/evidence_gate/blast_radius/`
- `app/evidence_gate/audit/`
- `tests/`
- `benchmarks/`
- `demo/`

## Delivery Gameplan

## Phase 1: Establish the build surface

Goal:
make this repo the service home instead of another planning branch.

Tasks:

1. Add the Python application skeleton and dependency manifest.
2. Choose one runtime stack: FastAPI + Pydantic + Valkey + SQLite/JSONL audit log.
3. Add configuration for thresholds, corpora, and backend toggles.
4. Decide how sibling repos are consumed:
   - short term: import or vendor selected modules
   - medium term: extract shared libraries cleanly
5. Replace or isolate the non-portable source sync flow.

Exit criteria:

- the app boots locally
- configuration loads cleanly
- one health endpoint works
- the dependency strategy is written down

## Phase 2: Define the canonical contract

Goal:
lock the product contract before wiring features.

Tasks:

1. Implement models for:
   - `DecisionRecord`
   - `EvidenceSpan`
   - `TwinCase`
   - `BlastRadius`
   - `MissingEvidence`
   - `ThresholdConfig`
2. Freeze the response shape from `docs/03_mvp_spec.md`.
3. Define decision semantics for:
   - `admit`
   - `abstain`
   - `escalate`
4. Define audit log fields:
   - request
   - retrieved evidence
   - thresholds used
   - decision
   - explanation
   - latency

Exit criteria:

- schemas serialize cleanly
- JSON examples round-trip
- every downstream module can code to one contract

## Phase 3: Build one ingestion path

Goal:
ingest one real engineering corpus end to end.

Tasks:

1. Choose one demo repository with:
   - code
   - architecture docs
   - runbooks
   - merged PR notes
   - incident or postmortem notes
2. Normalize all inputs into one manifest with source type metadata.
3. Build document chunking plus structural indexing.
4. Build repo indexing for code search and dependency analysis.
5. Build truth-pack artifacts for verification and twin lookup.

Exit criteria:

- one command ingests the full corpus
- code and non-code assets share a common metadata model
- the ingest output is versioned and repeatable

## Phase 4: Structural retrieval and verification

Goal:
return evidence that is both relevant and supportable.

Tasks:

1. Reuse structural retrieval from `structural-manifold-compression`.
2. Keep sidecar-style logic as a verification feature, not the primary ranker.
3. Verify candidate spans through the truth-pack flow from `score`.
4. Return evidence spans with support metadata:
   - score
   - source type
   - verification outcome
   - freshness if available
5. Add twin retrieval for near-match precedent.

Exit criteria:

- queries return ranked evidence spans
- unsupported spans are filtered or marked weak
- twin lookup returns useful precedents for at least some benchmark cases

## Phase 5: Change-impact workflow

Goal:
make the first workflow materially better than chat.

Tasks:

1. Integrate blast radius tracing from `SEP-mcp`.
2. Map impacted files to tests, docs, and runbooks where possible.
3. Add support for questions framed as:
   - "what breaks if"
   - "what should change with"
   - "what has precedent for"
4. Return blast radius in the same decision payload as evidence and twins.

Exit criteria:

- `change-impact` responses return impacted artifacts
- blast radius is auditable and traceable to source paths
- the output is clearly more operational than generic retrieval

## Phase 6: Decision engine and telemetry

Goal:
turn retrieval into a reliability product rather than a search demo.

Tasks:

1. Implement a deterministic decision layer using:
   - evidence strength
   - recurrence or precedent count
   - hazard or support risk
   - blast radius severity
   - missing evidence signals
2. Start with simple thresholds, not a learned policy.
3. Add health metrics inspired by the recurrence paper:
   - decision freshness
   - threshold parity checks
   - monotonicity of support vs admission
4. Write one audit record per decision.

Exit criteria:

- the system can explain why it admitted, abstained, or escalated
- decisions are stable under repeated runs
- telemetry is sufficient to calibrate thresholds later

## Phase 7: API and MCP surface

Goal:
expose one backend through the two surfaces that matter first.

Tasks:

1. Implement:
   - `POST /v1/decide/query`
   - `POST /v1/decide/change-impact`
   - `GET /v1/decisions/{id}`
2. Defer `POST /v1/decide/action` until the first two paths are credible.
3. Add MCP tools that call the same backend contract.
4. Ensure API and MCP share models, logging, and thresholds.

Exit criteria:

- the same question can be executed via HTTP and MCP
- every decision is reproducible from the audit log

## Phase 8: Benchmark and calibration

Goal:
prove the alpha is useful on one corpus instead of only sounding plausible.

Tasks:

1. Build 25 to 50 benchmark prompts:
   - change impact
   - runbook lookup
   - incident reuse
   - missing evidence
2. Label:
   - expected citations
   - acceptable abstentions
   - acceptable escalations
3. Compare against a weak baseline:
   - plain repo chat
   - naive RAG
4. Measure:
   - citation coverage
   - hallucination rate
   - abstention rate
   - time to useful answer
5. Tune thresholds from benchmark evidence, not instinct.

Exit criteria:

- the alpha beats the baseline on citation quality
- abstentions are explainable
- at least one repeatable demo case is clearly convincing

## Phase 9: Demo packaging

Goal:
turn the alpha into something a buyer or pilot partner can evaluate quickly.

Tasks:

1. Create a scripted demo around auth or session change impact.
2. Save 3 to 5 golden decision records.
3. Produce one case-study style report with:
   - question
   - evidence
   - decision
   - audit log
4. Add a short operator runbook.

Exit criteria:

- the demo can be run repeatedly in under 10 minutes
- the output looks like a product, not a lab notebook

## Suggested Sequence and Timebox

If executed tightly, this is a 4-6 week alpha plan:

- Week 1: Phases 1-2
- Week 2: Phase 3
- Week 3: Phases 4-5
- Week 4: Phases 6-7
- Week 5: Phase 8
- Week 6: Phase 9 and cleanup

## Risks To Manage Early

1. Dependency sprawl:
   importing whole sibling repos will drag in too much research surface.
2. Native complexity:
   start with Python wrappers or existing compiled artifacts where possible.
3. Evaluation leakage:
   generated benchmark questions alone will overstate quality.
4. Over-abstention:
   a strict gate that refuses everything is not a product.
5. Product drift:
   if the system becomes "search plus scores" instead of a decision contract,
   it will repeat the sidecar failure mode.

## Immediate Next Tasks

These are the next concrete tasks to execute in order:

1. Decide that `/sep/evidence-gate` is the implementation home.
2. Scaffold the service and canonical models in this repo.
3. Extract the minimum retrieval, blast radius, and truth-pack modules from the
   sibling repos.
4. Choose the demo corpus and build the first ingest manifest.
5. Implement the `change-impact` endpoint first.
6. Add audit logging from day one.
7. Build the benchmark before polishing any UI.

## Bottom Line

This repo already contains the strategy for a real product. What it does not
yet contain is the product.

The shortest path to something valuable is to stop expanding the planning layer
and use this repo to build one narrow, auditable `Evidence Gate` alpha for
engineering change intelligence.
