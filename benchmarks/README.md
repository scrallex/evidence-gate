# Benchmarks

This directory contains the public proof surface for `Evidence Gate: The
Reliability Layer for AI Agents`.

Current benchmark:

- `cases/fastapi_cases.json`: 50 binary admit/withhold queries over a curated `fastapi/fastapi` corpus
- `results/fastapi_structural_vs_baseline.json`: raw run output
- `results/fastapi_structural_vs_baseline.md`: human-readable summary
- `results/value_proof_benchmarks.json`: poisoned-corpus, mixed-source, SWE-bench healing-loop, and multi-corpus results
- `results/value_proof_benchmarks.md`: combined value-proof summary

Run it again with:

```bash
python scripts/run_fastapi_benchmark.py
```

Run the extended suite with:

```bash
python scripts/run_value_proof_benchmarks.py
```

Optional knobs:

- `--swebench-instances`
- `--swebench-repos`
- `--generalization-cases-per-repo`
- `--top-k`

The benchmark corpus is built from:

- topic-specific FastAPI source files
- related tests and `docs_src` examples
- English docs
- operational runbooks derived from deployment and proxy docs
- precedent PR summaries extracted from FastAPI release notes

The comparison is explicit:

- `Evidence Gate structural`: structural retrieval plus verification-aware admit/withhold policy
- `Baseline RAG`: lexical file retrieval plus a simple score-threshold admit heuristic

The extended proof suite adds:

- a poisoned-corpus benchmark to test deprecated or unsafe lexical traps
- a mixed-source incident benchmark to test external operational blocking
- a `SWE-bench_Lite` replay with a healing retry loop that feeds `missing_evidence` back into the next attempt
- a curated multi-corpus pilot across Redis, React, and Vite to test wrong-file rejection outside Python-heavy repos
