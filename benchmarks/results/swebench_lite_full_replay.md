# SWE-bench Lite Replay Report

This report measures Evidence Gate as a compiler-like healing loop over official SWE-bench tasks.
It is not a human-facing PR review study. It measures whether the gate blocks weak code-only attempts,
emits machine-readable `missing_evidence`, and admits stronger retries without opening the wrong-file path.

## Coverage

- Dataset: princeton-nlp/SWE-bench_Lite
- Selection mode: full
- Dataset instances: 300
- Dataset repositories: 12
- Evaluated instances: 300
- Evaluated repositories: 12
- Dataset coverage: 100.00%

## Results

- Initial gold-path allow rate: 32.67% (98/300)
- Healed gold-path allow rate: 50.67% (152/300)
- Absolute admit uplift from healing: +18.00 points (+54 cases)
- Healing retry rate: 26.00% (78/300)
- Healing success rate: 69.23% (54/78)
- Initial test-gap block rate: 49.00% (147/300)
- Wrong-file false-allow rate: 1.00% (3/300)
- Baseline allow rate: 100.00% (300/300)
- Alignment-gap trigger rate: 99.00% (297/300)

## Dataset Concentration

- Top two repositories account for 63.67% of the evaluated tasks.
- django/django: 114 cases (38.00%)
- sympy/sympy: 77 cases (25.67%)
- matplotlib/matplotlib: 23 cases (7.67%)

## Notable Misses

- All 3 wrong-file admits came from `sphinx-doc/sphinx` and concentrated on `.circleci/config.yml` decoys.

## Interpretation

Evidence Gate behaves like a compiler pass for coding agents: it rejects unsupported attempts, returns concrete diagnostics through `missing_evidence`, and raises admit rate when the retry adds the missing evidence instead of merely rephrasing the request.
The full replay is materially less optimistic than the earlier 4-task pilot: the healing loop still adds 18 percentage points of admit lift, but most tasks never enter the retry path because the current harness only retries when it can identify missing test evidence and a plausible test file.
This benchmark still replays official tasks instead of running a full autonomous agent such as OpenHands or SWE-agent end-to-end. It proves the healing contract, not final task-completion pass rate.
