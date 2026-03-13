# Value Proof

This repo now includes a broader value-proof suite beyond the checked-in FastAPI
benchmark.

Artifacts:

- [value_proof_benchmarks.md](/sep/evidence-gate/benchmarks/results/value_proof_benchmarks.md)
- [value_proof_benchmarks.json](/sep/evidence-gate/benchmarks/results/value_proof_benchmarks.json)
- [run_value_proof_benchmarks.py](/sep/evidence-gate/scripts/run_value_proof_benchmarks.py)

The suite now covers four distinct claims:

## 1. Poisoned corpus resistance

Question:
does Evidence Gate avoid admitting changes when the corpus contains highly
similar but deprecated or explicitly unsafe text?

Current result:

- 48 cases
- structural false-admit rate: 12.50%
- lexical baseline false-admit rate: 87.50%

Interpretation:
this is the strongest current proof of value. The gate is materially better than
a weak lexical admit heuristic at avoiding obvious RAG traps.

## 2. Multi-source incident blocking

Question:
can external incident history change the gating outcome?

Current result:

- 100 cases
- repo-only block rate: 0.00%
- mixed-source block rate: 80.00%
- incident twin hit rate: 80.00%

Interpretation:
the new Jira, PagerDuty, Slack, and Confluence ingestors are not just passive
storage. Mixed-source evidence can now turn an otherwise-admitted change into an
`escalate` decision when policy says a matched prior incident must block the
change.

## 3. SWE-bench replay with healing loop

Artifacts:

- [swebench_lite_full_replay.md](/sep/evidence-gate/benchmarks/results/swebench_lite_full_replay.md)
- [swebench_lite_full_replay.json](/sep/evidence-gate/benchmarks/results/swebench_lite_full_replay.json)

Question:
does the gate both reject wrong-file proposals and help an agent repair an
initially incomplete patch on real benchmark tasks?

Current result:

- 300 official `SWE-bench_Lite` tasks across 12 repositories
- initial gold-path allow rate: 32.67% (`98/300`)
- healed gold-path allow rate: 50.67% (`152/300`)
- absolute admit uplift from healing: `+18.00` points (`+54` cases)
- healing retry rate: 26.00% (`78/300`)
- healing success rate: 69.23% (`54/78`)
- initial test-gap block rate: 49.00% (`147/300`)
- decoy-path false-allow rate: 1.00% (`3/300`)
- alignment-gap trigger rate: 99.00% (`297/300`)
- lexical baseline allow rate: 100.00% (`300/300`)

Interpretation:
the 300-instance run is more credible and less flattering than the old 4-task
pilot. The core claim still holds: when the harness can identify missing test
evidence and a plausible retry path, the gate turns a block into structured
repair guidance and lifts admit rate by 18 percentage points without turning
into a blanket allow.

The right way to read the remaining gap is not "the healing loop failed." Most
tasks never entered the retry path at all because the current harness only
retries missing-test cases where it can nominate a candidate test file. That is
why the replay shows 78 retries instead of 300. The benchmark is proving the
healing contract, not an unconstrained auto-fix policy.

Where the current system is still weak:

- the dataset is concentrated: `django/django` and `sympy/sympy` account for `191/300` cases, or 63.67% of the run
- all three wrong-file false allows came from `sphinx-doc/sphinx`, each admitting a `.circleci/config.yml` decoy with no alignment warning
- `147/300` initial blocks were test-gap blocks, which means test discovery and test-to-code linking remain the highest-leverage path for future uplift

Why this matters:
this is the core "compiler for agents" claim. A human-facing PR reviewer can
describe the missing test after the fact. Evidence Gate instead turns the block
into structured repair guidance that an agent can consume immediately on the
next attempt.

Limit:
even this completed full replay is still a replay benchmark, not an end-to-end
autonomous pass-rate study with OpenHands or SWE-agent. It proves that the gate
can block, diagnose, and help repair some benchmark tasks. It does not yet
prove final solved-task uplift against a live coding agent.

## 4. Multi-corpus generalization pilot

Question:
does the structural retrieval and gate behavior survive outside Python-heavy
repos?

Current result:

- 12 curated cases across Redis, React, and Vite
- gold-path allow rate: 75.00%
- decoy-path false-allow rate: 0.00%
- source-hit rate: 33.33%
- test-hit rate: 66.67%

Repository detail:

- `redis/redis` at `753c9f616f71`: 75.00% gold allow, 0.00% decoy false-allow
- `facebook/react` at `014138df8786`: 100.00% gold allow, 0.00% decoy false-allow
- `vitejs/vite` at `b9187e04e816`: 50.00% gold allow, 0.00% decoy false-allow

Interpretation:
this is now proof of a cross-language baseline, not just a kill switch. After
fixing JS or TS test classification and adding a fuzzier workspace import
resolver, the pilot moved from 25.00% to 75.00% gold allow while keeping
0.00% false-allow. That is strong enough to support a design-partner pitch
across Python, C, JavaScript, and TypeScript. It is still not proof of full
universality: the source-hit rate remains low, and Vite still admits only half
of the curated gold paths. Redis also needed one fairness fix in this pass,
adding `.tcl` test files to the ingestible text extensions so its unit and
integration tests are visible to the gate.

Native graph note:
the repo now includes an initial LSIF or SCIP sidecar path under
`.evidence-gate/graphs` so a repository can provide file-level code graph
evidence instead of relying only on the heuristic parser. The checked-in
generalization numbers above predate any graph-assisted rerun and should still
be read as heuristic-only baseline results.

## Vite limitation

Vite is the cleanest example of why Evidence Gate should optimize for safety
before throughput. The current pilot admits only 50.00% of the curated Vite
gold paths because Vite depends heavily on dynamic imports, plugin-injected
state, and virtual-module behavior that the current static heuristics cannot
fully prove. Evidence Gate correctly fails safe here: it abstains or escalates
when it cannot statically guarantee the blast radius. That is a real product
limitation, but it is also the correct reliability behavior.

The new native graph stub is the intended way out of that ceiling. If a Vite or
TypeScript repository emits LSIF or SCIP sidecars, Evidence Gate can now ingest
that file-level graph and use it for both blast radius and retrieval without
changing the surrounding decision contract. What remains unproven is the actual
throughput gain on a graph-assisted Vite rerun.

## Honest conclusion

What is now proven:

- Evidence Gate lowers false admits on poisoned corpora.
- Evidence Gate can use external operational evidence to block changes.
- Evidence Gate can detect path-evidence mismatches that a lexical baseline
  would wave through.
- Evidence Gate can improve a SWE-bench-style replay when an agent retries with
  the gate's `missing_evidence` guidance.
- Evidence Gate now shows a credible cross-language baseline on curated
  Python, C, JavaScript, and TypeScript corpora.

What is not yet proven:

- broad cross-language autonomous task completion on large JavaScript,
  TypeScript, or C codebases
- final end-to-end pass-rate uplift against a live autonomous agent such as
  SWE-agent or OpenHands

That means the current repo now supports a strong claim about reliability,
negative-ROI prevention, and a compiler-like healing loop on SWE-bench-style
tasks. It also supports an early cross-language design-partner claim. It still
does not support a broad claim of universal autonomous software engineering
throughput gains.
