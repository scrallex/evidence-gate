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

Question:
does the gate both reject wrong-file proposals and help an agent repair an
initially incomplete patch on real benchmark tasks?

Current result:

- 4 official `SWE-bench_Lite` tasks across 4 repositories
- initial gold-path allow rate: 25.00%
- healed gold-path allow rate: 75.00%
- healing retry rate: 75.00%
- healing success rate: 66.67%
- decoy-path false-allow rate: 0.00%
- lexical baseline allow rate: 100.00%

Interpretation:
this is the first concrete uplift proof in the repo. Once the benchmark uses an
open-source safety policy and feeds `missing_evidence` back into the retry
prompt, the gate admits three of four gold paths while still rejecting every
wrong-file decoy. The remaining failed case healed into a path-alignment miss,
which is a real guardrail signal rather than a missing-test problem.

## 4. Multi-corpus generalization pilot

Question:
does the structural retrieval and gate behavior survive outside Python-heavy
repos?

Current result:

- 12 curated cases across Redis, React, and Vite
- gold-path allow rate: 25.00%
- decoy-path false-allow rate: 0.00%
- source-hit rate: 33.33%
- test-hit rate: 66.67%

Repository detail:

- `redis/redis` at `753c9f616f71`: 75.00% gold allow, 0.00% decoy false-allow
- `facebook/react` at `014138df8786`: 0.00% gold allow, 0.00% decoy false-allow
- `vitejs/vite` at `b9187e04e816`: 0.00% gold allow, 0.00% decoy false-allow

Interpretation:
this is proof of cross-language kill-switch behavior, not yet proof of
cross-language autonomous throughput. The decoy false-allow rate stayed at
0.00%, which is good. The low gold-path allow and source-hit rates on React and
Vite show a real retrieval gap: the current structural heuristics still miss
too much test evidence in large JavaScript and TypeScript repos. Redis also
needed one fairness fix in this pass, adding `.tcl` test files to the ingestible
text extensions so its unit and integration tests are visible to the gate.

## Honest conclusion

What is now proven:

- Evidence Gate lowers false admits on poisoned corpora.
- Evidence Gate can use external operational evidence to block changes.
- Evidence Gate can detect path-evidence mismatches that a lexical baseline
  would wave through.
- Evidence Gate can improve a SWE-bench-style replay when an agent retries with
  the gate's `missing_evidence` guidance.

What is not yet proven:

- broad cross-language autonomous task completion on large JavaScript,
  TypeScript, or C codebases
- final end-to-end pass-rate uplift against a live autonomous agent such as
  SWE-agent or OpenHands

That means the current repo now supports a strong claim about reliability,
negative-ROI prevention, and an initial healing-loop uplift on SWE-bench-style
tasks. It still does not support a broad claim of universal autonomous software
engineering throughput gains.
