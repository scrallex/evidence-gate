from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_agent_gate_outputs_retry_contract(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _write(
        repo_root / "src" / "billing.py",
        "def calculate_total_cents(subtotal_cents: int, tax_rate_percent: int) -> int:\n"
        "    return subtotal_cents + int(subtotal_cents * (tax_rate_percent / 100))\n",
    )
    _write(
        repo_root / "docs" / "billing.md",
        "# Billing\n\nBilling total calculation must be covered by regression tests before merge.\n",
    )

    env = os.environ.copy()
    env["EVIDENCE_GATE_AUDIT_ROOT"] = str(audit_root)
    env["EVIDENCE_GATE_KB_ROOT"] = str(kb_root)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_agent_gate.py",
            "--repo-path",
            str(repo_root),
            "--action-summary",
            "Review the billing total change before editing code.",
            "--changed-path",
            "src/billing.py",
            "--safety-policy-json",
            '{"require_test_evidence": true}',
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    payload = json.loads(result.stdout)
    assert payload["preparation"]["ready"] is True
    assert payload["action_decision"]["allowed"] is False
    assert payload["next_step"] == "repair_and_retry"
    assert payload["retry_prompt"].startswith("Evidence Gate blocked the previous attempt because:")
    assert "docs/billing.md" in payload["strongest_evidence_sources"]
