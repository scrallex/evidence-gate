from __future__ import annotations

import json
from pathlib import Path

from evidence_gate.config import Settings
from evidence_gate.ingest.confluence_export import ConfluenceExportIngestor
from evidence_gate.ingest.jira_export import JiraExportIngestor
from evidence_gate.ingest.local_repo import LocalRepoIngestor
from evidence_gate.ingest.markdown_incident import MarkdownIncidentIngestor
from evidence_gate.ingest.pagerduty_incident import PagerDutyIncidentIngestor
from evidence_gate.ingest.slack_incident import SlackIncidentIngestor
from evidence_gate.retrieval.structural import build_knowledge_base_from_ingestors


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_local_repo_ingestor_collects_repository_documents(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / "docs" / "auth.md", "# Auth\n\nAuth rollback details.\n")
    _write(repo_root / "src" / "auth.py", "def refresh_token():\n    return 'ok'\n")

    documents = LocalRepoIngestor(repo_root).collect_documents()

    assert len(documents) == 2
    assert any(document.path == "docs/auth.md" for document in documents)
    assert any(document.path == "src/auth.py" for document in documents)


def test_markdown_incident_ingestor_maps_json_exports_to_incident_documents(tmp_path: Path) -> None:
    incident_root = tmp_path / "incidents"
    incident_root.mkdir(parents=True)
    payload = {
        "title": "Session rollback required",
        "description": "Token refresh failures required a rollback.",
        "author": "incident-bot",
        "url": "https://example.com/incidents/1842",
        "created_at": "2026-03-10T12:00:00+00:00",
    }
    (incident_root / "incident_1842.json").write_text(json.dumps(payload), encoding="utf-8")

    documents = MarkdownIncidentIngestor(incident_root).collect_documents()

    assert len(documents) == 1
    assert documents[0].source_type.value == "incident"
    assert documents[0].metadata is not None
    assert documents[0].metadata.author == "incident-bot"
    assert documents[0].metadata.external_url == "https://example.com/incidents/1842"


def test_hybrid_ingestors_build_knowledge_base_with_external_incident_support(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    incident_root = tmp_path / "incidents"
    _write(repo_root / "docs" / "auth.md", "# Auth\n\nToken refresh and rollback flows.\n")
    _write(repo_root / "src" / "session.py", "def session_guard():\n    return 'ok'\n")
    incident_root.mkdir(parents=True)
    (incident_root / "incident_1842.md").write_text(
        "# Incident 1842\n\nSession rollback was required after auth cache issues.\n",
        encoding="utf-8",
    )

    knowledge_base = build_knowledge_base_from_ingestors(
        [LocalRepoIngestor(repo_root), MarkdownIncidentIngestor(incident_root)],
        Settings(),
    )
    matches = knowledge_base.truth_pack.structural_search(
        "Which auth incident required session rollback?",
        top_k=5,
    )

    assert any(match.span.source.startswith("external_incidents/") for match in matches)


def test_jira_export_ingestor_maps_ticket_exports_to_documents(tmp_path: Path) -> None:
    jira_root = tmp_path / "jira"
    jira_root.mkdir(parents=True)
    (jira_root / "issues.json").write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "key": "BILL-204",
                        "summary": "Duplicate-charge safeguard regressed",
                        "description": "<p>Billing retries can double-charge customers.</p>",
                        "status": {"name": "Done"},
                        "issuetype": {"name": "Bug"},
                        "epic": {"key": "BILL-200"},
                        "labels": ["billing", "safety"],
                        "creator": {"displayName": "Billing Bot"},
                        "browse_url": "https://jira.example.com/browse/BILL-204",
                        "updated": "2026-03-10T12:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    documents = JiraExportIngestor(jira_root).collect_documents()

    assert len(documents) == 1
    assert documents[0].path == "external_jira/BILL-204.md"
    assert documents[0].source_type.value == "doc"
    assert "Duplicate-charge safeguard regressed" in documents[0].content
    assert documents[0].metadata is not None
    assert documents[0].metadata.author == "Billing Bot"
    assert documents[0].metadata.external_url == "https://jira.example.com/browse/BILL-204"


def test_pagerduty_and_slack_ingestors_collect_incident_documents(tmp_path: Path) -> None:
    pagerduty_root = tmp_path / "pagerduty"
    slack_root = tmp_path / "slack" / "billing-incidents"
    pagerduty_root.mkdir(parents=True)
    slack_root.mkdir(parents=True)

    (pagerduty_root / "incidents.json").write_text(
        json.dumps(
            {
                "incidents": [
                    {
                        "incident_number": 4417,
                        "title": "Billing duplicate-charge incident",
                        "description": "<p>Duplicate-charge safeguards failed during retries.</p>",
                        "status": "resolved",
                        "service": {"summary": "billing"},
                        "urgency": "high",
                        "assigned_to_user": {"summary": "On-call"},
                        "html_url": "https://pagerduty.example.com/incidents/4417",
                        "created_at": "2026-03-10T12:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (slack_root / "2026-03-10.json").write_text(
        json.dumps(
            [
                {
                    "ts": "1741600000.123456",
                    "text": "Billing retries are double-charging customers.",
                    "user_profile": {"display_name": "ops-bot"},
                },
                {
                    "ts": "1741600300.123456",
                    "thread_ts": "1741600000.123456",
                    "text": "Mitigation: disable retries and start the rollback.",
                    "user_profile": {"display_name": "incident-commander"},
                },
            ]
        ),
        encoding="utf-8",
    )

    pagerduty_documents = PagerDutyIncidentIngestor(pagerduty_root).collect_documents()
    slack_documents = SlackIncidentIngestor(slack_root.parent).collect_documents()

    assert len(pagerduty_documents) == 1
    assert pagerduty_documents[0].path == "external_pagerduty/4417.md"
    assert pagerduty_documents[0].source_type.value == "incident"
    assert pagerduty_documents[0].metadata is not None
    assert pagerduty_documents[0].metadata.author == "On-call"

    assert len(slack_documents) == 1
    assert slack_documents[0].path.startswith("external_slack/billing-incidents/")
    assert slack_documents[0].source_type.value == "incident"
    assert "Mitigation: disable retries" in slack_documents[0].content
    assert slack_documents[0].metadata is not None
    assert slack_documents[0].metadata.author == "ops-bot"


def test_confluence_export_ingestor_maps_pages_to_document_records(tmp_path: Path) -> None:
    confluence_root = tmp_path / "confluence"
    confluence_root.mkdir(parents=True)
    (confluence_root / "pages.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "title": "Billing Architecture",
                        "body": {"storage": {"value": "<p>Duplicate-charge guards live in the ledger path.</p>"}},
                        "space": {"key": "ARCH"},
                        "version": {
                            "by": {"displayName": "Staff Architect"},
                            "when": "2026-03-10T12:00:00+00:00",
                        },
                        "_links": {
                            "base": "https://wiki.example.com",
                            "webui": "/spaces/ARCH/pages/99",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    documents = ConfluenceExportIngestor(confluence_root).collect_documents()

    assert len(documents) == 1
    assert documents[0].path == "external_confluence/ARCH/Billing-Architecture.md"
    assert documents[0].source_type.value == "doc"
    assert "Duplicate-charge guards live in the ledger path." in documents[0].content
    assert documents[0].metadata is not None
    assert documents[0].metadata.author == "Staff Architect"
    assert documents[0].metadata.external_url == "https://wiki.example.com/spaces/ARCH/pages/99"
