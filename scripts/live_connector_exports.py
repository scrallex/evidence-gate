#!/usr/bin/env python3
"""Fetch live read-only exports for Evidence Gate ingestion."""

from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Any
from urllib import error, parse, request

DEFAULT_LOOKBACK_DAYS = 30
GITHUB_SOURCE_KIND = "github"
JIRA_SOURCE_KIND = "jira"
PAGERDUTY_SOURCE_KIND = "pagerduty"
SLACK_SOURCE_KIND = "slack"
CONFLUENCE_SOURCE_KIND = "confluence"


def materialize_live_external_sources(
    *,
    output_root: Path,
    visible_root: Path | None = None,
    github_repository: str | None = None,
    github_token: str | None = None,
    github_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    github_updated_since: datetime | None = None,
    jira_base_url: str | None = None,
    jira_api_token: str | None = None,
    jira_user_email: str | None = None,
    jira_project_keys: str | tuple[str, ...] | list[str] | None = None,
    jira_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    jira_updated_since: datetime | None = None,
    pagerduty_token: str | None = None,
    pagerduty_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    pagerduty_updated_since: datetime | None = None,
    confluence_base_url: str | None = None,
    confluence_api_token: str | None = None,
    confluence_user_email: str | None = None,
    confluence_space_keys: str | tuple[str, ...] | list[str] | None = None,
    confluence_cql: str | None = None,
    confluence_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    confluence_updated_since: datetime | None = None,
    slack_bot_token: str | None = None,
    slack_channel_ids: str | tuple[str, ...] | list[str] | None = None,
    slack_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    slack_updated_since: datetime | None = None,
    timeout_seconds: int = 90,
) -> list[dict[str, str]]:
    """Fetch available live sources and return ingest-ready source specs."""

    output_root = Path(output_root).expanduser().resolve()
    visible_root = Path(visible_root or output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    github_repository = (github_repository or os.environ.get("GITHUB_REPOSITORY") or "").strip() or None
    github_token = (github_token or os.environ.get("GITHUB_TOKEN") or "").strip() or None
    jira_base_url = (jira_base_url or os.environ.get("JIRA_BASE_URL") or "").strip() or None
    jira_api_token = (jira_api_token or os.environ.get("JIRA_API_TOKEN") or "").strip() or None
    jira_user_email = (jira_user_email or os.environ.get("JIRA_USER_EMAIL") or "").strip() or None
    pagerduty_token = (pagerduty_token or os.environ.get("PAGERDUTY_TOKEN") or "").strip() or None
    confluence_base_url = (confluence_base_url or os.environ.get("CONFLUENCE_BASE_URL") or "").strip() or None
    confluence_api_token = (confluence_api_token or os.environ.get("CONFLUENCE_API_TOKEN") or "").strip() or None
    confluence_user_email = (confluence_user_email or os.environ.get("CONFLUENCE_USER_EMAIL") or "").strip() or None
    confluence_cql = (confluence_cql or os.environ.get("CONFLUENCE_CQL") or "").strip() or None
    slack_bot_token = (slack_bot_token or os.environ.get("SLACK_BOT_TOKEN") or "").strip() or None
    project_keys = _normalize_project_keys(jira_project_keys or os.environ.get("JIRA_PROJECT_KEYS"))
    confluence_space_keys = _normalize_project_keys(
        confluence_space_keys or os.environ.get("CONFLUENCE_SPACE_KEYS")
    )
    slack_channels = _normalize_project_keys(
        slack_channel_ids or os.environ.get("SLACK_CHANNEL_IDS") or os.environ.get("SLACK_CHANNELS")
    )

    external_sources: list[dict[str, str]] = []

    if github_token or github_repository:
        if not github_token:
            raise ValueError("GITHUB_TOKEN is required when enabling live GitHub pull request fetch.")
        if github_repository is None:
            raise ValueError("A GitHub repository is required for live pull request fetch.")
        pulls = fetch_recent_github_pull_requests(
            repository=github_repository,
            token=github_token,
            lookback_days=github_lookback_days,
            updated_since=github_updated_since,
            timeout_seconds=timeout_seconds,
        )
        if pulls:
            github_root = output_root / GITHUB_SOURCE_KIND
            github_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                github_root / "pulls.json",
                {
                    "repository": github_repository,
                    "pulls": pulls,
                },
            )
            external_sources.append(
                {
                    "type": GITHUB_SOURCE_KIND,
                    "path": _visible_path(visible_root, GITHUB_SOURCE_KIND),
                }
            )

    if jira_api_token or jira_base_url or project_keys:
        if not jira_api_token:
            raise ValueError("JIRA_API_TOKEN is required when enabling live Jira fetch.")
        if not jira_base_url:
            raise ValueError("JIRA_BASE_URL is required when enabling live Jira fetch.")
        issues = fetch_recent_jira_issues(
            base_url=jira_base_url,
            api_token=jira_api_token,
            user_email=jira_user_email,
            project_keys=project_keys,
            lookback_days=jira_lookback_days,
            updated_since=jira_updated_since,
            timeout_seconds=timeout_seconds,
        )
        if issues:
            jira_root = output_root / JIRA_SOURCE_KIND
            jira_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                jira_root / "issues.json",
                {
                    "issues": issues,
                },
            )
            external_sources.append(
                {
                    "type": JIRA_SOURCE_KIND,
                    "path": _visible_path(visible_root, JIRA_SOURCE_KIND),
                }
            )

    if pagerduty_token:
        incidents = fetch_recent_pagerduty_incidents(
            token=pagerduty_token,
            lookback_days=pagerduty_lookback_days,
            updated_since=pagerduty_updated_since,
            timeout_seconds=timeout_seconds,
        )
        if incidents:
            pagerduty_root = output_root / PAGERDUTY_SOURCE_KIND
            pagerduty_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                pagerduty_root / "incidents.json",
                {
                    "incidents": incidents,
                },
            )
            external_sources.append(
                {
                    "type": PAGERDUTY_SOURCE_KIND,
                    "path": _visible_path(visible_root, PAGERDUTY_SOURCE_KIND),
                }
            )

    if confluence_api_token or confluence_base_url or confluence_space_keys or confluence_cql:
        if not confluence_api_token:
            raise ValueError("CONFLUENCE_API_TOKEN is required when enabling live Confluence fetch.")
        if not confluence_base_url:
            raise ValueError("CONFLUENCE_BASE_URL is required when enabling live Confluence fetch.")
        pages = fetch_recent_confluence_pages(
            base_url=confluence_base_url,
            api_token=confluence_api_token,
            user_email=confluence_user_email,
            space_keys=confluence_space_keys,
            cql=confluence_cql,
            lookback_days=confluence_lookback_days,
            updated_since=confluence_updated_since,
            timeout_seconds=timeout_seconds,
        )
        if pages:
            confluence_root = output_root / CONFLUENCE_SOURCE_KIND
            confluence_root.mkdir(parents=True, exist_ok=True)
            _write_json(
                confluence_root / "pages.json",
                {
                    "pages": pages,
                },
            )
            external_sources.append(
                {
                    "type": CONFLUENCE_SOURCE_KIND,
                    "path": _visible_path(visible_root, CONFLUENCE_SOURCE_KIND),
                }
            )

    if slack_bot_token or slack_channels:
        if not slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required when enabling live Slack fetch.")
        if not slack_channels:
            raise ValueError("SLACK_CHANNEL_IDS or SLACK_CHANNELS is required when enabling live Slack fetch.")
        slack_threads = fetch_recent_slack_threads(
            token=slack_bot_token,
            channel_ids=slack_channels,
            lookback_days=slack_lookback_days,
            updated_since=slack_updated_since,
            timeout_seconds=timeout_seconds,
        )
        if slack_threads:
            slack_root = output_root / SLACK_SOURCE_KIND
            slack_root.mkdir(parents=True, exist_ok=True)
            for channel_id, messages in slack_threads.items():
                channel_root = slack_root / channel_id
                channel_root.mkdir(parents=True, exist_ok=True)
                _write_json(channel_root / "threads.json", messages)
            external_sources.append(
                {
                    "type": SLACK_SOURCE_KIND,
                    "path": _visible_path(visible_root, SLACK_SOURCE_KIND),
                }
            )

    return external_sources


def fetch_recent_github_pull_requests(
    *,
    repository: str,
    token: str,
    lookback_days: int,
    updated_since: datetime | None,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recently updated pull requests from the target GitHub repository."""

    api_root = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    cutoff = updated_since or (_utc_now() - timedelta(days=max(1, lookback_days)))
    page = 1
    pulls: list[dict[str, Any]] = []
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "evidence-gate-live-connectors",
    }

    while True:
        query = parse.urlencode(
            {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            }
        )
        payload = _request_json(
            url=f"{api_root}/repos/{repository}/pulls?{query}",
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        if not isinstance(payload, list) or not payload:
            break

        recent_count = 0
        for item in payload:
            if not isinstance(item, dict):
                continue
            updated_at = _parse_timestamp(item.get("updated_at"))
            if updated_at is not None and updated_at < cutoff:
                continue
            recent_count += 1
            pulls.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "body": item.get("body"),
                    "state": item.get("state"),
                    "draft": item.get("draft"),
                    "html_url": item.get("html_url"),
                    "updated_at": item.get("updated_at"),
                    "merged_at": item.get("merged_at"),
                    "closed_at": item.get("closed_at"),
                    "created_at": item.get("created_at"),
                    "user": {"login": _nested_text(item, "user", "login")},
                    "base": {
                        "ref": _nested_text(item, "base", "ref"),
                        "repo": {"full_name": _nested_text(item, "base", "repo", "full_name")},
                    },
                    "head": {
                        "ref": _nested_text(item, "head", "ref"),
                        "repo": {"full_name": _nested_text(item, "head", "repo", "full_name")},
                    },
                    "labels": [
                        {"name": _nested_text(label, "name")}
                        for label in item.get("labels", [])
                        if isinstance(label, dict) and _nested_text(label, "name")
                    ],
                }
            )
        if recent_count == 0:
            break
        page += 1

    return pulls


def fetch_recent_jira_issues(
    *,
    base_url: str,
    api_token: str,
    user_email: str | None,
    project_keys: tuple[str, ...],
    lookback_days: int,
    updated_since: datetime | None,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recently updated Jira issues and flatten them for ingest."""

    endpoint = base_url.rstrip("/") + "/rest/api/3/search"
    project_clause = ""
    if project_keys:
        quoted = ", ".join(project_keys)
        project_clause = f"project in ({quoted}) AND "
    jql = f"{project_clause}{_jira_updated_clause(updated_since, lookback_days)} ORDER BY updated DESC"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "evidence-gate-live-connectors",
    }
    if user_email:
        headers["Authorization"] = f"Basic {_basic_auth_value(user_email, api_token)}"
    else:
        headers["Authorization"] = f"Bearer {api_token}"

    issues: list[dict[str, Any]] = []
    start_at = 0
    while True:
        payload = _request_json(
            url=endpoint,
            method="POST",
            headers=headers,
            payload={
                "jql": jql,
                "startAt": start_at,
                "maxResults": 100,
                "fields": [
                    "summary",
                    "description",
                    "status",
                    "labels",
                    "creator",
                    "reporter",
                    "issuetype",
                    "updated",
                    "created",
                ],
            },
            timeout_seconds=timeout_seconds,
        )
        batch = payload.get("issues", []) if isinstance(payload, dict) else []
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            if not isinstance(item, dict):
                continue
            fields = item.get("fields", {})
            if not isinstance(fields, dict):
                fields = {}
            key = _first_non_empty(item.get("key"), item.get("id"))
            if key is None:
                continue
            issues.append(
                {
                    "key": key,
                    "summary": _first_non_empty(fields.get("summary"), key),
                    "description": _jira_plain_text(fields.get("description")) or "No ticket description provided.",
                    "status": _nested_text(fields, "status", "name"),
                    "issue_type": _nested_text(fields, "issuetype", "name"),
                    "labels": fields.get("labels") if isinstance(fields.get("labels"), list) else [],
                    "author": _first_non_empty(
                        _nested_text(fields, "creator", "displayName"),
                        _nested_text(fields, "creator", "name"),
                        _nested_text(fields, "reporter", "displayName"),
                        _nested_text(fields, "reporter", "name"),
                    ),
                    "browse_url": base_url.rstrip("/") + f"/browse/{key}",
                    "updated_at": fields.get("updated"),
                    "created_at": fields.get("created"),
                }
            )
        total = payload.get("total", start_at + len(batch)) if isinstance(payload, dict) else start_at + len(batch)
        start_at += len(batch)
        if start_at >= int(total):
            break
    return issues


def fetch_recent_pagerduty_incidents(
    *,
    token: str,
    lookback_days: int,
    updated_since: datetime | None,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recent PagerDuty incidents."""

    api_root = (os.environ.get("PAGERDUTY_API_URL") or "https://api.pagerduty.com").rstrip("/")
    now = _utc_now()
    since = updated_since or (now - timedelta(days=max(1, lookback_days)))
    headers = {
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Authorization": f"Token token={token}",
        "User-Agent": "evidence-gate-live-connectors",
    }

    incidents: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = parse.urlencode(
            {
                "since": since.isoformat(),
                "until": now.isoformat(),
                "limit": 100,
                "offset": offset,
            }
        )
        payload = _request_json(
            url=f"{api_root}/incidents?{query}",
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        batch = payload.get("incidents", []) if isinstance(payload, dict) else []
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            if not isinstance(item, dict):
                continue
            incidents.append(
                {
                    "incident_number": _first_non_empty(item.get("incident_number"), item.get("id")),
                    "id": item.get("id"),
                    "title": _first_non_empty(item.get("title"), item.get("summary")),
                    "description": _first_non_empty(
                        item.get("description"),
                        item.get("body"),
                        item.get("self"),
                        "No incident body provided.",
                    ),
                    "status": item.get("status"),
                    "service": {
                        "summary": _first_non_empty(
                            _nested_text(item, "service", "summary"),
                            _nested_text(item, "service", "name"),
                        )
                    },
                    "urgency": _first_non_empty(item.get("urgency"), item.get("severity")),
                    "html_url": _first_non_empty(item.get("html_url"), item.get("self")),
                    "created_at": item.get("created_at"),
                    "updated_at": _first_non_empty(item.get("last_status_change_at"), item.get("updated_at")),
                }
            )
        if not bool(payload.get("more")):
            break
        offset += len(batch)
    return incidents


def fetch_recent_confluence_pages(
    *,
    base_url: str,
    api_token: str,
    user_email: str | None,
    space_keys: tuple[str, ...],
    cql: str | None,
    lookback_days: int,
    updated_since: datetime | None,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recent Confluence pages and flatten them for ingest."""

    api_root, public_root = _normalize_confluence_roots(base_url)
    search_cql = cql.strip() if cql and cql.strip() else _build_confluence_cql(space_keys, updated_since, lookback_days)
    headers = {
        "Accept": "application/json",
        "User-Agent": "evidence-gate-live-connectors",
    }
    if user_email:
        headers["Authorization"] = f"Basic {_basic_auth_value(user_email, api_token)}"
    else:
        headers["Authorization"] = f"Bearer {api_token}"

    results: list[dict[str, Any]] = []
    start = 0
    while True:
        query = parse.urlencode(
            {
                "cql": search_cql,
                "limit": 100,
                "start": start,
                "expand": "content.body.storage,content.version,content.space",
            }
        )
        payload = _request_json(
            url=f"{api_root}/rest/api/search?{query}",
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        batch = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, dict):
                continue
            webui = _confluence_webui(
                _first_non_empty(
                    _nested_text(item, "url"),
                    _nested_text(item, "_links", "webui"),
                    _nested_text(content, "_links", "webui"),
                )
            )
            results.append(
                {
                    "title": _first_non_empty(content.get("title"), item.get("title"), content.get("id")),
                    "body": {
                        "storage": {
                            "value": _first_non_empty(
                                _nested_text(content, "body", "storage", "value"),
                                _nested_text(content, "body", "view", "value"),
                                _nested_text(item, "excerpt"),
                                "No page body provided.",
                            )
                        }
                    },
                    "space": {
                        "key": _first_non_empty(
                            _nested_text(content, "space", "key"),
                            _nested_text(content, "space", "name"),
                            "space",
                        )
                    },
                    "version": {
                        "by": {
                            "displayName": _first_non_empty(
                                _nested_text(content, "version", "by", "displayName"),
                                _nested_text(content, "history", "createdBy", "displayName"),
                            )
                        },
                        "when": _first_non_empty(
                            _nested_text(content, "version", "when"),
                            _nested_text(item, "lastModified"),
                        ),
                    },
                    "_links": {
                        "base": public_root,
                        "webui": webui,
                    },
                }
            )
        if len(batch) < 100:
            break
        start += len(batch)
    return results


def fetch_recent_slack_threads(
    *,
    token: str,
    channel_ids: tuple[str, ...],
    lookback_days: int,
    updated_since: datetime | None,
    timeout_seconds: int,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch recent Slack incident threads in export-compatible JSON form."""

    api_root = (os.environ.get("SLACK_API_URL") or "https://slack.com/api").rstrip("/")
    cutoff = updated_since or (_utc_now() - timedelta(days=max(1, lookback_days)))
    oldest = f"{cutoff.timestamp():.6f}"
    headers = {
        "Accept": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}",
        "User-Agent": "evidence-gate-live-connectors",
    }
    exports: dict[str, list[dict[str, Any]]] = {}
    for channel_id in channel_ids:
        history_messages = _fetch_slack_history(
            api_root=api_root,
            headers=headers,
            channel_id=channel_id,
            oldest=oldest,
            timeout_seconds=timeout_seconds,
        )
        if not history_messages:
            continue
        thread_roots = [
            message
            for message in history_messages
            if message.get("reply_count") or message.get("latest_reply")
        ]
        thread_messages: dict[str, dict[str, Any]] = {
            str(message.get("ts")): _normalize_slack_message(message)
            for message in history_messages
            if _normalize_slack_message(message) is not None
        }
        for root in thread_roots:
            root_ts = _first_non_empty(root.get("thread_ts"), root.get("ts"))
            if root_ts is None:
                continue
            replies = _fetch_slack_replies(
                api_root=api_root,
                headers=headers,
                channel_id=channel_id,
                thread_ts=root_ts,
                oldest=oldest,
                timeout_seconds=timeout_seconds,
            )
            for reply in replies:
                normalized = _normalize_slack_message(reply)
                if normalized is None:
                    continue
                thread_messages[str(normalized["ts"])] = normalized
        ordered = sorted(
            thread_messages.values(),
            key=lambda item: float(_first_non_empty(item.get("ts"), "0") or "0"),
        )
        if ordered:
            exports[channel_id] = ordered
    return exports


def _request_json(
    *,
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    attempt = 0
    while True:
        attempt += 1
        req = request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
            return json.loads(body)
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429 and attempt < max_retries:
                retry_after = _retry_after_seconds(exc.headers.get("Retry-After"))
                time.sleep(retry_after)
                continue
            if exc.code >= 500 and attempt < max_retries:
                time.sleep(min(attempt * 2, 10))
                continue
            raise RuntimeError(f"Live connector fetch failed with HTTP {exc.code}: {body[:400]}") from exc
        except error.URLError as exc:
            if attempt < max_retries:
                time.sleep(min(attempt * 2, 10))
                continue
            raise RuntimeError(f"Live connector fetch failed: {exc.reason}") from exc


def _fetch_slack_history(
    *,
    api_root: str,
    headers: dict[str, str],
    channel_id: str,
    oldest: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    cursor = ""
    while True:
        query = parse.urlencode(
            {
                "channel": channel_id,
                "limit": 200,
                "oldest": oldest,
                "inclusive": "true",
                "cursor": cursor,
            }
        )
        payload = _request_json(
            url=f"{api_root}/conversations.history?{query}",
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        _ensure_slack_ok(payload)
        batch = payload.get("messages", []) if isinstance(payload, dict) else []
        if not isinstance(batch, list) or not batch:
            break
        messages.extend(item for item in batch if isinstance(item, dict))
        cursor = _nested_text(payload, "response_metadata", "next_cursor") or ""
        if not cursor:
            break
    return messages


def _fetch_slack_replies(
    *,
    api_root: str,
    headers: dict[str, str],
    channel_id: str,
    thread_ts: str,
    oldest: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    query = parse.urlencode(
        {
            "channel": channel_id,
            "ts": thread_ts,
            "oldest": oldest,
            "inclusive": "true",
            "limit": 200,
        }
    )
    payload = _request_json(
        url=f"{api_root}/conversations.replies?{query}",
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    _ensure_slack_ok(payload)
    batch = payload.get("messages", []) if isinstance(payload, dict) else []
    if not isinstance(batch, list):
        return []
    return [item for item in batch if isinstance(item, dict)]


def _ensure_slack_ok(payload: Any) -> None:
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise RuntimeError(f"Slack live connector fetch failed: {payload.get('error', 'unknown_error')}")


def _normalize_slack_message(message: dict[str, Any]) -> dict[str, Any] | None:
    text = _first_non_empty(message.get("text"))
    ts = _first_non_empty(message.get("ts"))
    if ts is None or text is None:
        return None
    normalized: dict[str, Any] = {
        "ts": ts,
        "text": text,
    }
    thread_ts = _first_non_empty(message.get("thread_ts"))
    if thread_ts is not None and thread_ts != ts:
        normalized["thread_ts"] = thread_ts
    user = _first_non_empty(message.get("user"), message.get("username"), _nested_text(message, "bot_profile", "name"))
    if user is not None:
        normalized["user"] = user
    display_name = _first_non_empty(
        _nested_text(message, "user_profile", "display_name"),
        _nested_text(message, "bot_profile", "name"),
        _nested_text(message, "profile", "display_name"),
    )
    if display_name is not None:
        normalized["user_profile"] = {"display_name": display_name}
    return normalized


def _normalize_confluence_roots(base_url: str) -> tuple[str, str]:
    public_root = base_url.rstrip("/")
    if public_root.endswith("/wiki"):
        return public_root, public_root[:-5]
    return public_root + "/wiki", public_root


def _build_confluence_cql(
    space_keys: tuple[str, ...],
    updated_since: datetime | None,
    lookback_days: int,
) -> str:
    clauses = ["type = page", _confluence_updated_clause(updated_since, lookback_days)]
    if space_keys:
        quoted = ", ".join(f'"{key}"' for key in space_keys)
        clauses.append(f"space in ({quoted})")
    return " AND ".join(clauses) + " ORDER BY lastmodified DESC"


def _confluence_webui(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = parse.urlparse(value)
    if parsed.scheme and parsed.netloc:
        return parsed.path or None
    return value


def _jira_updated_clause(updated_since: datetime | None, lookback_days: int) -> str:
    return f"updated >= {_relative_window_clause(updated_since, lookback_days)}"


def _confluence_updated_clause(updated_since: datetime | None, lookback_days: int) -> str:
    return f'lastmodified >= now("{_relative_window_clause(updated_since, lookback_days)}")'


def _relative_window_clause(updated_since: datetime | None, lookback_days: int) -> str:
    if updated_since is None:
        return f"-{max(1, lookback_days)}d"
    delta = max(_utc_now() - updated_since, timedelta(minutes=1))
    total_seconds = int(delta.total_seconds())
    minutes = max(1, (total_seconds + 59) // 60)
    if minutes < 60:
        return f"-{minutes}m"
    if minutes < 24 * 60:
        hours = max(1, (total_seconds + 3599) // 3600)
        return f"-{hours}h"
    days = max(1, (total_seconds + 86399) // 86400)
    return f"-{days}d"


def _retry_after_seconds(value: str | None) -> int:
    if value is None:
        return 5
    try:
        parsed = int(value.strip())
    except ValueError:
        return 5
    return min(max(parsed, 1), 60)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _visible_path(visible_root: Path, suffix: str) -> str:
    return (visible_root / suffix).as_posix()


def _basic_auth_value(user_email: str, api_token: str) -> str:
    raw = f"{user_email}:{api_token}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _normalize_project_keys(value: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return tuple(part for part in parts if part)
    return tuple(str(part).strip() for part in value if str(part).strip())


def _jira_plain_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_jira_plain_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    if not isinstance(value, dict):
        return ""

    text = _first_non_empty(value.get("text"))
    if text:
        return text
    if value.get("type") == "hardBreak":
        return "\n"
    content = value.get("content")
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            piece = _jira_plain_text(item)
            if piece:
                pieces.append(piece)
        separator = "\n" if value.get("type") in {"paragraph", "heading"} else " "
        return separator.join(pieces).strip()
    return ""


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _nested_text(payload: object, *keys: str) -> str | None:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _first_non_empty(current)


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch live read-only exports for Evidence Gate.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--visible-root")
    parser.add_argument("--github-repository", default="")
    parser.add_argument("--github-lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--jira-base-url", default="")
    parser.add_argument("--jira-user-email", default="")
    parser.add_argument("--jira-project-keys", default="")
    parser.add_argument("--jira-lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--confluence-base-url", default="")
    parser.add_argument("--confluence-user-email", default="")
    parser.add_argument("--confluence-space-keys", default="")
    parser.add_argument("--confluence-cql", default="")
    parser.add_argument("--confluence-lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--slack-channel-ids", default="")
    parser.add_argument("--slack-lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--pagerduty-lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--json-output")
    args = parser.parse_args()

    sources = materialize_live_external_sources(
        output_root=Path(args.output_root),
        visible_root=Path(args.visible_root) if args.visible_root else None,
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
        timeout_seconds=args.timeout_seconds,
    )
    serialized = json.dumps(sources, separators=(",", ":"))
    if args.json_output:
        Path(args.json_output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
