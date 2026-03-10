# Product Thesis

## Short version

The strongest SEP commercialization path is a verified admission layer for AI systems.

The recurring invention across the top-ranked papers is not a new model and not compression as
the primary story. It is a structural reliability layer that decides whether a model or agent is
supported enough to answer or act.

## What to keep from the papers

### 1. Structural retrieval is the wedge

The `STM_Core_Whitepaper` is the clearest external story because it frames the system as
text-first structural retrieval with hazard-gated verification. That is legible to buyers with
large corpora and immediate LLM reliability pain.

### 2. Recurrence is the primitive

`reliability_gated_recurrence_polished` contributes the simplest durable primitive in the whole
set: repeated state plus low hazard equals admission. That translates well beyond trading into
"this request has enough precedent in the corpus to proceed."

### 3. Twin retrieval turns a block into an escalation path

`STM_Structural_Manifold_Whitepaper` adds the missing product behavior. The system should not
only reject weak cases; it should surface the closest prior cases, explain the mismatch, and make
escalation actionable.

### 4. Evidence discipline is part of the product, not a research accessory

The signal-regime papers are useful because they show the right operating posture: fact tables,
walk-forward style evaluation, auditable labels, and threshold calibration. Evidence Gate needs
that same discipline in query sets, admission logs, and calibration dashboards.

### 5. Architectural fit matters more than local gate quality

`iron_dome_methodology_2025.md` and `unified_strategy_live.md` are the most important negative
lessons. A gate can look strong in isolation and still fail if it sits outside the real decision
path. For the product, the reliability layer has to own the answer or action contract itself.

## Product claim

Evidence Gate is a reliability layer for LLM answers and agent actions. Before the model answers
or modifies anything, the gate decides whether the request is structurally supported by evidence
and precedent in the target corpus.

## Buyer and first workflow

### Buyer

AI platform teams, developer tooling teams, and enterprise engineering orgs with large internal
corpora: code, docs, runbooks, PRs, tickets, and incident history.

### First workflow

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

"Evidence Gate decides whether an AI system has enough structural evidence and precedent to
answer or act."
