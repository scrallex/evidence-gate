from __future__ import annotations

from pathlib import Path

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.config import Settings
from evidence_gate.decision.models import (
    ActionSafetyPolicy,
    BlastRadius,
    DecisionName,
    DecisionRecord,
    EvidenceSpan,
    SourceType,
)
from evidence_gate.decision.service import DecisionService
from datetime import datetime, timezone


def test_build_missing_evidence_uses_frontend_specific_test_note(tmp_path: Path) -> None:
    service = DecisionService(settings=Settings(), audit_store=FileAuditStore(tmp_path / "audit"))

    missing = service._build_missing_evidence(  # noqa: SLF001 - intentional unit coverage of policy helper
        evidence_spans=[
            EvidenceSpan(
                source="docs/dashboard.md",
                source_type=SourceType.DOC,
                score=0.9,
                snippet="Shared dashboard panel behavior.",
                verified=True,
            )
        ],
        twin_cases=[],
        blast_radius=BlastRadius(files=3, tests=2, docs=1, runbooks=0),
        changed_paths=["apps/web/src/components/SharedPanel.tsx"],
    )

    assert (
        "Downstream frontend tests appear impacted, but no supporting frontend test evidence was found."
        in missing
    )


def test_build_missing_evidence_skips_test_and_runbook_notes_when_paths_are_changed(tmp_path: Path) -> None:
    service = DecisionService(settings=Settings(), audit_store=FileAuditStore(tmp_path / "audit"))

    missing = service._build_missing_evidence(  # noqa: SLF001 - intentional unit coverage of policy helper
        evidence_spans=[
            EvidenceSpan(
                source="docs/security.md",
                source_type=SourceType.DOC,
                score=0.8,
                snippet="Security model notes.",
                verified=True,
            )
        ],
        twin_cases=[],
        blast_radius=BlastRadius(files=4, tests=1, docs=1, runbooks=1),
        changed_paths=["tests/test_config.py", "runbooks/live_connector_operations.md"],
    )

    assert "No supporting test evidence was found for the affected flow." not in missing
    assert "No runbook or operational handling evidence was found." not in missing


def test_apply_action_policy_accepts_changed_test_and_runbook_paths(tmp_path: Path) -> None:
    service = DecisionService(settings=Settings(), audit_store=FileAuditStore(tmp_path / "audit"))
    record = DecisionRecord(
        decision_id="decision-1",
        created_at=datetime.now(timezone.utc),
        request_type="action",
        decision=DecisionName.ESCALATE,
        hazard=0.4,
        recurrence=1,
        confidence=0.4,
        evidence_spans=[
            EvidenceSpan(
                source="docs/security.md",
                source_type=SourceType.DOC,
                score=0.8,
                snippet="Security model notes.",
                verified=True,
            )
        ],
        twin_cases=[],
        blast_radius=BlastRadius(files=4, tests=1, docs=1, runbooks=1),
        missing_evidence=[],
        answer_or_action="answer",
        explanation="explanation",
        request_payload={
            "changed_paths": ["tests/test_config.py", "runbooks/live_connector_operations.md"],
        },
    )

    updated, violations = service._apply_action_safety_policy(  # noqa: SLF001 - intentional unit coverage
        record,
        ActionSafetyPolicy(
            corpus_profile="open_source",
            require_test_evidence=True,
            require_runbook_evidence=True,
        ),
    )

    assert "Policy requires supporting test evidence." not in violations
    assert "Policy requires runbook or operational evidence." not in violations
    assert updated.missing_evidence == []
