# Evidence Gate Value Proof Report

This report extends the checked-in FastAPI benchmark with three additional proof paths:
a poisoned-corpus benchmark, a mixed-source incident blocking benchmark, and a SWE-bench replay pilot.

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

## 3. SWE-bench Replay Pilot

- Dataset: princeton-nlp/SWE-bench_Lite
- Cases: 4 across 4 repositories
- Gold-path allow rate: 0.00%
- Decoy-path false-allow rate: 0.00%
- Baseline allow rate: 100.00%
- Alignment-gap trigger rate: 100.00%

## Findings

- Evidence Gate retains a much lower false-admit profile than a lexical baseline on deliberately poisoned corpora.
- External incident evidence can now block a change that a repo-only review would otherwise allow.
- On the SWE-bench replay pilot, changed-path alignment blocked every wrong-file decoy that the lexical baseline would have allowed.
- The same SWE-bench pilot admitted none of the gold patches, which means the current action gate is still too conservative to claim end-to-end autonomous task uplift.

## Limitations

- The SWE-bench run is a replay benchmark over official tasks, not a full autonomous-agent pass-rate study.
- The checked-in SWE-bench pilot uses a 4-repo slice by default so the run completes in a reasonable time; scale it out with the script flags when you want a longer sweep.
- The mixed-source benchmark is synthetic but exercises the live Jira, PagerDuty, Slack, and Confluence ingestors.
- Evidence Gate remains strongest on Python-centric repositories because blast-radius analysis is Python-specific today.
