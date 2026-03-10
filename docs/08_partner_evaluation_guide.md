# Partner Evaluation Guide

This guide is the shortest path from clone to a partner-facing evaluation.

The design assumption is simple:

- the API runs on port `8000`
- the MCP streamable-http endpoint runs on port `8001`
- the target repository is mounted inside the container at `/workspace/target`

## Prerequisites

- Docker 24+ with Docker Compose
- `curl`
- `git`

## 1. Start the stack against a private repo

Pick the absolute path of the repository you want to evaluate, then start the
stack with that path mounted into the container:

```bash
EVIDENCE_GATE_REPO_MOUNT=/absolute/path/to/private-repo docker compose up -d --build
```

This mount is intentional. It keeps the container-side path stable, so every API
and MCP request can use:

```text
/workspace/target
```

## 2. Verify the services are up

Check the API:

```bash
curl http://127.0.0.1:8000/health
```

Check the MCP endpoint is listening:

```bash
curl -I http://127.0.0.1:8001/mcp
```

## 3. Build the repository knowledge base

```bash
curl -X POST http://127.0.0.1:8000/v1/knowledge-bases/ingest \
  -H "content-type: application/json" \
  -d '{"repo_path": "/workspace/target"}'
```

Successful ingest returns:

- `status`: `built`, `reused`, or `refreshed`
- `knowledge_base_path`
- `document_count`
- `span_count`

## 4. Run the core evaluation flows

Engineering evidence query:

```bash
curl -X POST http://127.0.0.1:8000/v1/decide/query \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "query": "If we change auth or session handling, what code, docs, tests, and runbooks are implicated?"
  }'
```

Change-impact decision:

```bash
curl -X POST http://127.0.0.1:8000/v1/decide/change-impact \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "change_summary": "If we change auth or session handling, what is impacted?",
    "changed_paths": ["src/session.py"]
  }'
```

Action-gating decision:

```bash
curl -X POST http://127.0.0.1:8000/v1/decide/action \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "action_summary": "Before editing auth/session handling, verify the change is safe.",
    "changed_paths": ["src/session.py"]
  }'
```

Expected behavior:

- HTTP `200`: Evidence Gate allowed the action
- HTTP `403`: Evidence Gate blocked the action and returned a structured reason

## 5. Connect an MCP client

Use the streamable-http endpoint:

```text
http://127.0.0.1:8001/mcp
```

Or point a local client at `./scripts/run_mcp_stdio.sh` if you want a stdio
server with absolute default paths for audit and knowledge-base storage.

See [07_mcp_server.md](/sep/evidence-gate/docs/07_mcp_server.md) for example
Cursor and Cline configurations.

## 6. Use the GitHub Action guardrail

The repo now ships a root [action.yml](/sep/evidence-gate/action.yml) that:

- starts the Dockerized Evidence Gate service in CI
- mounts the checked-out repo at `/workspace/target`
- calls `POST /v1/decide/action`
- writes a formatted PR comment markdown file
- optionally fails the workflow when the action is blocked

Minimal usage example:

```yaml
jobs:
  evidence-gate:
    permissions:
      contents: read
      pull-requests: write
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - id: diff
        shell: bash
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          python - <<'PY'
          import json
          import os
          import subprocess

          output = subprocess.check_output(
              ["git", "diff", "--name-only", f"{os.environ['BASE_SHA']}..{os.environ['HEAD_SHA']}"],
              text=True,
          )
          paths = [line.strip() for line in output.splitlines() if line.strip()]
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
              handle.write(f"paths={json.dumps(paths)}\n")
          PY
      - id: evidence_gate
        uses: scrallex/evidence-gate@evidence-gate
        with:
          action_summary: "Review the auth/session PR before merge"
          changed_paths: ${{ steps.diff.outputs.paths }}
          fail_on_block: "false"
```

The action exposes:

- `allowed`
- `decision`
- `decision_id`
- `response_path`
- `comment_path`

In this repository, the same pattern is already wired in
[evidence-gate-guardrail.yml](/sep/evidence-gate/.github/workflows/evidence-gate-guardrail.yml).

## 7. What a partner should provide for a useful evaluation

- one repository with a meaningful change surface
- a few known risky diff paths
- docs or runbooks that should be cited when changes are safe
- at least a few precedent artifacts such as PR summaries or incident notes

## 8. When the evaluation is working

You should be able to:

1. ingest the mounted repo once and reuse the cached knowledge base
2. ask a change-impact question and get citations plus a blast radius
3. call the action endpoint and see `200` or `403` based on the decision
4. connect an MCP client and retrieve the same contract from agent workflows

## 9. Demo sandbox

If you want a reproducible public demo before using a private repo, run:

```bash
./scripts/run_demo_sandbox.sh
```

That script clones FastAPI into `./data/repos/fastapi`, starts the Docker
stack, ingests the repo, and prints copy-paste commands for the decision
endpoints.
