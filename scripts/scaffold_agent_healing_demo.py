#!/usr/bin/env python3
"""Scaffold a public Evidence Gate healing-loop demo repository."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO_FILES: dict[str, str] = {
    ".gitignore": """__pycache__/
.pytest_cache/
.venv/
""",
    "README.md": """# Evidence Gate Healing Loop Demo

This repository is a minimal public demo for the Evidence Gate GitHub Action.

The story is intentionally simple:

- `billing/api.py` contains a bug in the tax calculation path.
- a first automated pull request fixes the code but skips the missing test.
- Evidence Gate blocks that pull request and leaves a retry prompt.
- a second commit adds the missing test and the pull request turns green.
""",
    "billing/__init__.py": "",
    "billing/api.py": """def calculate_total_cents(subtotal_cents: int, tax_rate_percent: int) -> int:
    \"\"\"Return the billed total in cents.

    BUG: this uses integer division for percentage conversion, which drops any
    non-100% tax rate to zero.
    \"\"\"

    tax_cents = int(subtotal_cents * (tax_rate_percent // 100))
    return subtotal_cents + tax_cents
""",
    "billing/health.py": """def healthcheck() -> str:
    return "ok"
""",
    "tests/test_health.py": """from billing.health import healthcheck


def test_healthcheck() -> None:
    assert healthcheck() == "ok"
""",
    "docs/billing.md": """# Billing service

The billing delivery path owns subtotal and tax calculations for invoice totals.
Any behavioral change in `billing/api.py` must ship with supporting tests before
merge.
""",
    "runbooks/billing_rollback.md": """# Billing rollback

If invoice totals regress after a deployment, disable writes and roll back the
last billing release before retrying customer traffic.
""",
    ".github/workflows/evidence-gate-demo.yml": """name: Evidence Gate Demo

on:
  pull_request:
    types:
      - opened
      - synchronize
      - reopened

permissions:
  contents: read
  pull-requests: write

jobs:
  evidence-gate:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Collect changed paths
        id: diff
        shell: bash
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          python - <<'PY'
          import json
          import os
          import subprocess
          from pathlib import Path

          output = subprocess.check_output(
              ["git", "diff", "--name-only", f"{os.environ['BASE_SHA']}..{os.environ['HEAD_SHA']}"],
              text=True,
          )
          paths = [line.strip() for line in output.splitlines() if line.strip()]
          with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
              handle.write(f"paths={json.dumps(paths)}\\n")
          PY

      - name: Run Evidence Gate
        id: evidence_gate
        uses: ./.github/actions/evidence-gate
        with:
          action_summary: >-
            Pull request #${{ github.event.pull_request.number }}:
            ${{ github.event.pull_request.title }}.
            Review the billing total calculation fix before merge and block if the change lacks supporting test evidence.
          changed_paths: ${{ steps.diff.outputs.paths }}
          base_sha: ${{ github.event.pull_request.base.sha }}
          head_sha: ${{ github.event.pull_request.head.sha }}
          safety_policy: >-
            {"corpus_profile":"open_source","require_test_evidence":true}
          fail_on_block: "false"

      - name: Upsert Evidence Gate PR comment
        if: ${{ always() && steps.evidence_gate.outputs.comment_path != '' }}
        uses: actions/github-script@v7
        env:
          COMMENT_PATH: ${{ steps.evidence_gate.outputs.comment_path }}
        with:
          script: |
            const fs = require("fs");

            const marker = "<!-- evidence-gate-comment -->";
            const body = `${marker}\\n${fs.readFileSync(process.env.COMMENT_PATH, "utf8")}`;
            const issue_number = context.payload.pull_request.number;
            const { owner, repo } = context.repo;

            const comments = await github.paginate(github.rest.issues.listComments, {
              owner,
              repo,
              issue_number,
              per_page: 100,
            });

            const existing = comments.find((comment) => {
              return comment.user?.type === "Bot" && comment.body?.includes(marker);
            });

            if (existing) {
              await github.rest.issues.updateComment({
                owner,
                repo,
                comment_id: existing.id,
                body,
              });
              return;
            }

            await github.rest.issues.createComment({
              owner,
              repo,
              issue_number,
              body,
            });

      - name: Enforce guardrail decision
        if: ${{ steps.evidence_gate.outcome == 'success' && steps.evidence_gate.outputs.allowed != 'true' }}
        shell: bash
        run: |
          echo "Evidence Gate blocked this pull request." >&2
          exit 1
""",
}

VENDORED_PATHS = (
    "action.yml",
    "Dockerfile",
    "README.md",
    "pyproject.toml",
    "app",
    "scripts",
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold(output_dir: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for relative_path, content in REPO_FILES.items():
        _write(output_dir / relative_path, content)

    vendored_root = output_dir / ".github" / "actions" / "evidence-gate"
    vendored_root.mkdir(parents=True, exist_ok=True)
    for relative_path in VENDORED_PATHS:
        source = repo_root / relative_path
        destination = vendored_root / relative_path
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/evidence-gate-healing-loop-demo"),
        help="Where to write the scaffolded demo repository.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = scaffold(args.output_dir)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
