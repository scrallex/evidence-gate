#!/usr/bin/env python3
"""Call the Evidence Gate action endpoint and emit CI-friendly outputs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from format_pr_comment import build_comment, build_retry_prompt
from live_connector_exports import materialize_live_external_sources


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Evidence Gate action guardrail.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--action-summary", required=True)
    parser.add_argument("--changed-paths-json", default="[]")
    parser.add_argument("--external-sources-json", default="[]")
    parser.add_argument("--diff-summary")
    parser.add_argument("--safety-policy-json", default="")
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
    parser.add_argument("--pagerduty-lookback-days", type=int, default=30)
    parser.add_argument("--output")
    parser.add_argument("--comment-output")
    parser.add_argument("--github-output")
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
    live_external_sources: list[dict[str, str]] = []
    if args.live_output_root:
        live_external_sources = materialize_live_external_sources(
            output_root=Path(args.live_output_root),
            visible_root=Path(args.live_visible_root) if args.live_visible_root else None,
            github_repository=args.github_repository or os.environ.get("GITHUB_REPOSITORY", ""),
            github_lookback_days=args.github_lookback_days,
            jira_base_url=args.jira_base_url,
            jira_user_email=args.jira_user_email,
            jira_project_keys=args.jira_project_keys,
            jira_lookback_days=args.jira_lookback_days,
            pagerduty_lookback_days=args.pagerduty_lookback_days,
            timeout_seconds=args.timeout_seconds,
        )
    external_sources = _merge_external_sources(external_sources, live_external_sources)
    safety_policy: dict[str, Any] | None = None
    if args.safety_policy_json:
        loaded_policy = json.loads(args.safety_policy_json)
        if not isinstance(loaded_policy, dict):
            raise SystemExit("--safety-policy-json must be a JSON object")
        safety_policy = loaded_policy

    ingest_payload: dict[str, Any] = {}
    if not args.skip_ingest:
        ingest_status_code, ingest_payload = _call_ingest_endpoint(
            api_url=args.api_url,
            repo_path=args.repo_path,
            refresh=args.refresh_knowledge_base,
            external_sources=external_sources,
            timeout_seconds=args.timeout_seconds,
        )
        if ingest_status_code != 200:
            raise SystemExit(
                f"knowledge-base ingest failed with HTTP {ingest_status_code}: "
                f"{json.dumps(ingest_payload, sort_keys=True)}"
            )

    status_code, payload = _call_action_endpoint(
        api_url=args.api_url,
        repo_path=args.repo_path,
        action_summary=args.action_summary,
        changed_paths=changed_paths,
        diff_summary=args.diff_summary,
        safety_policy=safety_policy,
        top_k=args.top_k,
        timeout_seconds=args.timeout_seconds,
    )

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    comment_path = None
    if args.comment_output:
        comment_path = Path(args.comment_output)
        comment_path.write_text(build_comment(payload), encoding="utf-8")

    if args.github_output:
        record = payload.get("decision_record", {})
        retry_prompt = build_retry_prompt(payload)
        _write_github_output(
            args.github_output,
            {
                "allowed": str(bool(payload.get("allowed", False))).lower(),
                "status_code": str(status_code),
                "decision": str(record.get("decision", "")),
                "decision_id": str(record.get("decision_id", "")),
                "response_path": args.output or "",
                "comment_path": str(comment_path) if comment_path is not None else "",
                "ingest_status": str(ingest_payload.get("status", "")),
                "repo_fingerprint": str(ingest_payload.get("repo_fingerprint", "")),
                "failure_reason": _single_line(str(payload.get("failure_reason", "") or "")),
                "missing_evidence_json": json.dumps(record.get("missing_evidence", []), separators=(",", ":")),
                "policy_violations_json": json.dumps(payload.get("policy_violations", []), separators=(",", ":")),
                "retry_prompt": _single_line(retry_prompt),
            },
        )

    if args.fail_on_block and not payload.get("allowed", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
