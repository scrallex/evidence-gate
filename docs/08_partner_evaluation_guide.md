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

If you have exported incidents, tickets, chat history, or architecture docs
available inside the container, include them during ingest:

```bash
curl -X POST http://127.0.0.1:8000/v1/knowledge-bases/ingest \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "external_sources": [
      {"type": "pagerduty", "path": "/workspace/pagerduty"},
      {"type": "jira", "path": "/workspace/jira"},
      {"type": "slack", "path": "/workspace/slack"},
      {"type": "confluence", "path": "/workspace/confluence"}
    ]
  }'
```

The bundled evaluator stack mounts only the target repository by default. If
you want extra corpora in the container, mount them explicitly through a custom
Compose override or use a host-local Evidence Gate process instead of the
bundled container.

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

For open-source corpora or agent benchmarks, calibrate the safety policy to the
corpus instead of requiring enterprise artifacts:

```bash
curl -X POST http://127.0.0.1:8000/v1/decide/action \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "action_summary": "Before merging the patch, verify the change is safe.",
    "changed_paths": ["src/cache.js"],
    "safety_policy": {
      "corpus_profile": "open_source",
      "require_test_evidence": true
    }
  }'
```

If this open-source gate still returns HTTP `403`, treat
`decision_record.missing_evidence` as repair instructions for the next agent
attempt instead of ending the run immediately.

For design-partner framing, this behaves more like a compiler for agent PRs
than a passive reviewer: the first blocked attempt returns concrete diagnostics,
and the follow-up attempt is expected to satisfy them before submission.

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

The repo ships a root [action.yml](/sep/evidence-gate/action.yml) that:

- starts the Dockerized Evidence Gate service in CI
- mounts the checked-out repo at `/workspace/target`
- optionally ingests mounted external corpora before gating
- computes a diff summary from `base_sha` and `head_sha` when available
- calls `POST /v1/decide/action` with optional `safety_policy`
- writes a formatted PR comment markdown file
- optionally fails the workflow when the action is blocked

The action can ingest any mounted export directory that the container or target
service can see through `external_sources`. If those corpora live outside the
checkout, mount them into the runner or point the action at an already-running
Evidence Gate service that can see those paths.

Billing-style merge gate example:

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
          action_summary: "Review the billing PR before merge"
          changed_paths: ${{ steps.diff.outputs.paths }}
          base_sha: ${{ github.event.pull_request.base.sha }}
          head_sha: ${{ github.event.pull_request.head.sha }}
          external_sources: >-
            [
              {"type":"jira","path":"/workspace/target/exports/jira"},
              {"type":"pagerduty","path":"/workspace/target/exports/pagerduty"},
              {"type":"slack","path":"/workspace/target/exports/slack"},
              {"type":"confluence","path":"/workspace/target/exports/confluence"}
            ]
          safety_policy: >-
            {"max_blast_radius_files":6,"max_hazard":0.45,"min_confidence":0.55,"require_test_evidence":true,"require_precedent":true,"require_incident_precedent":true}
          fail_on_block: "false"
      - name: Enforce guardrail decision
        if: ${{ steps.evidence_gate.outputs.allowed != 'true' }}
        shell: bash
        run: |
          echo "Evidence Gate blocked this pull request." >&2
          exit 1
```

The action exposes:

- `allowed`
- `decision`
- `decision_id`
- `response_path`
- `comment_path`

For autonomous-agent evaluations, prefer `fail_on_block: "false"` on the first
pass. Read the blocked response, inject the `missing_evidence` strings back into
the agent prompt, and only fail the workflow if the follow-up attempt is still
blocked.
- `ingest_status`
- `repo_fingerprint`

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

## 10. Additional proof artifacts

If a partner asks for broader evidence than the checked-in FastAPI report, point
them at:

- [value_proof_benchmarks.md](/sep/evidence-gate/benchmarks/results/value_proof_benchmarks.md)
- [10_value_proof.md](/sep/evidence-gate/docs/10_value_proof.md)

Those documents show the current shape of the claim honestly: strong false-admit
prevention and mixed-source blocking, but not yet a demonstrated uplift on
end-to-end autonomous task completion.
