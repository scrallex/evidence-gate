from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_required_check
from run_action_guardrail import GuardrailExecutionResult


def test_run_required_check_derives_gitlab_diff_and_writes_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    summary_path = tmp_path / "summary.md"
    dotenv_path = tmp_path / "evidence-gate.env"
    calls: dict[str, object] = {}

    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.setenv("CI_MERGE_REQUEST_DIFF_BASE_SHA", "base123")
    monkeypatch.setenv("CI_COMMIT_SHA", "head456")
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "42")
    monkeypatch.setenv("CI_MERGE_REQUEST_TITLE", "Guard billing retries")

    def _fake_check_output(cmd: list[str], text: bool) -> str:
        calls["diff_cmd"] = cmd
        assert cmd == ["git", "-C", str(repo_root), "diff", "--name-only", "base123..head456"]
        return "services/billing.py\ntests/test_billing.py\n"

    def _fake_execute_guardrail(**kwargs) -> GuardrailExecutionResult:
        calls["guard"] = kwargs
        return GuardrailExecutionResult(
            exit_code=1,
            status_code=403,
            payload={
                "allowed": False,
                "status": "block",
                "failure_reason": "Action blocked because Evidence Gate returned escalate for the proposed change.",
                "decision_record": {
                    "decision": "escalate",
                    "decision_id": "decision-gitlab-1",
                    "blast_radius": {"files": 4, "tests": 1, "docs": 1, "runbooks": 1},
                    "missing_evidence": ["No supporting test evidence was found for the affected flow."],
                    "twin_cases": [],
                    "evidence_spans": [{"source": "docs/billing.md"}],
                    "explanation": "Decision escalate.",
                },
                "policy_violations": [],
            },
            ingest_payload={"status": "built", "repo_fingerprint": "repo-123"},
            comment_path=None,
        )

    monkeypatch.setattr(run_required_check.subprocess, "check_output", _fake_check_output)
    monkeypatch.setattr(run_required_check, "execute_guardrail", _fake_execute_guardrail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_required_check.py",
            "--provider",
            "gitlab",
            "--api-url",
            "http://127.0.0.1:8000",
            "--repo-path",
            str(repo_root),
            "--summary-output",
            str(summary_path),
            "--dotenv-output",
            str(dotenv_path),
            "--fail-on-block",
        ],
    )

    exit_code = run_required_check.main()

    assert exit_code == 1
    assert calls["guard"]["changed_paths"] == ["services/billing.py", "tests/test_billing.py"]
    assert calls["guard"]["action_summary"] == (
        "Merge request !42: Guard billing retries. "
        "Evaluate the diff as an active merge gate and block if the safety policy is violated."
    )
    assert "Evidence Gate: Block (Escalate)" in summary_path.read_text(encoding="utf-8")

    dotenv_lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    assert "EVIDENCE_GATE_ALLOWED=false" in dotenv_lines
    assert "EVIDENCE_GATE_DECISION=escalate" in dotenv_lines
    assert any(line.startswith("EVIDENCE_GATE_CHANGED_PATHS=[\"services/billing.py\",\"tests/test_billing.py\"]") for line in dotenv_lines)


def test_run_required_check_appends_github_step_summary(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    event_path = tmp_path / "event.json"
    summary_path = tmp_path / "github-step-summary.md"
    calls: dict[str, object] = {}
    event_path.write_text(
        json.dumps(
            {
                "number": 17,
                "pull_request": {
                    "number": 17,
                    "title": "Harden session refresh flow",
                    "base": {"sha": "base456"},
                    "head": {"sha": "head789"},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    def _fake_check_output(cmd: list[str], text: bool) -> str:
        calls["diff_cmd"] = cmd
        assert cmd == ["git", "-C", str(repo_root), "diff", "--name-only", "base456..head789"]
        return "src/session.py\n"

    def _fake_execute_guardrail(**kwargs) -> GuardrailExecutionResult:
        calls["guard"] = kwargs
        return GuardrailExecutionResult(
            exit_code=0,
            status_code=200,
            payload={
                "allowed": True,
                "status": "allow",
                "failure_reason": None,
                "decision_record": {
                    "decision": "admit",
                    "decision_id": "decision-github-1",
                    "blast_radius": {"files": 2, "tests": 1, "docs": 1, "runbooks": 0},
                    "missing_evidence": [],
                    "twin_cases": [{"source": "prs/pr_17.md"}],
                    "evidence_spans": [{"source": "src/session.py"}],
                    "explanation": "Decision admit.",
                },
                "policy_violations": [],
            },
            ingest_payload={"status": "built", "repo_fingerprint": "repo-456"},
            comment_path=None,
        )

    monkeypatch.setattr(run_required_check.subprocess, "check_output", _fake_check_output)
    monkeypatch.setattr(run_required_check, "execute_guardrail", _fake_execute_guardrail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_required_check.py",
            "--provider",
            "github",
            "--api-url",
            "http://127.0.0.1:8000",
            "--repo-path",
            str(repo_root),
        ],
    )

    exit_code = run_required_check.main()

    assert exit_code == 0
    assert calls["guard"]["changed_paths"] == ["src/session.py"]
    assert calls["guard"]["action_summary"] == (
        "Pull request #17: Harden session refresh flow. "
        "Evaluate the diff as an active merge gate and block if the safety policy is violated."
    )
    assert "Evidence Gate: Allow (Admit)" in summary_path.read_text(encoding="utf-8")
