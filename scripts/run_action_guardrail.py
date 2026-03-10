#!/usr/bin/env python3
"""Call the Evidence Gate action endpoint and emit CI-friendly outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib import error, request

from format_pr_comment import build_comment


def _call_action_endpoint(
    *,
    api_url: str,
    repo_path: str,
    action_summary: str,
    changed_paths: list[str],
    top_k: int,
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    payload = json.dumps(
        {
            "repo_path": repo_path,
            "action_summary": action_summary,
            "changed_paths": changed_paths,
            "top_k": top_k,
        }
    ).encode("utf-8")
    endpoint = api_url.rstrip("/") + "/v1/decide/action"
    req = request.Request(
        endpoint,
        data=payload,
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


def _write_github_output(path: str, values: dict[str, str]) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Evidence Gate action guardrail.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--action-summary", required=True)
    parser.add_argument("--changed-paths-json", default="[]")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--output")
    parser.add_argument("--comment-output")
    parser.add_argument("--github-output")
    parser.add_argument("--fail-on-block", action="store_true")
    args = parser.parse_args()

    changed_paths = json.loads(args.changed_paths_json)
    if not isinstance(changed_paths, list) or not all(isinstance(item, str) for item in changed_paths):
        raise SystemExit("--changed-paths-json must be a JSON array of strings")

    status_code, payload = _call_action_endpoint(
        api_url=args.api_url,
        repo_path=args.repo_path,
        action_summary=args.action_summary,
        changed_paths=changed_paths,
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
        _write_github_output(
            args.github_output,
            {
                "allowed": str(bool(payload.get("allowed", False))).lower(),
                "status_code": str(status_code),
                "decision": str(record.get("decision", "")),
                "decision_id": str(record.get("decision_id", "")),
                "response_path": args.output or "",
                "comment_path": str(comment_path) if comment_path is not None else "",
            },
        )

    if args.fail_on_block and not payload.get("allowed", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
