from __future__ import annotations

from pathlib import Path

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.config import Settings
from evidence_gate.decision.models import BlastRadius, EvidenceSpan, SourceType
from evidence_gate.decision.service import DecisionService


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
