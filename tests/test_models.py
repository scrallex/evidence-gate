from __future__ import annotations

from datetime import datetime, timezone

from evidence_gate.decision.models import (
    BlastRadius,
    DecisionName,
    DecisionRecord,
    EvidenceSpan,
    SourceType,
    TwinCase,
)


def test_decision_record_round_trip() -> None:
    record = DecisionRecord(
        decision_id="abc123",
        created_at=datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc),
        request_type="query",
        decision=DecisionName.ADMIT,
        hazard=0.18,
        recurrence=4,
        confidence=0.82,
        evidence_spans=[
            EvidenceSpan(
                source="docs/auth.md",
                source_type=SourceType.DOC,
                score=0.91,
                snippet="Session auth details",
                line_number=12,
            )
        ],
        twin_cases=[
            TwinCase(
                id="pr_1842",
                source="prs/pr_1842.md",
                source_type=SourceType.PR,
                similarity=0.86,
                summary="Token refresh rollout fix",
            )
        ],
        blast_radius=BlastRadius(files=4, tests=1, docs=1, runbooks=1, impacted_paths=["src/session.py"]),
        missing_evidence=[],
        answer_or_action="Proceed with review.",
        explanation="Decision admit based on strong evidence.",
        request_payload={"repo_path": "/repo", "query": "auth change"},
    )

    payload = record.model_dump_json()
    restored = DecisionRecord.model_validate_json(payload)

    assert restored.decision == DecisionName.ADMIT
    assert restored.evidence_spans[0].source == "docs/auth.md"
    assert restored.twin_cases[0].source_type == SourceType.PR

