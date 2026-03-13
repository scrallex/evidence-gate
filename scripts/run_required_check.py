#!/usr/bin/env python3
"""Provider-native wrapper for running Evidence Gate as a required CI check."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from format_pr_comment import build_comment
from run_action_guardrail import execute_guardrail


def _detect_provider(explicit: str) -> str:
    if explicit != "auto":
        return explicit
    if os.environ.get("GITLAB_CI"):
        return "gitlab"
    if os.environ.get("GITHUB_ACTIONS"):
        return "github"
    return "generic"


def _resolve_refs(provider: str, repo_path: Path, base_sha: str, head_sha: str) -> tuple[str, str]:
    if base_sha and head_sha:
        return base_sha, head_sha

    if provider == "gitlab":
        inferred_base = os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", "")
        inferred_head = os.environ.get("CI_COMMIT_SHA", "")
        if inferred_base and inferred_head:
            return inferred_base, inferred_head

    if provider == "github":
        event_path = os.environ.get("GITHUB_EVENT_PATH", "")
        if event_path:
            try:
                payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            pull_request = payload.get("pull_request", {}) if isinstance(payload, dict) else {}
            base = pull_request.get("base", {}) if isinstance(pull_request, dict) else {}
            head = pull_request.get("head", {}) if isinstance(pull_request, dict) else {}
            inferred_base = base.get("sha") if isinstance(base, dict) else ""
            inferred_head = head.get("sha") if isinstance(head, dict) else ""
            if isinstance(inferred_base, str) and isinstance(inferred_head, str) and inferred_base and inferred_head:
                return inferred_base, inferred_head

    inferred_head = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    inferred_base = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD^"],
        text=True,
    ).strip()
    return inferred_base, inferred_head


def _collect_changed_paths(repo_path: Path, base_sha: str, head_sha: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "-C", str(repo_path), "diff", "--name-only", f"{base_sha}..{head_sha}"],
        text=True,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def _default_action_summary(provider: str) -> str:
    if provider == "github":
        event_path = os.environ.get("GITHUB_EVENT_PATH", "")
        if event_path:
            try:
                payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            pull_request = payload.get("pull_request", {}) if isinstance(payload, dict) else {}
            number = pull_request.get("number") or payload.get("number")
            title = pull_request.get("title") if isinstance(pull_request, dict) else ""
            if number and title:
                return (
                    f"Pull request #{number}: {title}. "
                    "Evaluate the diff as an active merge gate and block if the safety policy is violated."
                )
    if provider == "gitlab":
        iid = os.environ.get("CI_MERGE_REQUEST_IID", "")
        title = os.environ.get("CI_MERGE_REQUEST_TITLE", "")
        if iid and title:
            return (
                f"Merge request !{iid}: {title}. "
                "Evaluate the diff as an active merge gate and block if the safety policy is violated."
            )
    return "Evaluate the current diff as an active merge gate and block if the safety policy is violated."


def _append_step_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write(markdown)
        if not markdown.endswith("\n"):
            handle.write("\n")


def _write_dotenv(path: Path, result: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for key, value in result.items():
            handle.write(f"{key}={value}\n")


def _single_line(value: str) -> str:
    return " ".join(value.split())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Evidence Gate as a provider-native required check.")
    parser.add_argument("--provider", choices=("auto", "github", "gitlab", "generic"), default="auto")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--action-summary", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--changed-paths-json", default="")
    parser.add_argument("--external-sources-json", default="[]")
    parser.add_argument("--diff-summary")
    parser.add_argument("--safety-policy-json", default="")
    parser.add_argument("--safety-policy-file", default="")
    parser.add_argument("--safety-policy-preset", default="")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--live-output-root")
    parser.add_argument("--live-visible-root")
    parser.add_argument("--github-repository", default="")
    parser.add_argument("--github-lookback-days", type=int, default=30)
    parser.add_argument("--jira-base-url", default="")
    parser.add_argument("--jira-user-email", default="")
    parser.add_argument("--jira-project-keys", default="")
    parser.add_argument("--jira-lookback-days", type=int, default=30)
    parser.add_argument("--confluence-base-url", default="")
    parser.add_argument("--confluence-user-email", default="")
    parser.add_argument("--confluence-space-keys", default="")
    parser.add_argument("--confluence-cql", default="")
    parser.add_argument("--confluence-lookback-days", type=int, default=30)
    parser.add_argument("--slack-channel-ids", default="")
    parser.add_argument("--slack-lookback-days", type=int, default=30)
    parser.add_argument("--pagerduty-lookback-days", type=int, default=30)
    parser.add_argument("--output")
    parser.add_argument("--comment-output")
    parser.add_argument("--summary-output")
    parser.add_argument("--dotenv-output")
    parser.add_argument("--github-output")
    parser.add_argument("--gating-mode", choices=("enforce", "shadow"), default="enforce")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--refresh-knowledge-base", action="store_true")
    parser.add_argument("--fail-on-block", action="store_true")
    args = parser.parse_args()

    provider = _detect_provider(args.provider)
    repo_path = Path(args.repo_path).resolve()

    try:
        external_sources = json.loads(args.external_sources_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--external-sources-json must be valid JSON: {exc}") from exc
    if not isinstance(external_sources, list) or not all(isinstance(item, dict) for item in external_sources):
        raise SystemExit("--external-sources-json must be a JSON array of objects")

    if args.changed_paths_json:
        changed_paths = json.loads(args.changed_paths_json)
        if not isinstance(changed_paths, list) or not all(isinstance(item, str) for item in changed_paths):
            raise SystemExit("--changed-paths-json must be a JSON array of strings")
        base_sha = args.base_sha
        head_sha = args.head_sha
    else:
        try:
            base_sha, head_sha = _resolve_refs(provider, repo_path, args.base_sha, args.head_sha)
            changed_paths = _collect_changed_paths(repo_path, base_sha, head_sha)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"Unable to resolve the diff for the required check: {exc}") from exc

    action_summary = args.action_summary or _default_action_summary(provider)

    try:
        result = execute_guardrail(
            api_url=args.api_url,
            repo_path=str(repo_path),
            action_summary=action_summary,
            changed_paths=changed_paths,
            external_sources=external_sources,
            diff_summary=args.diff_summary,
            safety_policy_json=args.safety_policy_json,
            safety_policy_file=args.safety_policy_file,
            safety_policy_preset=args.safety_policy_preset,
            top_k=args.top_k,
            timeout_seconds=args.timeout_seconds,
            live_output_root=Path(args.live_output_root) if args.live_output_root else None,
            live_visible_root=Path(args.live_visible_root) if args.live_visible_root else None,
            github_repository=args.github_repository,
            github_lookback_days=args.github_lookback_days,
            jira_base_url=args.jira_base_url,
            jira_user_email=args.jira_user_email,
            jira_project_keys=args.jira_project_keys,
            jira_lookback_days=args.jira_lookback_days,
            confluence_base_url=args.confluence_base_url,
            confluence_user_email=args.confluence_user_email,
            confluence_space_keys=args.confluence_space_keys,
            confluence_cql=args.confluence_cql,
            confluence_lookback_days=args.confluence_lookback_days,
            slack_channel_ids=args.slack_channel_ids,
            slack_lookback_days=args.slack_lookback_days,
            pagerduty_lookback_days=args.pagerduty_lookback_days,
            output_path=Path(args.output) if args.output else None,
            comment_output_path=Path(args.comment_output) if args.comment_output else None,
            github_output_path=args.github_output,
            gating_mode=args.gating_mode,
            skip_ingest=args.skip_ingest,
            refresh_knowledge_base=args.refresh_knowledge_base,
            fail_on_block=args.fail_on_block,
        )
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    markdown = build_comment(result.payload)
    if args.summary_output:
        Path(args.summary_output).write_text(markdown, encoding="utf-8")
    if provider == "github":
        _append_step_summary(markdown)

    if args.dotenv_output:
        record = result.payload.get("decision_record", {})
        dotenv_values = {
            "EVIDENCE_GATE_ALLOWED": str(bool(result.payload.get("allowed", False))).lower(),
            "EVIDENCE_GATE_STATUS": str(result.payload.get("status", "")),
            "EVIDENCE_GATE_DECISION": str(record.get("decision", "")),
            "EVIDENCE_GATE_DECISION_ID": str(record.get("decision_id", "")),
            "EVIDENCE_GATE_GATING_MODE": args.gating_mode,
            "EVIDENCE_GATE_CHANGED_PATHS": json.dumps(changed_paths, separators=(",", ":")),
            "EVIDENCE_GATE_FAILURE_REASON": _single_line(str(result.payload.get("failure_reason", "") or "")),
        }
        _write_dotenv(Path(args.dotenv_output), dotenv_values)

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
