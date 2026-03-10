# Value Proof

This repo now includes a broader value-proof suite beyond the checked-in FastAPI
benchmark.

Artifacts:

- [value_proof_benchmarks.md](/sep/evidence-gate/benchmarks/results/value_proof_benchmarks.md)
- [value_proof_benchmarks.json](/sep/evidence-gate/benchmarks/results/value_proof_benchmarks.json)
- [run_value_proof_benchmarks.py](/sep/evidence-gate/scripts/run_value_proof_benchmarks.py)

The suite covers three distinct claims:

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

## 3. SWE-bench replay pilot

Question:
does the gate distinguish a gold patch path from an obviously wrong-file
proposal on real benchmark tasks?

Current result:

- 4 official `SWE-bench_Lite` tasks across 4 repositories
- gold-path allow rate: 0.00%
- decoy-path false-allow rate: 0.00%
- lexical baseline allow rate: 100.00%

Interpretation:
this is proof of safety bias, not yet proof of autonomous agent uplift. The
gate reliably rejects wrong-file proposals, but it is still too conservative to
greenlight the gold patches in this pilot because most tasks lacked strong
test, runbook, or precedent evidence.

## Honest conclusion

What is now proven:

- Evidence Gate lowers false admits on poisoned corpora.
- Evidence Gate can use external operational evidence to block changes.
- Evidence Gate can detect path-evidence mismatches that a lexical baseline
  would wave through.

What is not yet proven:

- higher end-to-end autonomous task completion on SWE-bench or a comparable
  agent benchmark

That means the current repo supports a strong claim about reliability and
negative-ROI prevention, but not yet a full claim about autonomous software
engineering throughput gains.
