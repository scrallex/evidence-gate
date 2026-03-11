from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.decision.models import BlastRadius, DecisionName, DecisionRecord


def _record(decision_id: str, *, created_at: datetime | None = None) -> DecisionRecord:
    return DecisionRecord(
        decision_id=decision_id,
        created_at=created_at or datetime.now(timezone.utc),
        request_type="query",
        decision=DecisionName.ADMIT,
        hazard=0.1,
        recurrence=2,
        confidence=0.9,
        evidence_spans=[],
        twin_cases=[],
        blast_radius=BlastRadius(files=1),
        missing_evidence=[],
        answer_or_action=f"answer {decision_id}",
        explanation=f"explanation {decision_id}",
        request_payload={"decision_id": decision_id},
    )


def test_sqlite_audit_store_persists_and_lists_records(tmp_path: Path) -> None:
    store = FileAuditStore(tmp_path / "audit")
    first = _record("first", created_at=datetime(2026, 3, 11, 22, 0, tzinfo=timezone.utc))
    second = _record("second", created_at=datetime(2026, 3, 11, 22, 1, tzinfo=timezone.utc))

    store.save(first)
    store.save(second)

    assert (tmp_path / "audit" / "audit.db").exists()
    assert store.get("first") == first

    recent = store.list_recent(limit=2)
    assert [record.decision_id for record in recent] == ["second", "first"]

    ledger_lines = store.read_ledger_text().strip().splitlines()
    assert [json.loads(line)["decision_id"] for line in ledger_lines] == ["first", "second"]


def test_sqlite_audit_store_imports_legacy_jsonl_and_json_records(tmp_path: Path) -> None:
    audit_root = tmp_path / "audit"
    decisions_dir = audit_root / "decisions"
    decisions_dir.mkdir(parents=True)
    ledger_record = _record("legacy-ledger", created_at=datetime(2026, 3, 11, 21, 0, tzinfo=timezone.utc))
    json_record = _record("legacy-json", created_at=datetime(2026, 3, 11, 21, 1, tzinfo=timezone.utc))

    (audit_root / "decisions.jsonl").write_text(
        ledger_record.model_dump_json() + "\n",
        encoding="utf-8",
    )
    (decisions_dir / f"{json_record.decision_id}.json").write_text(
        json_record.model_dump_json(indent=2),
        encoding="utf-8",
    )

    store = FileAuditStore(audit_root)

    assert store.get("legacy-ledger") == ledger_record
    assert store.get("legacy-json") == json_record

    ledger_lines = store.read_ledger_text().strip().splitlines()
    assert [json.loads(line)["decision_id"] for line in ledger_lines] == [
        "legacy-ledger",
        "legacy-json",
    ]
