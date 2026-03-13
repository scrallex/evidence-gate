# Evidence Gate Value Proof Report

This report extends the checked-in FastAPI benchmark with four additional proof paths:
a poisoned-corpus benchmark, a mixed-source incident blocking benchmark,
a SWE-bench replay with a healing retry loop, and a cross-language multi-corpus pilot.

## 1. Poisoned Corpus Benchmark

- Cases: 48
- Structural binary accuracy: 81.25%
- Baseline binary accuracy: 56.25%
- Structural false-admit rate: 12.50%
- Baseline false-admit rate: 87.50%

## 2. Multi-Source Incident Blocking Benchmark

- Cases: 100
- Repo-only block rate: 0.00%
- Mixed-source block rate: 80.00%
- Incident twin hit rate: 80.00%
- Incremental block rate from external evidence: 80.00%

## 3. SWE-bench Replay With Healing Loop

Fast-suite note:
the checked-in `value_proof_benchmarks` run still keeps a compact 4-task
SWE-bench slice so the full proof suite stays lightweight. The representative
dataset-scale artifact is now `benchmarks/results/swebench_lite_full_replay.md`,
which reports 32.67% initial gold-path allow, 50.67% healed gold-path allow,
and 1.00% wrong-file false-allow across all 300 `SWE-bench_Lite` tasks.

- Dataset: princeton-nlp/SWE-bench_Lite
- Cases: 4 across 4 repositories
- Initial gold-path allow rate: 25.00%
- Healed gold-path allow rate: 75.00%
- Healing retry rate: 75.00%
- Healing success rate: 66.67%
- Initial test-gap block rate: 75.00%
- Decoy-path false-allow rate: 0.00%
- Baseline allow rate: 100.00%
- Alignment-gap trigger rate: 100.00%

## 4. Multi-Corpus Generalization Pilot

- Cases: 12 across 3 repositories
- Gold-path allow rate: 75.00%
- Decoy-path false-allow rate: 0.00%
- Source-hit rate: 33.33%
- Test-hit rate: 66.67%

Per-repository detail:
- facebook/react: commit 014138df8786, language=javascript, gold allow=100.00%, decoy false-allow=0.00%, source hit=25.00%, test hit=25.00%
- redis/redis: commit 753c9f616f71, language=c, gold allow=75.00%, decoy false-allow=0.00%, source hit=25.00%, test hit=100.00%
- vitejs/vite: commit b9187e04e816, language=typescript, gold allow=50.00%, decoy false-allow=0.00%, source hit=50.00%, test hit=75.00%

## Findings

- Evidence Gate retains a much lower false-admit profile than a lexical baseline on deliberately poisoned corpora.
- External incident evidence can now block a change that a repo-only review would otherwise allow.
- On the compact SWE-bench replay, changed-path alignment blocked every wrong-file decoy while the healing loop raised gold-path allow from 25.00% to 75.00%. On the standalone 300-task replay, the same pattern persists with a more realistic 32.67% to 50.67% uplift and 1.00% wrong-file false-allow.
- The healing loop turns `missing_evidence` into a compiler-like retry instruction instead of treating `escalate` as a terminal failure.
- After the JS or TS test-classification and workspace-alias fixes, the cross-language pilot reached 75.00% gold-path allow with 0.00% false-allow.

## Limitations

- The SWE-bench run is a replay benchmark over official tasks, not a full autonomous-agent pass-rate study.
- The checked-in fast SWE-bench slice uses a 4-repo sample by default so the full proof suite completes quickly; use `benchmarks/results/swebench_lite_full_replay.md` for the full 300-task result.
- The mixed-source benchmark is synthetic but exercises the live Jira, PagerDuty, Slack, and Confluence ingestors.
- The multi-corpus pilot is still a curated slice; scale it out to more repositories and cases if you need a broader confidence interval.
- The cross-language source-hit rate is still only 33.33%, so JS or TS workspace-to-source linking remains partial.
- Evidence Gate remains strongest on Python repositories; JavaScript, TypeScript, and C still rely on lighter import parsing today.
