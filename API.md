# API

## HTTP endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `POST` | `/v1/knowledge-bases/ingest` | Build or refresh a repository knowledge base |
| `GET` | `/v1/knowledge-bases` | List cached knowledge bases |
| `GET` | `/v1/knowledge-bases/status` | Check ready or stale status for one repo |
| `DELETE` | `/v1/knowledge-bases` | Delete a cached knowledge base |
| `POST` | `/v1/knowledge-bases/prune` | Remove stale cached knowledge bases |
| `GET` | `/v1/knowledge-bases/maintenance/status` | Inspect retention settings |
| `POST` | `/v1/knowledge-bases/maintenance/run` | Run retention cleanup |
| `POST` | `/v1/decide/query` | Ask an evidence-backed repository question |
| `POST` | `/v1/decide/change-impact` | Get citations plus blast radius for a planned change |
| `POST` | `/v1/decide/action` | Run the strict merge or action gate |
| `GET` | `/v1/decisions/{id}` | Read one persisted decision |
| `GET` | `/v1/dashboard/overview` | Stakeholder metrics and blocked-action feed |

## Core decision contract

Every decision returns:

- cited `evidence_spans`
- `twin_cases` for prior incidents or PRs
- `blast_radius`
- `missing_evidence`
- a calibrated `decision`: `admit`, `abstain`, or `escalate`

The stricter action endpoint wraps that in:

- `allowed`
- `status`: `allow` or `block`
- `failure_reason`
- `policy_violations`

## Example action request

```json
{
  "repo_path": "/absolute/path/to/repo",
  "action_summary": "Review the auth/session change before merge.",
  "changed_paths": ["src/session.py"],
  "diff_summary": "Removes the legacy rollback branch.",
  "safety_policy": {
    "require_test_evidence": true,
    "require_runbook_evidence": true
  }
}
```

## MCP surface

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
- `evidence_gate_evaluate_intent`
- `evidence_gate_get_decision`
- `evidence_gate_list_recent_decisions`

### Resources

- `evidence-gate://schemas/decision-record`
- `evidence-gate://decisions/{decision_id}`
- `evidence-gate://audit/decisions.jsonl`

### Prompts

- `evidence_gate_review_change`
- `evidence_gate_fail_explain_repair_retry`
- `evidence_gate_plan_with_intent`

## Recommended usage

- Use `change-impact` when you want advisory citations and blast radius.
- Use `action` when you want allow or block behavior.
- Use `gate_action_with_healing` when the caller is an agent that should repair
  and retry instead of stopping.
- Use `evaluate_intent` when the agent should inspect incidents or runbooks
  before writing code.

## External source types

Ingest supports:

- `incidents`
- `github`
- `jira`
- `pagerduty`
- `slack`
- `confluence`
