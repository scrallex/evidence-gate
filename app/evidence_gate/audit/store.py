"""File-backed audit storage for decision records."""

from __future__ import annotations

from pathlib import Path

from evidence_gate.decision.models import DecisionRecord


class FileAuditStore:
    """Persist decisions to individual JSON files plus a JSONL ledger."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.decisions_dir = self.root / "decisions"
        self.ledger_path = self.root / "decisions.jsonl"
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, record: DecisionRecord) -> None:
        decision_path = self.decisions_dir / f"{record.decision_id}.json"
        decision_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")

    def get(self, decision_id: str) -> DecisionRecord | None:
        decision_path = self.decisions_dir / f"{decision_id}.json"
        if not decision_path.exists():
            return None
        return DecisionRecord.model_validate_json(decision_path.read_text(encoding="utf-8"))

    def list_recent(self, limit: int = 20) -> list[DecisionRecord]:
        if limit <= 0 or not self.ledger_path.exists():
            return []
        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        records: list[DecisionRecord] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            records.append(DecisionRecord.model_validate_json(line))
            if len(records) >= limit:
                break
        return records

    def read_ledger_text(self) -> str:
        if not self.ledger_path.exists():
            return ""
        return self.ledger_path.read_text(encoding="utf-8")
