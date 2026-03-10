# Benchmarks

This directory contains the public proof surface for `Evidence Gate`.

Current benchmark:

- `cases/fastapi_cases.json`: 50 binary admit/withhold queries over a curated `fastapi/fastapi` corpus
- `results/fastapi_structural_vs_baseline.json`: raw run output
- `results/fastapi_structural_vs_baseline.md`: human-readable summary

Run it again with:

```bash
python scripts/run_fastapi_benchmark.py
```

The benchmark corpus is built from:

- topic-specific FastAPI source files
- related tests and `docs_src` examples
- English docs
- operational runbooks derived from deployment and proxy docs
- precedent PR summaries extracted from FastAPI release notes

The comparison is explicit:

- `Evidence Gate structural`: structural retrieval plus verification-aware admit/withhold policy
- `Baseline RAG`: lexical file retrieval plus a simple score-threshold admit heuristic
