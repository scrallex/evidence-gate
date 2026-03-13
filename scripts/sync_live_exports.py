#!/usr/bin/env python3
"""Stateful polling wrapper for Evidence Gate live connector exports."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from live_connector_exports import (
    CONFLUENCE_SOURCE_KIND,
    GITHUB_SOURCE_KIND,
    JIRA_SOURCE_KIND,
    PAGERDUTY_SOURCE_KIND,
    SLACK_SOURCE_KIND,
    materialize_live_external_sources,
)

STATE_VERSION = 1


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": STATE_VERSION, "sources": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"version": STATE_VERSION, "sources": {}}
    if not isinstance(payload.get("sources"), dict):
        payload["sources"] = {}
    return payload


def _save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _env_or_value(value: str, env_name: str) -> str:
    return value.strip() or str(os.environ.get(env_name, "")).strip()


def _configured_sources(args: argparse.Namespace) -> tuple[str, ...]:
    configured: list[str] = []
    if _env_or_value(args.github_repository, "GITHUB_REPOSITORY") or os.environ.get("GITHUB_TOKEN"):
        configured.append(GITHUB_SOURCE_KIND)
    if _env_or_value(args.jira_base_url, "JIRA_BASE_URL") or os.environ.get("JIRA_API_TOKEN"):
        configured.append(JIRA_SOURCE_KIND)
    if os.environ.get("PAGERDUTY_TOKEN"):
        configured.append(PAGERDUTY_SOURCE_KIND)
    if _env_or_value(args.confluence_base_url, "CONFLUENCE_BASE_URL") or os.environ.get("CONFLUENCE_API_TOKEN"):
        configured.append(CONFLUENCE_SOURCE_KIND)
    if _env_or_value(args.slack_channel_ids, "SLACK_CHANNEL_IDS") or _env_or_value(args.slack_channel_ids, "SLACK_CHANNELS") or os.environ.get("SLACK_BOT_TOKEN"):
        configured.append(SLACK_SOURCE_KIND)
    return tuple(dict.fromkeys(configured))


def _state_since(payload: dict[str, Any], source_kind: str) -> datetime | None:
    sources = payload.get("sources", {})
    if not isinstance(sources, dict):
        return None
    source_payload = sources.get(source_kind, {})
    if not isinstance(source_payload, dict):
        return None
    return _parse_timestamp(source_payload.get("last_synced_at"))


def _run_sync(
    *,
    args: argparse.Namespace,
    state_path: Path,
) -> list[dict[str, str]]:
    now = datetime.now(timezone.utc)
    state = _load_state(state_path)
    configured = _configured_sources(args)
    external_sources = materialize_live_external_sources(
        output_root=Path(args.output_root),
        visible_root=Path(args.visible_root) if args.visible_root else None,
        github_repository=args.github_repository,
        github_lookback_days=args.github_lookback_days,
        github_updated_since=_state_since(state, GITHUB_SOURCE_KIND),
        jira_base_url=args.jira_base_url,
        jira_user_email=args.jira_user_email,
        jira_project_keys=args.jira_project_keys,
        jira_lookback_days=args.jira_lookback_days,
        jira_updated_since=_state_since(state, JIRA_SOURCE_KIND),
        pagerduty_lookback_days=args.pagerduty_lookback_days,
        pagerduty_updated_since=_state_since(state, PAGERDUTY_SOURCE_KIND),
        confluence_base_url=args.confluence_base_url,
        confluence_user_email=args.confluence_user_email,
        confluence_space_keys=args.confluence_space_keys,
        confluence_cql=args.confluence_cql,
        confluence_lookback_days=args.confluence_lookback_days,
        confluence_updated_since=_state_since(state, CONFLUENCE_SOURCE_KIND),
        slack_channel_ids=args.slack_channel_ids,
        slack_lookback_days=args.slack_lookback_days,
        slack_updated_since=_state_since(state, SLACK_SOURCE_KIND),
        timeout_seconds=args.timeout_seconds,
    )
    sources = state.setdefault("sources", {})
    for source_kind in configured:
        source_payload = sources.setdefault(source_kind, {})
        if not isinstance(source_payload, dict):
            source_payload = {}
            sources[source_kind] = source_payload
        source_payload["last_synced_at"] = now.isoformat()
    state["version"] = STATE_VERSION
    state["last_run_at"] = now.isoformat()
    _save_state(state_path, state)
    return external_sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--visible-root")
    parser.add_argument("--state-file", default="")
    parser.add_argument("--poll-interval-seconds", type=int, default=0)
    parser.add_argument("--max-runs", type=int, default=1)
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
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--json-output", default="")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    state_path = Path(args.state_file) if args.state_file else output_root / "sync-state.json"
    runs = 0
    while True:
        external_sources = _run_sync(args=args, state_path=state_path)
        serialized = json.dumps(external_sources, separators=(",", ":"))
        if args.json_output:
            Path(args.json_output).write_text(serialized + "\n", encoding="utf-8")
        else:
            print(serialized)
        runs += 1
        if args.poll_interval_seconds <= 0:
            break
        if args.max_runs > 0 and runs >= args.max_runs:
            break
        time.sleep(args.poll_interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
