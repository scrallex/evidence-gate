## Evidence Gate Result

- Failure reason: Action blocked because Evidence Gate safety thresholds were violated: Policy requires runbook or operational evidence.
- Missing evidence: Safety policy violation: Policy requires runbook or operational evidence.
- Strongest evidence: `app/evidence_gate/mcp/server.py`, `tests/test_mcp_server.py`, `app/evidence_gate/benchmark/fastapi.py`
- Blast radius: 7 files, 2 tests, 1 docs, 0 runbooks
- Policy: `require_runbook_evidence` with `corpus_profile=open_source`

## Operator Note

The MCP workflow change already has code and regression-test support, but it
does not satisfy the team standard for operational runbook coverage.

### Suggested Retry Prompt

Evidence Gate blocked the previous attempt because: Safety policy violation: Policy requires runbook or operational evidence. Write the operational runbook for the MCP workflow, then retry the gate.
