from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _structured_payload(result) -> dict[str, object]:
    if result.structuredContent is not None:
        return result.structuredContent
    if result.content and getattr(result.content[0], "text", None):
        return json.loads(result.content[0].text)
    return {}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_sample_repo(root: Path) -> None:
    _write(
        root / "src" / "session.py",
        "from src.auth import refresh_token\n\n"
        "def session_guard():\n"
        "    return refresh_token()\n",
    )
    _write(
        root / "src" / "auth.py",
        "def refresh_token():\n"
        "    return 'ok'\n",
    )
    _write(
        root / "src" / "billing.py",
        "def calculate_total_cents(subtotal_cents: int, tax_rate_percent: int) -> int:\n"
        "    return subtotal_cents + int(subtotal_cents * (tax_rate_percent / 100))\n",
    )
    _write(
        root / "tests" / "test_auth.py",
        "from src.session import session_guard\n\n"
        "def test_session_guard():\n"
        "    assert session_guard() == 'ok'\n",
    )
    _write(
        root / "docs" / "auth.md",
        "# Auth\n\nChanging auth or session handling impacts token refresh and rollback flows.\n",
    )
    _write(
        root / "runbooks" / "session_rollback.md",
        "# Session Rollback\n\nIf token refresh fails, use the session rollback procedure.\n",
    )
    _write(
        root / "prs" / "pr_1842.md",
        "# PR 1842\n\nAdjusted token refresh behavior during the auth session rollout.\n",
    )
    _write(
        root / "incidents" / "incident_2025_09_17.md",
        "# Incident\n\nSession refresh failures required rollback and auth cache cleanup.\n",
    )


async def _exercise_mcp_server(
    repo_root: Path,
    incident_root: Path,
    audit_root: Path,
    kb_root: Path,
) -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[1]
    python_path_parts = [str(project_root / "app")]
    if existing_python_path := os.environ.get("PYTHONPATH"):
        python_path_parts.append(existing_python_path)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(python_path_parts)
    env["EVIDENCE_GATE_AUDIT_ROOT"] = str(audit_root)
    env["EVIDENCE_GATE_KB_ROOT"] = str(kb_root)

    server = StdioServerParameters(
        command="python",
        args=["-m", "evidence_gate.mcp"],
        env=env,
        cwd=project_root,
    )

    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            tools = await session.list_tools()
            resources = await session.list_resources()
            resource_templates = await session.list_resource_templates()
            prompts = await session.list_prompts()

            prepare = await session.call_tool(
                "evidence_gate_prepare_repository",
                {
                    "repo_path": str(repo_root),
                    "external_sources": [
                        {
                            "type": "incidents",
                            "path": str(incident_root),
                        }
                    ],
                },
            )
            ingest = await session.call_tool(
                "evidence_gate_ingest_repository",
                {
                    "repo_path": str(repo_root),
                    "external_sources": [
                        {
                            "type": "incidents",
                            "path": str(incident_root),
                        }
                    ],
                },
            )
            status = await session.call_tool(
                "evidence_gate_get_knowledge_base_status",
                {"repo_path": str(repo_root)},
            )
            decision = await session.call_tool(
                "evidence_gate_decide_change_impact",
                {
                    "repo_path": str(repo_root),
                    "change_summary": "If we change auth or session handling, what is impacted?",
                    "changed_paths": ["src/session.py"],
                },
            )
            decision_payload = _structured_payload(decision)
            decision_id = decision_payload.get("decision_id")
            assert isinstance(decision_id, str)
            action_decision = await session.call_tool(
                "evidence_gate_decide_action",
                {
                    "repo_path": str(repo_root),
                    "action_summary": "Before changing auth/session handling, verify the action is safe.",
                    "changed_paths": ["src/session.py"],
                },
            )
            blocked_action_decision = await session.call_tool(
                "evidence_gate_decide_action",
                {
                    "repo_path": str(repo_root),
                    "action_summary": "Before changing auth/session handling, verify the action is safe.",
                    "changed_paths": ["src/session.py"],
                    "diff_summary": "Legacy sentinel rollback required after token refresh regression.",
                    "safety_policy": {
                        "escalate_on_incident_match": True,
                    },
                },
            )
            healing_loop = await session.call_tool(
                "evidence_gate_gate_action_with_healing",
                {
                    "repo_path": str(repo_root),
                    "action_summary": "Before changing billing total calculation, verify the action is safe.",
                    "changed_paths": ["src/billing.py"],
                    "safety_policy": {
                        "require_test_evidence": True,
                    },
                },
            )
            recent_decisions = await session.call_tool(
                "evidence_gate_list_recent_decisions",
                {"limit": 5},
            )
            external_query = await session.call_tool(
                "evidence_gate_decide_query",
                {
                    "repo_path": str(repo_root),
                    "query": "Which incident mentioned legacy sentinel rollback?",
                },
            )

            decision_resource = await session.read_resource(f"evidence-gate://decisions/{decision_id}")
            schema_resource = await session.read_resource("evidence-gate://schemas/decision-record")
            audit_resource = await session.read_resource("evidence-gate://audit/decisions.jsonl")
            prompt = await session.get_prompt(
                "evidence_gate_review_change",
                {
                    "repo_path": str(repo_root),
                    "change_summary": "Review an auth/session change before editing code.",
                    "changed_paths": "src/session.py",
                },
            )
            healing_prompt = await session.get_prompt(
                "evidence_gate_fail_explain_repair_retry",
                {
                    "repo_path": str(repo_root),
                    "action_summary": "Review a billing change before editing code.",
                    "changed_paths": "src/billing.py",
                    "diff_summary": "Modify the billing tax calculation without test coverage.",
                },
            )

    return {
        "tools": [tool.name for tool in tools.tools],
        "resources": [str(resource.uri) for resource in resources.resources],
        "resource_templates": [str(resource.uriTemplate) for resource in resource_templates.resourceTemplates],
        "prompts": [prompt_def.name for prompt_def in prompts.prompts],
        "prepare": _structured_payload(prepare),
        "ingest": _structured_payload(ingest),
        "status": _structured_payload(status),
        "decision": decision_payload,
        "action_decision": _structured_payload(action_decision),
        "blocked_action_decision": _structured_payload(blocked_action_decision),
        "healing_loop": _structured_payload(healing_loop),
        "recent_decisions": _structured_payload(recent_decisions),
        "external_query": _structured_payload(external_query),
        "decision_resource": decision_resource.contents[0].text,
        "schema_resource": schema_resource.contents[0].text,
        "audit_resource": audit_resource.contents[0].text,
        "prompt_messages": prompt.messages,
        "healing_prompt_messages": healing_prompt.messages,
    }


def test_mcp_stdio_server_exposes_evidence_gate_workflow(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    incident_root = tmp_path / "external_incidents"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    _write(
        incident_root / "incident_1842.md",
        "# Incident 1842\n\nLegacy sentinel rollback required after the token refresh regression.\n",
    )

    payload = asyncio.run(_exercise_mcp_server(repo_root, incident_root, audit_root, kb_root))

    assert "evidence_gate_health" in payload["tools"]
    assert "evidence_gate_ingest_repository" in payload["tools"]
    assert "evidence_gate_decide_change_impact" in payload["tools"]
    assert "evidence_gate_decide_action" in payload["tools"]
    assert "evidence_gate_prepare_repository" in payload["tools"]
    assert "evidence_gate_gate_action_with_healing" in payload["tools"]
    assert "evidence_gate_list_recent_decisions" in payload["tools"]
    assert "evidence-gate://schemas/decision-record" in payload["resources"]
    assert "evidence-gate://audit/decisions.jsonl" in payload["resources"]
    assert "evidence-gate://decisions/{decision_id}" in payload["resource_templates"]
    assert "evidence_gate_review_change" in payload["prompts"]
    assert "evidence_gate_fail_explain_repair_retry" in payload["prompts"]

    prepare_payload = payload["prepare"]
    assert isinstance(prepare_payload, dict)
    assert prepare_payload["ready"] is True
    assert prepare_payload["status"] == "ready"
    assert prepare_payload["preparation_action"] == "ingested"

    ingest_payload = payload["ingest"]
    assert isinstance(ingest_payload, dict)
    assert ingest_payload["status"] in {"built", "reused"}

    status_payload = payload["status"]
    assert isinstance(status_payload, dict)
    assert status_payload["status"] == "ready"

    decision_payload = payload["decision"]
    assert decision_payload["decision"] == "admit"
    assert decision_payload["blast_radius"]["files"] >= 2
    assert any(span["source"] == "docs/auth.md" for span in decision_payload["evidence_spans"])
    assert any(twin["source"] == "prs/pr_1842.md" for twin in decision_payload["twin_cases"])

    action_payload = payload["action_decision"]
    assert action_payload["allowed"] is True
    assert action_payload["decision_record"]["decision"] == "admit"

    blocked_action_payload = payload["blocked_action_decision"]
    assert blocked_action_payload["allowed"] is False
    assert blocked_action_payload["status"] == "block"
    assert blocked_action_payload["decision_record"]["decision"] == "escalate"
    assert blocked_action_payload["policy_violations"] == [
        "Policy blocks changes that match prior incident precedent."
    ]
    assert any(
        twin["source"] == "external_incidents/incident_1842.md"
        for twin in blocked_action_payload["decision_record"]["twin_cases"]
    )

    recent_decisions = payload["recent_decisions"]
    assert len(recent_decisions["decisions"]) >= 3

    external_query_payload = payload["external_query"]
    assert any(
        twin["source"] == "external_incidents/incident_1842.md"
        for twin in external_query_payload["twin_cases"]
    )

    healing_payload = payload["healing_loop"]
    assert healing_payload["next_step"] == "repair_and_retry"
    assert healing_payload["retry_prompt"].startswith("Evidence Gate blocked the previous attempt because:")
    assert healing_payload["action_decision"]["allowed"] is False
    assert healing_payload["action_decision"]["decision_record"]["decision"] == "escalate"
    assert healing_payload["preparation"]["ready"] is True

    decision_resource = json.loads(payload["decision_resource"])
    assert decision_resource["decision_id"] == decision_payload["decision_id"]

    schema_resource = json.loads(payload["schema_resource"])
    assert "properties" in schema_resource
    assert "decision" in schema_resource["properties"]

    assert decision_payload["decision_id"] in payload["audit_resource"]

    prompt_messages = payload["prompt_messages"]
    assert prompt_messages
    assert "evidence_gate_decide_change_impact" in prompt_messages[0].content.text

    healing_prompt_messages = payload["healing_prompt_messages"]
    assert healing_prompt_messages
    assert "evidence_gate_prepare_repository" in healing_prompt_messages[0].content.text
    assert "evidence_gate_gate_action_with_healing" in healing_prompt_messages[0].content.text
