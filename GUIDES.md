# Guides

## Local quickstart

Install:

```bash
python -m pip install -e '.[dev]'
```

Run the API:

```bash
uvicorn evidence_gate.api.main:app --app-dir app --reload
```

Run the MCP server:

```bash
evidence-gate-mcp
```

Run the shell bridge for non-MCP agents:

```bash
python scripts/run_agent_gate.py \
  --repo-path /absolute/path/to/repo \
  --action-summary "Review the auth/session change before editing." \
  --changed-path src/session.py
```

## Dashboard

Run the FastAPI service first, then:

```bash
cd dashboard
npm install
npm run dev
```

The dashboard reads `GET /v1/dashboard/overview` and is designed for VPs,
CTOs, and CISOs who care about prevented risk, not terminal output.

## Required checks

### GitHub

Use the checked-in wrapper:

- [evidence-gate-guardrail.yml](/sep/evidence-gate/.github/workflows/evidence-gate-guardrail.yml)

The root [action.yml](/sep/evidence-gate/action.yml) now prefers the prebuilt
image `ghcr.io/scrallex/evidence-gate:latest` and falls back to a local Docker
build only when needed.

### GitLab

Use the checked-in merge-request job:

- [evidence-gate-required-check.yml](/sep/evidence-gate/ci/gitlab/evidence-gate-required-check.yml)

### Provider-neutral runner

Both wrappers share:

- [run_required_check.py](/sep/evidence-gate/scripts/run_required_check.py)

That script computes changed paths from the CI diff and then runs the normal
action gate.

## MCP and agent integrations

Best current path for Cursor, Cline, and similar agents:

1. prepare the repository once
2. call `evidence_gate_gate_action_with_healing`
3. if blocked, feed `retry_prompt` into the next agent attempt
4. rerun before presenting the patch as safe

If you want preflight guidance before code is written, call
`evidence_gate_evaluate_intent` first.

For local IDEs that prefer stdio over streamable HTTP, use:

```bash
./scripts/run_mcp_stdio.sh
```

## Live connectors

Evidence Gate can materialize live read-only context from GitHub, Jira,
Confluence, Slack, and PagerDuty.

One-shot export:

```bash
python scripts/fetch_live_exports.py --output-root /tmp/evidence-gate-live
```

Incremental polling:

```bash
python scripts/sync_live_exports.py \
  --output-root /tmp/evidence-gate-live \
  --visible-root /tmp/evidence-gate-live
```

Operational guidance is in:

- [live_connector_operations.md](/sep/evidence-gate/runbooks/live_connector_operations.md)

## Native graphs and test discovery

For repos with dynamic imports, generated routing, or heavy TypeScript
indirection, place LSIF or SCIP sidecars under `.evidence-gate/graphs`.

The gate now uses:

- Tree-sitter JS or TS parsing
- native graph neighbors from LSIF or SCIP sidecars
- changed-path-aware test linking for likely downstream tests

This is the current path to improving healing-loop success without relaxing the
safety posture.

## Security and privacy

The alpha defaults to local structural embeddings plus a deterministic decision
engine. Organizational memory is not sent to a public model by default.

Supported backend configuration surface:

- local deterministic or structural mode
- Azure OpenAI config contract
- Ollama config contract
- vLLM config contract

Relevant environment controls live in [config.py](/sep/evidence-gate/app/evidence_gate/config.py).

## Runbooks

These are part of the product surface, not internal notes:

- [mcp_agent_troubleshooting.md](/sep/evidence-gate/runbooks/mcp_agent_troubleshooting.md)
- [live_connector_operations.md](/sep/evidence-gate/runbooks/live_connector_operations.md)
- [required_check_operations.md](/sep/evidence-gate/runbooks/required_check_operations.md)
