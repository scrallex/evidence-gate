#!/usr/bin/env python3
"""Publish and exercise the public Evidence Gate healing-loop demo repository."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from scaffold_agent_healing_demo import scaffold


WORKFLOW_NAME = "Evidence Gate Demo"
COMMENT_MARKER = "<!-- evidence-gate-comment -->"


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def gh_json(args: list[str]) -> Any:
    result = run(["gh", *args])
    return json.loads(result.stdout)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_in_file(path: Path, before: str, after: str) -> None:
    content = path.read_text(encoding="utf-8")
    if before not in content:
        raise ValueError(f"Could not find expected content in {path}")
    path.write_text(content.replace(before, after, 1), encoding="utf-8")


def current_login() -> str:
    payload = gh_json(["api", "user"])
    return str(payload["login"])


def repo_exists(repo: str) -> bool:
    result = run(["gh", "repo", "view", repo], check=False)
    return result.returncode == 0


def ensure_repo(
    *,
    repo: str,
    repo_dir: Path,
    delete_existing: bool,
) -> None:
    if repo_exists(repo):
        if not delete_existing:
            raise RuntimeError(f"GitHub repository already exists: {repo}")
        run(["gh", "repo", "delete", repo, "--yes"])
        time.sleep(2)

    run(["git", "init", "-b", "main"], cwd=repo_dir)
    run(["git", "config", "user.name", "Evidence Gate Demo Bot"], cwd=repo_dir)
    run(
        [
            "git",
            "config",
            "user.email",
            f"{repo.split('/', maxsplit=1)[0]}@users.noreply.github.com",
        ],
        cwd=repo_dir,
    )
    run(["git", "add", "."], cwd=repo_dir)
    run(["git", "commit", "-m", "Initial demo scaffold"], cwd=repo_dir)
    run(
        [
            "gh",
            "repo",
            "create",
            repo,
            "--public",
            "--source",
            str(repo_dir),
            "--remote",
            "origin",
            "--push",
            "--description",
            "Public Evidence Gate healing-loop demo repository.",
        ]
    )


def create_first_agent_commit(repo_dir: Path) -> str:
    run(["git", "checkout", "-b", "agent/fix-tax-calculation"], cwd=repo_dir)
    replace_in_file(
        repo_dir / "billing" / "api.py",
        "tax_cents = int(subtotal_cents * (tax_rate_percent // 100))",
        "tax_cents = int(subtotal_cents * (tax_rate_percent / 100))",
    )
    run(["git", "add", "billing/api.py"], cwd=repo_dir)
    run(
        [
            "git",
            "commit",
            "-m",
            "Fix billing tax calculation without test coverage",
        ],
        cwd=repo_dir,
    )
    run(["git", "push", "-u", "origin", "agent/fix-tax-calculation"], cwd=repo_dir)
    return git_head(repo_dir)


def create_healing_commit(repo_dir: Path) -> str:
    write(
        repo_dir / "tests" / "test_total.py",
        """from billing.api import calculate_total_cents


def test_calculate_total_cents_includes_tax() -> None:
    assert calculate_total_cents(1000, 8) == 1080
""",
    )
    run(["git", "add", "tests/test_total.py"], cwd=repo_dir)
    run(
        [
            "git",
            "commit",
            "-m",
            "Add regression test for billing tax calculation",
        ],
        cwd=repo_dir,
    )
    run(["git", "push"], cwd=repo_dir)
    return git_head(repo_dir)


def create_empty_sync_commit(repo_dir: Path, message: str) -> str:
    run(["git", "commit", "--allow-empty", "-m", message], cwd=repo_dir)
    run(["git", "push"], cwd=repo_dir)
    return git_head(repo_dir)


def git_head(repo_dir: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()


def create_pull_request(repo: str) -> dict[str, Any]:
    run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--base",
            "main",
            "--head",
            "agent/fix-tax-calculation",
            "--title",
            "Agent fix: restore billing tax calculation",
            "--body",
            "Automated agent attempt to fix the billing tax bug before merge.",
        ]
    )
    pulls = gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--head",
            "agent/fix-tax-calculation",
            "--json",
            "number,url,headRefOid",
        ]
    )
    if not pulls:
        raise RuntimeError("Could not resolve the opened pull request.")
    return pulls[0]


def wait_for_run(
    *,
    repo: str,
    head_sha: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        runs = gh_json(
            [
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                WORKFLOW_NAME,
                "--json",
                "databaseId,displayTitle,headSha,status,conclusion,url",
                "--limit",
                "20",
            ]
        )
        matches = [run_payload for run_payload in runs if run_payload.get("headSha") == head_sha]
        if matches:
            latest = matches[0]
            if latest.get("status") == "completed":
                return latest
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for workflow run for {head_sha}")


def wait_for_comment(
    *,
    repo: str,
    pr_number: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        comments = gh_json(["api", f"repos/{repo}/issues/{pr_number}/comments"])
        for comment in comments:
            body = str(comment.get("body", ""))
            if COMMENT_MARKER in body:
                return comment
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for Evidence Gate comment on PR #{pr_number}")


def pr_checks_text(repo: str, pr_number: int) -> str:
    result = run(["gh", "pr", "checks", str(pr_number), "--repo", repo], check=False)
    return result.stdout.strip()


def extract_retry_prompt(comment_body: str) -> str:
    marker = "### Suggested Retry Prompt"
    if marker not in comment_body:
        return ""
    tail = comment_body.split(marker, maxsplit=1)[1].strip()
    return tail.splitlines()[0].strip() if tail else ""


def capture_state(
    *,
    repo: str,
    pr_number: int,
    pr_url: str,
    run_payload: dict[str, Any],
    comment_body: str,
    checks_text: str,
    artifact_dir: Path,
    phase: str,
) -> dict[str, Any]:
    comment_path = artifact_dir / f"{phase}_comment.md"
    checks_path = artifact_dir / f"{phase}_checks.txt"
    write(comment_path, comment_body)
    write(checks_path, checks_text + "\n")
    return {
        "phase": phase,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "run": run_payload,
        "comment_path": str(comment_path),
        "checks_path": str(checks_path),
        "retry_prompt": extract_retry_prompt(comment_body),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-name",
        default="evidence-gate-healing-loop-demo",
        help="Name of the public GitHub repository to create.",
    )
    parser.add_argument(
        "--owner",
        default="",
        help="GitHub owner. Defaults to the currently authenticated gh user.",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("/tmp/evidence-gate-healing-loop-demo"),
        help="Local checkout path for the generated demo repository.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/agent_healing_demo"),
        help="Where to write captured demo artifacts.",
    )
    parser.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete an existing GitHub repository with the same name before creating the demo.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help="Maximum time to wait for each workflow run or comment.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    owner = args.owner or current_login()
    repo = f"{owner}/{args.repo_name}"
    repo_dir = scaffold(args.workdir)
    artifact_dir = args.artifact_dir.expanduser().resolve()
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    ensure_repo(repo=repo, repo_dir=repo_dir, delete_existing=args.delete_existing)
    create_first_agent_commit(repo_dir)
    pull_request = create_pull_request(repo)
    first_head = create_empty_sync_commit(repo_dir, "Trigger Evidence Gate pull request evaluation")
    first_run = wait_for_run(repo=repo, head_sha=first_head, timeout_seconds=args.timeout_seconds)
    first_comment = wait_for_comment(
        repo=repo,
        pr_number=int(pull_request["number"]),
        timeout_seconds=args.timeout_seconds,
    )
    first_state = capture_state(
        repo=repo,
        pr_number=int(pull_request["number"]),
        pr_url=str(pull_request["url"]),
        run_payload=first_run,
        comment_body=str(first_comment["body"]),
        checks_text=pr_checks_text(repo, int(pull_request["number"])),
        artifact_dir=artifact_dir,
        phase="blocked",
    )

    second_head = create_healing_commit(repo_dir)
    second_run = wait_for_run(repo=repo, head_sha=second_head, timeout_seconds=args.timeout_seconds)
    second_comment = wait_for_comment(
        repo=repo,
        pr_number=int(pull_request["number"]),
        timeout_seconds=args.timeout_seconds,
    )
    second_state = capture_state(
        repo=repo,
        pr_number=int(pull_request["number"]),
        pr_url=str(pull_request["url"]),
        run_payload=second_run,
        comment_body=str(second_comment["body"]),
        checks_text=pr_checks_text(repo, int(pull_request["number"])),
        artifact_dir=artifact_dir,
        phase="healed",
    )

    summary = {
        "repo": repo,
        "repo_url": f"https://github.com/{repo}",
        "local_repo_dir": str(repo_dir),
        "pr_number": int(pull_request["number"]),
        "pr_url": str(pull_request["url"]),
        "blocked": first_state,
        "healed": second_state,
    }
    write(artifact_dir / "demo_summary.json", json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
