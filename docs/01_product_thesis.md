# Product Thesis

## Short version

The strongest commercialization path here is a verified admission layer for AI
systems.

The recurring invention across the earlier research threads is not a new
model and not compression as the primary story. It is a structural reliability
layer that decides whether a model or agent is supported enough to answer or
act.

## Foundational product principles

### 1. Structural retrieval is the wedge

The cleanest external story is text-first structural retrieval with hazard-gated
verification. That is legible to buyers with large corpora and immediate LLM
reliability pain.

### 2. Recurrence is the primitive

The simplest durable primitive is repeated state plus low hazard equals
admission. That translates well beyond any original research setting into
"this request has enough precedent in the corpus to proceed."

### 3. Twin retrieval turns a block into an escalation path

The system should not only reject weak cases; it should surface the closest
prior cases, explain the mismatch, and make escalation actionable.

### 4. Evidence discipline is part of the product, not a research accessory

Evidence Gate needs fact tables, auditable labels, threshold calibration, and
benchmark discipline. That operating posture is part of the product, not a
research accessory.

### 5. Architectural fit matters more than local gate quality

A gate can look strong in isolation and still fail if it sits outside the real
decision path. For the product, the reliability layer has to own the answer or
action contract itself.

## Product claim

Evidence Gate is the reliability layer for AI agents. Before an agent answers
or acts, the gate decides whether the request is structurally supported by
evidence and precedent in the target corpus.

## Buyer and first workflow

### Buyer

AI platform teams, developer tooling teams, and enterprise engineering orgs with large internal
corpora: code, docs, runbooks, PRs, tickets, and incident history.

### First benchmarked workflow

Engineering change intelligence:

"If we change auth or session handling, what code, tests, docs, prior PRs, and incidents are
impacted, and is there enough evidence to recommend the change confidently?"

This is stronger than generic chat because the outcome is operational:

- blast radius
- cited evidence spans
- twin cases
- decision to admit, abstain, or escalate

## What to stop pitching

- Compression as the main product claim
- Universal manifold or physics framing
- Trading as the market-facing story
- Research breadth over one sharp reliability workflow

## Product test

If a buyer cannot understand the value in one sentence, the framing is too abstract.

The sentence should be:

"Evidence Gate: The Reliability Layer for AI Agents."
