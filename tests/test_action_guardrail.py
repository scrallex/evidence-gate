from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_action_guardrail


def test_run_action_guardrail_ingests_before_blocking_and_writes_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "action.json"
    comment_path = tmp_path / "comment.md"
    github_output = tmp_path / "github-output.txt"
    calls: dict[str, object] = {}

    def _fake_ingest_endpoint(
        *,
        api_url: str,
        repo_path: str,
        refresh: bool,
        external_sources: list[dict[str, str]],
        timeout_seconds: int,
    ) -> tuple[int, dict[str, object]]:
        calls["ingest"] = {
            "api_url": api_url,
            "repo_path": repo_path,
            "refresh": refresh,
            "external_sources": external_sources,
            "timeout_seconds": timeout_seconds,
        }
        return 200, {
            "status": "built",
            "repo_fingerprint": "repo-fingerprint-123",
        }

    def _fake_action_endpoint(
        *,
        api_url: str,
        repo_path: str,
        action_summary: str,
        changed_paths: list[str],
        diff_summary: str | None,
        safety_policy: dict[str, object] | None,
        top_k: int,
        timeout_seconds: int,
    ) -> tuple[int, dict[str, object]]:
        calls["action"] = {
            "api_url": api_url,
            "repo_path": repo_path,
            "action_summary": action_summary,
            "changed_paths": changed_paths,
            "diff_summary": diff_summary,
            "safety_policy": safety_policy,
            "top_k": top_k,
            "timeout_seconds": timeout_seconds,
        }
        return 403, {
            "allowed": False,
            "status": "block",
            "failure_reason": (
                "Action blocked because Evidence Gate safety thresholds were violated: "
                "Blast radius files 4 exceeded policy limit 1."
            ),
            "policy_violations": [
                "Blast radius files 4 exceeded policy limit 1.",
            ],
            "decision_record": {
                "decision": "escalate",
                "decision_id": "decision-123",
                "blast_radius": {"files": 4, "tests": 1, "docs": 1, "runbooks": 1},
                "missing_evidence": [
                    "Safety policy violation: Blast radius files 4 exceeded policy limit 1."
                ],
                "twin_cases": [{"source": "external_pagerduty/4417.md"}],
                "evidence_spans": [{"source": "docs/billing.md"}],
                "explanation": "Decision escalate after safety policy enforcement.",
            },
        }

    monkeypatch.setattr(run_action_guardrail, "_call_ingest_endpoint", _fake_ingest_endpoint)
    monkeypatch.setattr(run_action_guardrail, "_call_action_endpoint", _fake_action_endpoint)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_action_guardrail.py",
            "--api-url",
            "http://127.0.0.1:8000",
            "--repo-path",
            "/workspace/target",
            "--action-summary",
            "Review the billing PR before merge.",
            "--changed-paths-json",
            '["services/billing.py"]',
            "--external-sources-json",
            '[{"type":"pagerduty","path":"/workspace/exports/pagerduty"}]',
            "--diff-summary",
            "Removed duplicate-charge safeguards from the billing authorization flow.",
            "--safety-policy-json",
            '{"max_blast_radius_files":1,"require_incident_precedent":true}',
            "--refresh-knowledge-base",
            "--output",
            str(output_path),
            "--comment-output",
            str(comment_path),
            "--github-output",
            str(github_output),
            "--fail-on-block",
        ],
    )

    exit_code = run_action_guardrail.main()

    assert exit_code == 1
    assert calls["ingest"] == {
        "api_url": "http://127.0.0.1:8000",
        "repo_path": "/workspace/target",
        "refresh": True,
        "external_sources": [{"type": "pagerduty", "path": "/workspace/exports/pagerduty"}],
        "timeout_seconds": 90,
    }
    assert calls["action"] == {
        "api_url": "http://127.0.0.1:8000",
        "repo_path": "/workspace/target",
        "action_summary": "Review the billing PR before merge.",
        "changed_paths": ["services/billing.py"],
        "diff_summary": "Removed duplicate-charge safeguards from the billing authorization flow.",
        "safety_policy": {
            "max_blast_radius_files": 1,
            "require_incident_precedent": True,
        },
        "top_k": 5,
        "timeout_seconds": 90,
    }

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision_record"]["decision"] == "escalate"
    assert payload["policy_violations"] == ["Blast radius files 4 exceeded policy limit 1."]

    comment = comment_path.read_text(encoding="utf-8")
    assert "Evidence Gate: Block (Escalate)" in comment
    assert "Policy violations" in comment
    assert "external_pagerduty/4417.md" in comment
    assert "Suggested Retry Prompt" in comment

    output_lines = github_output.read_text(encoding="utf-8").splitlines()
    assert "allowed=false" in output_lines
    assert "status_code=403" in output_lines
    assert "decision=escalate" in output_lines
    assert "decision_id=decision-123" in output_lines
    assert "ingest_status=built" in output_lines
    assert "repo_fingerprint=repo-fingerprint-123" in output_lines
    assert any(line.startswith("failure_reason=Action blocked because Evidence Gate safety thresholds were violated:") for line in output_lines)
    assert any(line.startswith('missing_evidence_json=["Safety policy violation: Blast radius files 4 exceeded policy limit 1."]') for line in output_lines)
    assert any(line.startswith('policy_violations_json=["Blast radius files 4 exceeded policy limit 1."]') for line in output_lines)
    assert any("retry_prompt=Evidence Gate blocked the previous attempt because:" in line for line in output_lines)


def test_run_action_guardrail_merges_live_external_sources_before_ingest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: dict[str, object] = {}

    def _fake_live_sources(**kwargs) -> list[dict[str, str]]:
        calls["live"] = kwargs
        return [{"type": "github", "path": "/workspace/live_exports/github"}]

    def _fake_ingest_endpoint(
        *,
        api_url: str,
        repo_path: str,
        refresh: bool,
        external_sources: list[dict[str, str]],
        timeout_seconds: int,
    ) -> tuple[int, dict[str, object]]:
        calls["ingest"] = {
            "api_url": api_url,
            "repo_path": repo_path,
            "refresh": refresh,
            "external_sources": external_sources,
            "timeout_seconds": timeout_seconds,
        }
        return 200, {"status": "built", "repo_fingerprint": "repo-fingerprint-456"}

    def _fake_action_endpoint(
        *,
        api_url: str,
        repo_path: str,
        action_summary: str,
        changed_paths: list[str],
        diff_summary: str | None,
        safety_policy: dict[str, object] | None,
        top_k: int,
        timeout_seconds: int,
    ) -> tuple[int, dict[str, object]]:
        calls["action"] = {
            "api_url": api_url,
            "repo_path": repo_path,
            "action_summary": action_summary,
            "changed_paths": changed_paths,
            "diff_summary": diff_summary,
            "safety_policy": safety_policy,
            "top_k": top_k,
            "timeout_seconds": timeout_seconds,
        }
        return 200, {
            "allowed": True,
            "status": "allow",
            "policy_violations": [],
            "decision_record": {
                "decision": "admit",
                "decision_id": "decision-456",
                "blast_radius": {"files": 1, "tests": 1, "docs": 0, "runbooks": 0},
                "missing_evidence": [],
                "twin_cases": [{"source": "external_github_prs/pr_42.md"}],
                "evidence_spans": [{"source": "services/billing.py"}],
                "explanation": "Decision admit based on recent PR precedent and local evidence.",
            },
        }

    monkeypatch.setattr(run_action_guardrail, "materialize_live_external_sources", _fake_live_sources)
    monkeypatch.setattr(run_action_guardrail, "_call_ingest_endpoint", _fake_ingest_endpoint)
    monkeypatch.setattr(run_action_guardrail, "_call_action_endpoint", _fake_action_endpoint)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_action_guardrail.py",
            "--api-url",
            "http://127.0.0.1:8000",
            "--repo-path",
            "/workspace/target",
            "--action-summary",
            "Review the billing PR before merge.",
            "--changed-paths-json",
            '["services/billing.py"]',
            "--external-sources-json",
            '[{"type":"pagerduty","path":"/workspace/live_exports/pagerduty"}]',
            "--live-output-root",
            str(tmp_path / "live"),
            "--live-visible-root",
            "/workspace/live_exports",
            "--github-repository",
            "acme/billing",
        ],
    )

    exit_code = run_action_guardrail.main()

    assert exit_code == 0
    assert calls["live"] == {
        "output_root": tmp_path / "live",
        "visible_root": Path("/workspace/live_exports"),
        "github_repository": "acme/billing",
        "github_lookback_days": 30,
        "jira_base_url": "",
        "jira_user_email": "",
        "jira_project_keys": "",
        "jira_lookback_days": 30,
        "confluence_base_url": "",
        "confluence_user_email": "",
        "confluence_space_keys": "",
        "confluence_cql": "",
        "confluence_lookback_days": 30,
        "slack_channel_ids": "",
        "slack_lookback_days": 30,
        "pagerduty_lookback_days": 30,
        "timeout_seconds": 90,
    }
    assert calls["ingest"] == {
        "api_url": "http://127.0.0.1:8000",
        "repo_path": "/workspace/target",
        "refresh": False,
        "external_sources": [
            {"type": "pagerduty", "path": "/workspace/live_exports/pagerduty"},
            {"type": "github", "path": "/workspace/live_exports/github"},
        ],
        "timeout_seconds": 90,
    }
