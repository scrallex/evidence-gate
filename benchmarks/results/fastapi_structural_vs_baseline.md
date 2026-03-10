# FastAPI Benchmark Report

This benchmark uses a curated, reproducible slice of `fastapi/fastapi`: topic-specific source files,
tests, English docs, `docs_src` examples, operational runbooks derived from deployment docs, and
precedent PR summaries extracted from FastAPI's own release notes.

The primary decision metric is binary: `admit` versus `withhold`.
A backend is correct when it admits supported cases and withholds unsupported near-neighbor cases.

Decision policies used in this benchmark:

- `Evidence Gate structural`: admit only when structural retrieval recovers focused support, at least
  one focused precedent PR, and verified code, test, or runbook evidence.
- `Baseline RAG`: admit when the lexical top-3 mean score is at least `0.32` and at least 2 of
  the top-5 lexical hits also clear `0.32`.

## Summary

- Cases: 50 total (25 supported, 25 unsupported)
- Structural binary accuracy: 84.00%
- Baseline binary accuracy: 76.00%
- Structural true-admit rate: 68.00%
- Baseline true-admit rate: 100.00%
- Structural false-admit rate: 0.00%
- Baseline false-admit rate: 48.00%
- Structural positive path-hit rate: 88.00%
- Baseline positive path-hit rate: 76.00%

## Example Structural Wins

- fastapi-007 `websocket-routing`
  Query: If we change Socket.IO namespace authorization behavior, what FastAPI tests, docs, and precedent PRs are implicated?
  Structural: withhold | Baseline: admit
  Structural top hits: docs/en/docs/reference/background.md, fastapi/security/oauth2.py, fastapi/openapi/utils.py
  Baseline top hits: docs/en/docs/tutorial/security/oauth2-jwt.md, docs/en/docs/advanced/security/oauth2-scopes.md, prs/websocket-routing-pr-13202.md
- fastapi-011 `wsgi-middleware`
  Query: If we change Rack adapter lifecycle behavior, what FastAPI docs, examples, and precedent PRs are implicated?
  Structural: withhold | Baseline: admit
  Structural top hits: docs/en/docs/advanced/security/oauth2-scopes.md, fastapi/security/oauth2.py, docs/en/docs/reference/background.md
  Baseline top hits: docs/en/docs/advanced/security/oauth2-scopes.md, runbooks/https-runbook.md, prs/background-tasks-pr-10392.md
- fastapi-012 `wsgi-middleware`
  Query: If we change CGI gateway adapter behavior, what FastAPI docs, examples, and precedent PRs are implicated?
  Structural: withhold | Baseline: admit
  Structural top hits: fastapi/background.py, fastapi/security/oauth2.py, fastapi/applications.py
  Baseline top hits: docs/en/docs/advanced/middleware.md, docs/en/docs/advanced/security/oauth2-scopes.md, runbooks/https-runbook.md
- fastapi-015 `gzip-middleware`
  Query: If we change Brotli response compression level handling, what FastAPI docs, examples, and precedent PRs are implicated?
  Structural: withhold | Baseline: admit
  Structural top hits: fastapi/applications.py, fastapi/dependencies/utils.py, fastapi/routing.py
  Baseline top hits: runbooks/https-runbook.md, docs/en/docs/advanced/middleware.md, docs/en/docs/tutorial/security/oauth2-jwt.md
- fastapi-016 `gzip-middleware`
  Query: If we change zstd response compression behavior, what FastAPI docs, examples, and precedent PRs are implicated?
  Structural: withhold | Baseline: admit
  Structural top hits: fastapi/applications.py, fastapi/dependencies/utils.py, fastapi/routing.py
  Baseline top hits: docs/en/docs/advanced/middleware.md, runbooks/https-runbook.md, docs/en/docs/advanced/security/oauth2-scopes.md

## Notes

- This is a retrieval-and-decision benchmark, not a full answer-generation benchmark.
- Operational runbooks are derived from FastAPI's public deployment and proxy docs.
- Precedent PR artifacts are extracted from FastAPI's public release notes and stored as topic-shaped `prs/` documents.
- The baseline intentionally uses a simple repo-RAG-style admit heuristic rather than Evidence Gate's abstention logic.
