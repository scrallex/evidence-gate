# MCP Agent Integration Troubleshooting Runbook

This runbook covers the operational failure modes for the Evidence Gate MCP and
agent-healing workflow.

Use it when a change touches:

- `app/evidence_gate/mcp/server.py`
- `scripts/run_agent_gate.py`
- `GUIDES.md`
- `API.md`
- `tests/test_mcp_server.py`
- `tests/test_agent_gate_script.py`
- `README.md`

## Organizational Standard

Do not present MCP workflow changes as safe until all of the following are true:

- `evidence_gate_prepare_repository` can build or reuse the knowledge base for the target repo
- `evidence_gate_gate_action_with_healing` returns a stable retry contract when the change is blocked
- the shell bridge in `scripts/run_agent_gate.py` returns `next_step`, `retry_prompt`, and evidence sources
- regression coverage exists in `tests/test_mcp_server.py` and `tests/test_agent_gate_script.py`
- this runbook still matches the actual failure and repair flow for Cursor, Cline, and SWE-agent style clients

## Blast Radius

An MCP workflow regression can affect:

- the stdio or HTTP MCP entrypoint in `app/evidence_gate/mcp/server.py`
- Cursor and Cline IDE integrations that depend on `evidence_gate_fail_explain_repair_retry`
- shell-tool agents such as SWE-agent that depend on `scripts/run_agent_gate.py`
- the repo-level setup guidance in `GUIDES.md`, `API.md`, and `README.md`
- the retry loop contract validated by `tests/test_mcp_server.py` and `tests/test_agent_gate_script.py`

Expected blast radius for the current integration surface is roughly:

- `8` files
- `2` test files
- `2` docs
- `1` runbook

## Failure Modes

Common failures for this workflow:

1. the repo is not prepared, so the first gate call has stale or missing context
2. the MCP server responds, but the agent ignores `retry_prompt` and treats the block as a passive warning
3. the shell bridge returns JSON, but the agent does not retry on `next_step=repair_and_retry`
4. the docs describe a tool or prompt name that no longer exists in `app/evidence_gate/mcp/server.py`
5. the change updates the workflow but skips the regression tests or operational runbook

## Debug Checklist

1. Confirm the local API or MCP process is healthy.
2. Prepare the repository before the first gate call.
3. Run the shell bridge against the repo and inspect `allowed`, `missing_evidence`, and `retry_prompt`.
4. Run the MCP regression tests.
5. If the gate still escalates, inspect the top evidence spans and make sure the changed test files and this runbook are being retrieved.

Example commands:

```bash
python scripts/run_agent_gate.py \
  --repo-path /sep/evidence-gate \
  --action-summary "Review the MCP and agent integration workflow changes before claiming they are safe to merge." \
  --changed-path app/evidence_gate/mcp/server.py \
  --changed-path scripts/run_agent_gate.py \
  --changed-path GUIDES.md \
  --changed-path API.md \
  --changed-path tests/test_mcp_server.py \
  --changed-path tests/test_agent_gate_script.py \
  --changed-path README.md \
  --diff-summary "Add evidence_gate_prepare_repository, evidence_gate_gate_action_with_healing, and evidence_gate_fail_explain_repair_retry; add shell bridge scripts/run_agent_gate.py; document Cursor, Cline, and SWE-agent usage in GUIDES.md and API.md; add regression coverage in tests/test_mcp_server.py and tests/test_agent_gate_script.py."
pytest -q tests/test_mcp_server.py tests/test_agent_gate_script.py
```

## Repair Guidance

If the gate blocks a workflow change:

- first add or fix the missing regression test coverage
- then update this runbook if the operational behavior or debug path changed
- rerun the gate and confirm the returned evidence includes both the relevant test files and this runbook

## Rollback

If the MCP-specific workflow is unstable:

1. fall back to `evidence_gate_decide_change_impact` and `evidence_gate_decide_action`
2. disable automated retry behavior in the client until `retry_prompt` handling is fixed
3. keep the shell bridge available for manual diagnosis
