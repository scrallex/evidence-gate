#!/usr/bin/env python3
"""Fetch live read-only exports for Evidence Gate ingestion."""

from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

DEFAULT_LOOKBACK_DAYS = 30
GITHUB_SOURCE_KIND = "github"
JIRA_SOURCE_KIND = "jira"
PAGERDUTY_SOURCE_KIND = "pagerduty"


def materialize_live_external_sources(
    *,
    output_root: Path,
    visible_root: Path | None = None,
    github_repository: str | None = None,
    github_token: str | None = None,
    github_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    jira_base_url: str | None = None,
    jira_api_token: str | None = None,
    jira_user_email: str | None = None,
    jira_project_keys: str | tuple[str, ...] | list[str] | None = None,
    jira_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    pagerduty_token: str | None = None,
    pagerduty_lookback_days: int = DEFAULT_LOOKBACK_DAYS,
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
    project_keys = _normalize_project_keys(jira_project_keys or os.environ.get("JIRA_PROJECT_KEYS"))

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

    return external_sources


def fetch_recent_github_pull_requests(
    *,
    repository: str,
    token: str,
    lookback_days: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recently updated pull requests from the target GitHub repository."""

    api_root = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    cutoff = _utc_now() - timedelta(days=max(1, lookback_days))
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
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recently updated Jira issues and flatten them for ingest."""

    endpoint = base_url.rstrip("/") + "/rest/api/3/search"
    project_clause = ""
    if project_keys:
        quoted = ", ".join(project_keys)
        project_clause = f"project in ({quoted}) AND "
    jql = f"{project_clause}updated >= -{max(1, lookback_days)}d ORDER BY updated DESC"
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
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Fetch recent PagerDuty incidents."""

    api_root = (os.environ.get("PAGERDUTY_API_URL") or "https://api.pagerduty.com").rstrip("/")
    now = _utc_now()
    since = now - timedelta(days=max(1, lookback_days))
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


def _request_json(
    *,
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Live connector fetch failed with HTTP {exc.code}: {body[:400]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Live connector fetch failed: {exc.reason}") from exc
    return json.loads(body)


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
