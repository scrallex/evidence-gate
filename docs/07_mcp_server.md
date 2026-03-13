# MCP Server

`Evidence Gate` ships an MCP server for coding agents and IDEs.

It exposes the same decision contract as the HTTP API so an agent can gather
citations and blast radius before editing a risky file, then request a stricter
allow-or-block decision when needed.

## What it exposes

### Tools

- `evidence_gate_health`
- `evidence_gate_ingest_repository`
- `evidence_gate_list_knowledge_bases`
- `evidence_gate_get_knowledge_base_status`
- `evidence_gate_prepare_repository`
- `evidence_gate_decide_query`
- `evidence_gate_decide_change_impact`
- `evidence_gate_decide_action`
- `evidence_gate_gate_action_with_healing`
- `evidence_gate_get_decision`
- `evidence_gate_list_recent_decisions`

### Resources

- `evidence-gate://schemas/decision-record`
- `evidence-gate://decisions/{decision_id}`
- `evidence-gate://audit/decisions.jsonl`

### Prompt

- `evidence_gate_review_change`
- `evidence_gate_fail_explain_repair_retry`

`evidence_gate_ingest_repository` accepts:

- `repo_path`
- `refresh`
- `external_sources`

Supported `external_sources` types:

- `incidents`
- `github`
- `jira`
- `pagerduty`
- `slack`
- `confluence`

`evidence_gate_decide_change_impact` also accepts:

- `diff_summary`

`evidence_gate_decide_action` also accepts:

- `diff_summary`
- `safety_policy`

`evidence_gate_gate_action_with_healing` also accepts:

- `diff_summary`
- `safety_policy`
- `prepare_repository`
- `refresh_repository`
- `external_sources`

## Recommended fast path

For Cursor, Cline, and other MCP-native coding agents, the cleanest workflow is:

1. call `evidence_gate_prepare_repository` once per repo session or when the knowledge base may be stale
2. call `evidence_gate_gate_action_with_healing` for the actual fail-explain-repair-retry loop
3. if `next_step` is `repair_and_retry`, feed `retry_prompt` back into the next agent turn
4. rerun `evidence_gate_gate_action_with_healing` on the revised patch before presenting it as safe

That tool wraps the lower-level action gate with the two integration details most IDE agents otherwise get wrong:

- ensuring the repository is actually indexed before the first decision
- turning a blocked decision into an explicit retry prompt instead of forcing the client to reverse-engineer `missing_evidence`

Example mixed-source ingest payload:

```json
{
  "repo_path": "/absolute/path/to/repo",
  "external_sources": [
    {
      "type": "pagerduty",
      "path": "/absolute/path/to/pagerduty"
    },
    {
      "type": "jira",
      "path": "/absolute/path/to/jira"
    },
    {
      "type": "github",
      "path": "/absolute/path/to/github_prs"
    },
    {
      "type": "confluence",
      "path": "/absolute/path/to/confluence"
    }
  ]
}
```

If you want those directories generated from live systems instead of manual
exports, use `scripts/fetch_live_exports.py` first. It fetches recent GitHub,
Jira, and PagerDuty data into ingest-ready directories while preserving the
existing MCP and HTTP ingest contract.

## Local stdio

Run the server locally:

```bash
evidence-gate-mcp
```

For local IDEs that struggle with relative env paths, prefer the wrapper script:

```bash
./scripts/run_mcp_stdio.sh
```

Or without the console script:

```bash
python -m evidence_gate.mcp
```

This is the best starting point for single-user local IDE integration.

## Streamable HTTP

Run the server as a networked MCP endpoint:

```bash
evidence-gate-mcp --transport streamable-http --host 127.0.0.1 --port 8001
```

The MCP endpoint will be available at:

```text
http://127.0.0.1:8001/mcp
```

## Cursor config

Cursor supports project-scoped `.cursor/mcp.json` files as well as global MCP
configuration. Example project-scoped stdio entry:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "type": "stdio",
      "command": "/absolute/path/to/evidence-gate/scripts/run_mcp_stdio.sh",
      "env": {
        "EVIDENCE_GATE_AUDIT_ROOT": "/absolute/path/to/evidence-gate-audit",
        "EVIDENCE_GATE_KB_ROOT": "/absolute/path/to/evidence-gate-kb"
      },
      "envFile": "/absolute/path/to/evidence-gate/.env"
    }
  }
}
```

Example remote or local HTTP entry:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

Cursor usage note:
prime the session with `evidence_gate_fail_explain_repair_retry` when you want
the assistant to automatically interpret `retry_prompt` as the next coding
instruction instead of a passive warning.

## Cline config

You can register the stdio server through the Cline CLI:

```bash
cline mcp add evidence-gate -- /absolute/path/to/evidence-gate/scripts/run_mcp_stdio.sh
```

Or use a checked-in `cline_mcp_settings.json` entry:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "type": "stdio",
      "command": "/absolute/path/to/evidence-gate/scripts/run_mcp_stdio.sh",
      "env": {
        "EVIDENCE_GATE_AUDIT_ROOT": "/absolute/path/to/evidence-gate-audit",
        "EVIDENCE_GATE_KB_ROOT": "/absolute/path/to/evidence-gate-kb"
      },
      "autoApprove": [
        "evidence_gate_health",
        "evidence_gate_prepare_repository",
        "evidence_gate_gate_action_with_healing",
        "evidence_gate_decide_query"
      ],
      "disabled": false
    }
  }
}
```

Example remote or local HTTP entry:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8001/mcp",
      "autoApprove": [
        "evidence_gate_health",
        "evidence_gate_prepare_repository",
        "evidence_gate_gate_action_with_healing"
      ],
      "timeout": 60,
      "disabled": false
    }
  }
}
```

Cline usage note:
prefer `evidence_gate_gate_action_with_healing` over the raw action gate unless
you are deliberately building your own retry orchestration.

## SWE-agent or other shell-tool agents

SWE-agent-style tool bundles often execute shell commands rather than speaking
MCP directly. Use the included bridge script:

```bash
python scripts/run_agent_gate.py \
  --repo-path /absolute/path/to/repo \
  --action-summary "Review the auth/session change before editing code." \
  --changed-path src/session.py
```

The script prints JSON with:

- `preparation`
- `action_decision`
- `retry_prompt`
- `next_step`
- `strongest_evidence_sources`
- `twin_case_sources`

That lets a shell-tool agent follow the same loop as MCP-native IDE clients:

1. run the bridge tool
2. if `next_step` is `repair_and_retry`, use `retry_prompt` as the next model instruction
3. rerun the bridge tool on the revised patch before reporting success

## Recommended agent behavior

For risky engineering edits:

1. Call `evidence_gate_prepare_repository` first when the knowledge base may be missing or stale.
2. Call `evidence_gate_decide_change_impact` first when the user wants blast radius, citations, or planning help without a hard gate.
3. Pass `diff_summary` whenever a code review, PR, or patch already has a concrete diff summary available.
4. Prefer `evidence_gate_gate_action_with_healing` over the raw action gate when you want the full fail-explain-repair-retry loop.
5. Use `safety_policy` only when the caller intends to enforce explicit CI or delivery thresholds.
6. If the decision is `abstain` or `escalate`, do not call the change safe.
7. Surface the missing evidence and cite the strongest evidence spans.
8. Inspect any returned PR or incident twins before continuing.
9. Ingest external exports before asking questions that depend on them.
10. If the agent is evaluating the same repo that hosts the Evidence Gate runtime, keep audit and knowledge-base roots outside that repo.

## Troubleshooting

- If a local client fails to start the server because `command` is not resolved, use an absolute path to `./scripts/run_mcp_stdio.sh`.
- If the server starts but the client sees empty audit or knowledge-base roots, set `EVIDENCE_GATE_AUDIT_ROOT` and `EVIDENCE_GATE_KB_ROOT` to absolute paths.
- If Cursor or Cline is orchestrating the coding loop directly, prefer `evidence_gate_gate_action_with_healing`; it already returns the retry prompt and next-step guidance.
- If a shell-tool agent such as SWE-agent is not MCP-native, use `python scripts/run_agent_gate.py` as the bridge tool instead of reimplementing the retry contract in prompts.
- If you change the MCP workflow in this repo itself, update `runbooks/mcp_agent_troubleshooting.md`; that file is the checked-in operational runbook for this integration surface.
- If the IDE launches the server outside the repo root, avoid relative paths such as `var/audit`; use absolute paths instead.
- If you are evaluating the Evidence Gate repo itself, do not reuse repo-local `var/` paths for audit or knowledge-base storage. Use absolute paths outside the checkout, such as `/tmp/evidence-gate-audit` and `/tmp/evidence-gate-kb`.
- If you want agents to inspect prior system decisions, use `evidence_gate_list_recent_decisions` or read `evidence-gate://audit/decisions.jsonl`.

For Codex-oriented setup guidance, see `docs/09_agent_skills.md`.
