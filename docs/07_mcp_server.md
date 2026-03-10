# MCP Server

`Evidence Gate` now ships a first-cut MCP server for coding agents and IDEs.

It exposes the same decision contract as the HTTP API so an agent can ask for a
change-impact decision before it edits a risky file.

## What it exposes

### Tools

- `evidence_gate_health`
- `evidence_gate_ingest_repository`
- `evidence_gate_list_knowledge_bases`
- `evidence_gate_get_knowledge_base_status`
- `evidence_gate_decide_query`
- `evidence_gate_decide_change_impact`
- `evidence_gate_get_decision`

### Resources

- `evidence-gate://schemas/decision-record`
- `evidence-gate://decisions/{decision_id}`

### Prompt

- `evidence_gate_review_change`

## Local stdio

Run the server locally:

```bash
evidence-gate-mcp
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

Example `mcp.json` entry for a local stdio server:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "type": "stdio",
      "command": "evidence-gate-mcp",
      "env": {
        "EVIDENCE_GATE_AUDIT_ROOT": "${workspaceFolder}/var/audit",
        "EVIDENCE_GATE_KB_ROOT": "${workspaceFolder}/var/knowledge_bases"
      }
    }
  }
}
```

Example remote or local HTTP entry:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

## Cline config

Example `cline_mcp_settings.json` entry for a local stdio server:

```json
{
  "mcpServers": {
    "evidence-gate": {
      "command": "evidence-gate-mcp",
      "env": {
        "EVIDENCE_GATE_AUDIT_ROOT": "/absolute/path/to/var/audit",
        "EVIDENCE_GATE_KB_ROOT": "/absolute/path/to/var/knowledge_bases"
      },
      "alwaysAllow": [
        "evidence_gate_health",
        "evidence_gate_get_knowledge_base_status",
        "evidence_gate_decide_query",
        "evidence_gate_decide_change_impact"
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
      "url": "http://127.0.0.1:8001/mcp",
      "disabled": false
    }
  }
}
```

## Recommended agent behavior

For risky engineering edits:

1. Call `evidence_gate_decide_change_impact` before proposing the change.
2. If the decision is `abstain` or `escalate`, stop calling the change safe.
3. Surface the missing evidence and cite the strongest evidence spans.
4. Inspect any returned PR or incident twins before continuing.
