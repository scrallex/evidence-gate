from __future__ import annotations

from datetime import datetime, timezone

from evidence_gate.decision.models import (
    ActionDecisionResponse,
    BlastRadius,
    DecisionName,
    DecisionRecord,
    EvidenceSpan,
    ExternalMetadata,
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
                metadata=ExternalMetadata(
                    author="docs-bot",
                    external_url="https://example.com/auth-doc",
                ),
            )
        ],
        twin_cases=[
            TwinCase(
                id="pr_1842",
                source="prs/pr_1842.md",
                source_type=SourceType.PR,
                similarity=0.86,
                summary="Token refresh rollout fix",
                metadata=ExternalMetadata(
                    author="reviewer",
                    external_url="https://example.com/pr/1842",
                ),
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
    assert restored.evidence_spans[0].metadata is not None
    assert restored.evidence_spans[0].metadata.external_url == "https://example.com/auth-doc"


def test_action_decision_response_round_trip() -> None:
    record = DecisionRecord(
        decision_id="block123",
        created_at=datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc),
        request_type="action",
        decision=DecisionName.ESCALATE,
        hazard=0.42,
        recurrence=2,
        confidence=0.51,
        evidence_spans=[],
        twin_cases=[],
        blast_radius=BlastRadius(files=7, tests=1, docs=1, runbooks=0),
        missing_evidence=["No runbook or operational handling evidence was found."],
        answer_or_action="Escalate this change for review.",
        explanation="Decision escalate based on partial support.",
        request_payload={"repo_path": "/repo", "action_summary": "risky change"},
    )
    response = ActionDecisionResponse(
        allowed=False,
        status="block",
        blocking_decisions=[DecisionName.ABSTAIN, DecisionName.ESCALATE],
        failure_reason="Action blocked because Evidence Gate returned escalate for the proposed change.",
        decision_record=record,
    )

    restored = ActionDecisionResponse.model_validate_json(response.model_dump_json())

    assert restored.allowed is False
    assert restored.status == "block"
    assert restored.decision_record.request_type == "action"
