from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import live_connector_exports
import sync_live_exports


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


def test_materialize_live_external_sources_writes_slack_and_confluence_exports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        live_connector_exports,
        "fetch_recent_confluence_pages",
        lambda **kwargs: [
            {
                "title": "Billing Architecture",
                "body": {"storage": {"value": "<p>Ledger rollback path.</p>"}},
                "space": {"key": "ARCH"},
                "version": {"by": {"displayName": "Architect"}, "when": "2026-03-12T12:00:00+00:00"},
                "_links": {"base": "https://acme.atlassian.net", "webui": "/spaces/ARCH/pages/42"},
            }
        ],
    )
    monkeypatch.setattr(
        live_connector_exports,
        "fetch_recent_slack_threads",
        lambda **kwargs: {
            "C123456": [
                {
                    "ts": "1741600000.123456",
                    "text": "Billing retries are double-charging customers.",
                    "user_profile": {"display_name": "ops-bot"},
                },
                {
                    "ts": "1741600300.123456",
                    "thread_ts": "1741600000.123456",
                    "text": "Mitigation: disable retries.",
                    "user_profile": {"display_name": "incident-commander"},
                },
            ]
        },
    )

    output_root = tmp_path / "live"
    sources = live_connector_exports.materialize_live_external_sources(
        output_root=output_root,
        visible_root=Path("/workspace/live_exports"),
        confluence_base_url="https://acme.atlassian.net/wiki",
        confluence_api_token="confluence-token",
        confluence_user_email="arch@acme.test",
        confluence_space_keys="ARCH",
        slack_bot_token="slack-token",
        slack_channel_ids="C123456",
    )

    assert sources == [
        {"type": "confluence", "path": "/workspace/live_exports/confluence"},
        {"type": "slack", "path": "/workspace/live_exports/slack"},
    ]
    confluence_payload = json.loads((output_root / "confluence" / "pages.json").read_text(encoding="utf-8"))
    slack_payload = json.loads((output_root / "slack" / "C123456" / "threads.json").read_text(encoding="utf-8"))

    assert confluence_payload["pages"][0]["title"] == "Billing Architecture"
    assert slack_payload[1]["thread_ts"] == "1741600000.123456"


def test_sync_live_exports_reuses_state_as_incremental_cursor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    moments = iter(
        [
            datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 12, 12, 5, tzinfo=timezone.utc),
        ]
    )

    monkeypatch.setattr(sync_live_exports, "datetime", type("FrozenDateTime", (), {
        "now": staticmethod(lambda tz=None: next(moments)),
        "fromisoformat": staticmethod(datetime.fromisoformat),
    }))

    def _fake_materialize(**kwargs) -> list[dict[str, str]]:
        calls.append(kwargs)
        return [{"type": "github", "path": "/workspace/live_exports/github"}]

    monkeypatch.setattr(sync_live_exports, "materialize_live_external_sources", _fake_materialize)
    state_file = tmp_path / "live" / "state.json"

    first_sources = sync_live_exports._run_sync(
        args=type(
            "Args",
            (),
            {
                "output_root": str(tmp_path / "live"),
                "visible_root": "/workspace/live_exports",
                "github_repository": "acme/billing",
                "github_lookback_days": 30,
                "jira_base_url": "",
                "jira_user_email": "",
                "jira_project_keys": "",
                "jira_lookback_days": 30,
                "pagerduty_lookback_days": 30,
                "confluence_base_url": "",
                "confluence_user_email": "",
                "confluence_space_keys": "",
                "confluence_cql": "",
                "confluence_lookback_days": 30,
                "slack_channel_ids": "",
                "slack_lookback_days": 30,
                "timeout_seconds": 90,
            },
        )(),
        state_path=state_file,
    )
    second_sources = sync_live_exports._run_sync(
        args=type(
            "Args",
            (),
            {
                "output_root": str(tmp_path / "live"),
                "visible_root": "/workspace/live_exports",
                "github_repository": "acme/billing",
                "github_lookback_days": 30,
                "jira_base_url": "",
                "jira_user_email": "",
                "jira_project_keys": "",
                "jira_lookback_days": 30,
                "pagerduty_lookback_days": 30,
                "confluence_base_url": "",
                "confluence_user_email": "",
                "confluence_space_keys": "",
                "confluence_cql": "",
                "confluence_lookback_days": 30,
                "slack_channel_ids": "",
                "slack_lookback_days": 30,
                "timeout_seconds": 90,
            },
        )(),
        state_path=state_file,
    )

    assert first_sources == [{"type": "github", "path": "/workspace/live_exports/github"}]
    assert second_sources == [{"type": "github", "path": "/workspace/live_exports/github"}]
    assert calls[0]["github_updated_since"] is None
    assert calls[1]["github_updated_since"] == datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved_state["sources"]["github"]["last_synced_at"] == "2026-03-12T12:05:00+00:00"
