"""SQLite-backed audit storage for decision records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from evidence_gate.decision.models import DecisionRecord
from sqlalchemy import Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for audit storage."""


class AuditDecisionRow(Base):
    """Persisted audit decision payload plus a few queryable fields."""

    __tablename__ = "audit_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    request_type: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[str] = mapped_column(Text)


@dataclass(frozen=True, slots=True)
class LegacyArtifacts:
    decisions_dir: Path
    ledger_path: Path


class SQLiteAuditStore:
    """Persist decisions to a local SQLite database with legacy file import support."""

    database_name = "audit.db"

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.database_path = self.root / self.database_name
        self.legacy = LegacyArtifacts(
            decisions_dir=self.root / "decisions",
            ledger_path=self.root / "decisions.jsonl",
        )
        self.engine = create_engine(
            f"sqlite+pysqlite:///{self.database_path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        self._import_legacy_artifacts_if_needed()

    def save(self, record: DecisionRecord) -> None:
        payload = record.model_dump_json()
        with self.session_factory.begin() as session:
            existing = session.scalar(
                select(AuditDecisionRow).where(AuditDecisionRow.decision_id == record.decision_id)
            )
            if existing is None:
                session.add(self._row_from_record(record, payload))
                return
            existing.created_at = record.created_at.isoformat()
            existing.request_type = record.request_type
            existing.decision = record.decision.value
            existing.payload = payload

    def get(self, decision_id: str) -> DecisionRecord | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(AuditDecisionRow).where(AuditDecisionRow.decision_id == decision_id)
            )
        if row is None:
            return None
        return DecisionRecord.model_validate_json(row.payload)

    def list_recent(self, limit: int = 20) -> list[DecisionRecord]:
        if limit <= 0:
            return []
        with self.session_factory() as session:
            rows = session.scalars(
                select(AuditDecisionRow).order_by(AuditDecisionRow.id.desc()).limit(limit)
            ).all()
        return [DecisionRecord.model_validate_json(row.payload) for row in rows]

    def read_ledger_text(self) -> str:
        with self.session_factory() as session:
            rows = session.scalars(select(AuditDecisionRow).order_by(AuditDecisionRow.id.asc())).all()
        if not rows:
            return ""
        return "\n".join(row.payload for row in rows) + "\n"

    def _import_legacy_artifacts_if_needed(self) -> None:
        if self._has_rows():
            return
        legacy_records = list(self._iter_legacy_records())
        if not legacy_records:
            return
        with self.session_factory.begin() as session:
            for record in legacy_records:
                session.add(self._row_from_record(record, record.model_dump_json()))

    def _has_rows(self) -> bool:
        with self.session_factory() as session:
            return session.scalar(select(AuditDecisionRow.id).limit(1)) is not None

    def _iter_legacy_records(self) -> Iterable[DecisionRecord]:
        seen_ids: set[str] = set()
        if self.legacy.ledger_path.exists():
            for line in self.legacy.ledger_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = DecisionRecord.model_validate_json(line)
                if record.decision_id in seen_ids:
                    continue
                seen_ids.add(record.decision_id)
                yield record

        if self.legacy.decisions_dir.exists():
            for path in sorted(self.legacy.decisions_dir.glob("*.json")):
                record = DecisionRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if record.decision_id in seen_ids:
                    continue
                seen_ids.add(record.decision_id)
                yield record

    def _row_from_record(self, record: DecisionRecord, payload: str) -> AuditDecisionRow:
        return AuditDecisionRow(
            decision_id=record.decision_id,
            created_at=record.created_at.isoformat(),
            request_type=record.request_type,
            decision=record.decision.value,
            payload=payload,
        )

FileAuditStore = SQLiteAuditStore

__all__ = ["FileAuditStore", "SQLiteAuditStore"]
