#!/usr/bin/env python3
"""Call the Evidence Gate action endpoint and emit CI-friendly outputs."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from evidence_gate.policy_loader import resolve_action_safety_policy

from format_pr_comment import build_comment, build_retry_prompt
from live_connector_exports import materialize_live_external_sources


@dataclass(slots=True)
class GuardrailExecutionResult:
    exit_code: int
    status_code: int
    payload: dict[str, Any]
    ingest_payload: dict[str, Any]
    comment_path: Path | None


def _call_json_endpoint(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        status_code = exc.code
        response_body = exc.read().decode("utf-8")
    return status_code, json.loads(response_body)


def _call_ingest_endpoint(
    *,
    api_url: str,
    repo_path: str,
    refresh: bool,
    external_sources: list[dict[str, str]],
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    return _call_json_endpoint(
        endpoint=api_url.rstrip("/") + "/v1/knowledge-bases/ingest",
        payload={
            "repo_path": repo_path,
            "refresh": refresh,
            "external_sources": external_sources,
        },
        timeout_seconds=timeout_seconds,
    )


def _call_action_endpoint(
    *,
    api_url: str,
    repo_path: str,
    action_summary: str,
    changed_paths: list[str],
    diff_summary: str | None,
    safety_policy: dict[str, Any] | None,
    top_k: int,
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    return _call_json_endpoint(
        endpoint=api_url.rstrip("/") + "/v1/decide/action",
        payload={
            "repo_path": repo_path,
            "action_summary": action_summary,
            "changed_paths": changed_paths,
            "diff_summary": diff_summary,
            "safety_policy": safety_policy,
            "top_k": top_k,
        },
        timeout_seconds=timeout_seconds,
    )


def _write_github_output(path: str, values: dict[str, str]) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _merge_external_sources(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for item in group:
            source_type = str(item.get("type", "")).strip()
            source_path = str(item.get("path", "")).strip()
            if not source_type or not source_path:
                continue
            identity = (source_type.lower(), source_path)
            if identity in seen:
                continue
            merged.append({"type": source_type, "path": source_path})
            seen.add(identity)
    return merged


def execute_guardrail(
    *,
    api_url: str,
    repo_path: str,
    action_summary: str,
    changed_paths: list[str],
    external_sources: list[dict[str, str]] | None = None,
    diff_summary: str | None = None,
    safety_policy_json: str = "",
    safety_policy_file: str = "",
    safety_policy_preset: str = "",
    top_k: int = 5,
    timeout_seconds: int = 90,
    live_output_root: Path | None = None,
    live_visible_root: Path | None = None,
    github_repository: str = "",
    github_lookback_days: int = 30,
    jira_base_url: str = "",
    jira_user_email: str = "",
    jira_project_keys: str = "",
    jira_lookback_days: int = 30,
    confluence_base_url: str = "",
    confluence_user_email: str = "",
    confluence_space_keys: str = "",
    confluence_cql: str = "",
    confluence_lookback_days: int = 30,
    slack_channel_ids: str = "",
    slack_lookback_days: int = 30,
    pagerduty_lookback_days: int = 30,
    output_path: Path | None = None,
    comment_output_path: Path | None = None,
    github_output_path: str | None = None,
    gating_mode: str = "enforce",
    skip_ingest: bool = False,
    refresh_knowledge_base: bool = False,
    fail_on_block: bool = False,
) -> GuardrailExecutionResult:
    if not all(isinstance(item, str) for item in changed_paths):
        raise ValueError("changed_paths must contain only strings")
    if external_sources is None:
        external_sources = []
    if not all(isinstance(item, dict) for item in external_sources):
        raise ValueError("external_sources must contain only objects")

    live_external_sources: list[dict[str, str]] = []
    if live_output_root is not None:
        live_external_sources = materialize_live_external_sources(
            output_root=live_output_root,
            visible_root=live_visible_root,
            github_repository=github_repository or os.environ.get("GITHUB_REPOSITORY", ""),
            github_lookback_days=github_lookback_days,
            jira_base_url=jira_base_url,
            jira_user_email=jira_user_email,
            jira_project_keys=jira_project_keys,
            jira_lookback_days=jira_lookback_days,
            confluence_base_url=confluence_base_url,
            confluence_user_email=confluence_user_email,
            confluence_space_keys=confluence_space_keys,
            confluence_cql=confluence_cql,
            confluence_lookback_days=confluence_lookback_days,
            slack_channel_ids=slack_channel_ids,
            slack_lookback_days=slack_lookback_days,
            pagerduty_lookback_days=pagerduty_lookback_days,
            timeout_seconds=timeout_seconds,
        )
    merged_external_sources = _merge_external_sources(external_sources, live_external_sources)
    safety_policy = resolve_action_safety_policy(
        inline_json=safety_policy_json,
        preset=safety_policy_preset,
        file_path=safety_policy_file,
        cwd=Path.cwd(),
    )

    ingest_payload: dict[str, Any] = {}
    if not skip_ingest:
        ingest_status_code, ingest_payload = _call_ingest_endpoint(
            api_url=api_url,
            repo_path=repo_path,
            refresh=refresh_knowledge_base,
            external_sources=merged_external_sources,
            timeout_seconds=timeout_seconds,
        )
        if ingest_status_code != 200:
            raise RuntimeError(
                f"knowledge-base ingest failed with HTTP {ingest_status_code}: "
                f"{json.dumps(ingest_payload, sort_keys=True)}"
            )

    status_code, payload = _call_action_endpoint(
        api_url=api_url,
        repo_path=repo_path,
        action_summary=action_summary,
        changed_paths=changed_paths,
        diff_summary=diff_summary,
        safety_policy=safety_policy,
        top_k=top_k,
        timeout_seconds=timeout_seconds,
    )

    if output_path is not None:
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    comment_path = None
    if comment_output_path is not None:
        comment_path = comment_output_path
        comment_path.write_text(build_comment(payload), encoding="utf-8")

    if github_output_path:
        record = payload.get("decision_record", {})
        retry_prompt = build_retry_prompt(payload)
        _write_github_output(
            github_output_path,
            {
                "allowed": str(bool(payload.get("allowed", False))).lower(),
                "status_code": str(status_code),
                "decision": str(record.get("decision", "")),
                "decision_id": str(record.get("decision_id", "")),
                "response_path": str(output_path) if output_path is not None else "",
                "comment_path": str(comment_path) if comment_path is not None else "",
                "ingest_status": str(ingest_payload.get("status", "")),
                "repo_fingerprint": str(ingest_payload.get("repo_fingerprint", "")),
                "gating_mode": gating_mode,
                "shadow_blocked": str(gating_mode == "shadow" and not payload.get("allowed", False)).lower(),
                "failure_reason": _single_line(str(payload.get("failure_reason", "") or "")),
                "missing_evidence_json": json.dumps(record.get("missing_evidence", []), separators=(",", ":")),
                "policy_violations_json": json.dumps(payload.get("policy_violations", []), separators=(",", ":")),
                "retry_prompt": _single_line(retry_prompt),
            },
        )

    if gating_mode == "shadow":
        decision_name = str(payload.get("decision_record", {}).get("decision", "")).strip() or "unknown"
        summary = _single_line(str(payload.get("failure_reason", "") or "Evidence Gate would have blocked this action."))
        if payload.get("allowed", False):
            print(f"::notice title=Evidence Gate Shadow Mode::Would allow this action ({decision_name}).")
        else:
            print(
                "::warning title=Evidence Gate Shadow Mode::"
                f"Would have blocked this action ({decision_name}). {summary}"
            )
        return GuardrailExecutionResult(
            exit_code=0,
            status_code=status_code,
            payload=payload,
            ingest_payload=ingest_payload,
            comment_path=comment_path,
        )

    exit_code = 1 if fail_on_block and not payload.get("allowed", False) else 0
    return GuardrailExecutionResult(
        exit_code=exit_code,
        status_code=status_code,
        payload=payload,
        ingest_payload=ingest_payload,
        comment_path=comment_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Evidence Gate action guardrail.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--action-summary", required=True)
    parser.add_argument("--changed-paths-json", default="[]")
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
    parser.add_argument("--github-output")
    parser.add_argument("--gating-mode", choices=("enforce", "shadow"), default="enforce")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--refresh-knowledge-base", action="store_true")
    parser.add_argument("--fail-on-block", action="store_true")
    args = parser.parse_args()

    changed_paths = json.loads(args.changed_paths_json)
    if not isinstance(changed_paths, list) or not all(isinstance(item, str) for item in changed_paths):
        raise SystemExit("--changed-paths-json must be a JSON array of strings")
    external_sources = json.loads(args.external_sources_json)
    if not isinstance(external_sources, list) or not all(isinstance(item, dict) for item in external_sources):
        raise SystemExit("--external-sources-json must be a JSON array of objects")
    try:
        result = execute_guardrail(
            api_url=args.api_url,
            repo_path=args.repo_path,
            action_summary=args.action_summary,
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
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
