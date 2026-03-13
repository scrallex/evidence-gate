# Benchmarks

## Top-line results

| Benchmark | Current result | Why it matters |
| --- | --- | --- |
| FastAPI structural benchmark | 84.00% accuracy, 0.00% false-admit | Core change-intelligence baseline |
| Poisoned corpus benchmark | 12.50% false-admit vs 87.50% lexical baseline | Shows resistance to unsafe near-matches |
| Mixed-source incident benchmark | 80.00% block rate with incident evidence | Shows external history can change the decision |
| SWE-bench Lite replay | 32.67% initial allow, 50.67% healed allow, +18.00 points | Shows the healing loop has real value |
| Wrong-file decoy allow rate | 1.00% | Shows the gate is not just "allow everything" |
| Multi-corpus pilot | 75.00% gold-path allow, 0.00% decoy false-allow | Shows an early Python plus JS plus TS baseline |

## Most important takeaway

The strongest current claim is not raw autonomous coding throughput. It is that
Evidence Gate can:

- keep false admits low
- use external incidents to block unsafe changes
- catch wrong-file proposals
- turn some blocked tasks into successful retries through `missing_evidence`

That is the value prop the repo can defend today.

## SWE-bench Lite summary

On the checked-in 300-task replay:

- `98/300` tasks were initially allowed
- `152/300` were allowed after the healing retry path
- `54` blocked tasks were repaired into later admits
- `147/300` initial blocks were test-gap blocks
- wrong-file false-allow stayed at `3/300`

This is why test discovery and code-to-test linking remain the highest-leverage
path for future uplift.

## Artifact links

- [fastapi_structural_vs_baseline.md](./benchmarks/results/fastapi_structural_vs_baseline.md)
- [fastapi_structural_vs_baseline.json](./benchmarks/results/fastapi_structural_vs_baseline.json)
- [value_proof_benchmarks.md](./benchmarks/results/value_proof_benchmarks.md)
- [value_proof_benchmarks.json](./benchmarks/results/value_proof_benchmarks.json)
- [swebench_lite_full_replay.md](./benchmarks/results/swebench_lite_full_replay.md)
- [swebench_lite_full_replay.json](./benchmarks/results/swebench_lite_full_replay.json)

## Reproduce

Run the fast benchmark:

```bash
python scripts/run_fastapi_benchmark.py
```

Run the broader proof suite:

```bash
python scripts/run_value_proof_benchmarks.py
```

Run the full SWE-bench Lite replay:

```bash
python scripts/run_swebench_full_replay.py
```

## Current gaps

- The repo does not yet prove final solved-task uplift against a live framework
  such as OpenHands or SWE-agent.
- Dynamic JS or TS repos still benefit from LSIF or SCIP sidecars; the current
  native graph support is real, but still bootstrap-grade.
- The benchmark story is strongest on safety and healing, not on universal
  autonomous software engineering throughput.
