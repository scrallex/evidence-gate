from __future__ import annotations

from pathlib import Path

from evidence_gate.policy_loader import (
    builtin_policy_path,
    list_builtin_policy_names,
    resolve_action_safety_policy,
)


def test_builtin_policy_presets_exist() -> None:
    names = list_builtin_policy_names()

    assert "strict-financial" in names
    assert "agile-frontend" in names
    assert builtin_policy_path("strict-financial").name == "strict-financial.yml"


def test_resolve_action_safety_policy_merges_preset_file_and_inline_override(tmp_path: Path) -> None:
    custom_policy = tmp_path / "custom-policy.yml"
    custom_policy.write_text(
        "max_blast_radius_files: 9\nrequire_runbook_evidence: true\n",
        encoding="utf-8",
    )

    resolved = resolve_action_safety_policy(
        preset="agile-frontend",
        file_path=str(custom_policy),
        inline_json='{"min_confidence":0.55,"require_precedent":true}',
        cwd=Path.cwd(),
    )

    assert resolved is not None
    assert resolved["require_test_evidence"] is True
    assert resolved["require_runbook_evidence"] is True
    assert resolved["require_precedent"] is True
    assert resolved["min_confidence"] == 0.55
    assert resolved["max_blast_radius_files"] == 9
