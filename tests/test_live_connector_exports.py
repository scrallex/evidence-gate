from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import live_connector_exports


def test_materialize_live_external_sources_writes_normalized_exports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        live_connector_exports,
        "fetch_recent_github_pull_requests",
        lambda **kwargs: [
            {
                "number": 42,
                "title": "Restore duplicate-charge safeguards",
                "body": "Adds back the billing guard.",
            }
        ],
    )
    monkeypatch.setattr(
        live_connector_exports,
        "fetch_recent_jira_issues",
        lambda **kwargs: [
            {
                "key": "BILL-42",
                "summary": "Billing guard rollback",
                "description": "Customer-impacting duplicate-charge issue.",
            }
        ],
    )
    monkeypatch.setattr(
        live_connector_exports,
        "fetch_recent_pagerduty_incidents",
        lambda **kwargs: [
            {
                "incident_number": 4417,
                "title": "Billing duplicate-charge incident",
                "description": "Guardrail failed in production.",
            }
        ],
    )

    output_root = tmp_path / "live"
    sources = live_connector_exports.materialize_live_external_sources(
        output_root=output_root,
        visible_root=Path("/workspace/live_exports"),
        github_repository="acme/billing",
        github_token="github-token",
        jira_base_url="https://acme.atlassian.net",
        jira_api_token="jira-token",
        jira_user_email="dev@acme.test",
        jira_project_keys="BILL",
        pagerduty_token="pagerduty-token",
    )

    assert sources == [
        {"type": "github", "path": "/workspace/live_exports/github"},
        {"type": "jira", "path": "/workspace/live_exports/jira"},
        {"type": "pagerduty", "path": "/workspace/live_exports/pagerduty"},
    ]
    github_payload = json.loads((output_root / "github" / "pulls.json").read_text(encoding="utf-8"))
    jira_payload = json.loads((output_root / "jira" / "issues.json").read_text(encoding="utf-8"))
    pagerduty_payload = json.loads((output_root / "pagerduty" / "incidents.json").read_text(encoding="utf-8"))

    assert github_payload["repository"] == "acme/billing"
    assert github_payload["pulls"][0]["number"] == 42
    assert jira_payload["issues"][0]["key"] == "BILL-42"
    assert pagerduty_payload["incidents"][0]["incident_number"] == 4417


def test_materialize_live_external_sources_requires_jira_base_url_when_token_present(
    tmp_path: Path,
) -> None:
    try:
        live_connector_exports.materialize_live_external_sources(
            output_root=tmp_path / "live",
            jira_api_token="jira-token",
        )
    except ValueError as exc:
        assert "JIRA_BASE_URL" in str(exc)
    else:
        raise AssertionError("Expected live Jira fetch configuration error.")
