"""Slack export ingestor for incident-oriented channel threads."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from evidence_gate.decision.models import ExternalMetadata, SourceType
from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.ingest.external_common import (
    build_document_record,
    first_non_empty,
    iter_external_export_files,
    markdown_from_lines,
    parse_timestamp,
    read_json_payload,
    slugify,
)
from evidence_gate.retrieval.repository import DocumentRecord


class SlackIncidentIngestor(BaseIngestor):
    """Convert Slack channel exports into incident-oriented thread documents."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def collect_documents(self) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        for path in iter_external_export_files(self.root):
            if path.suffix.lower() == ".json":
                documents.extend(self._build_json_documents(path))
                continue
            relative_path = path.relative_to(self.root).as_posix()
            record = build_document_record(
                virtual_path=f"external_slack/{relative_path}",
                source_type=SourceType.INCIDENT,
                content=path.read_text(encoding="utf-8", errors="ignore"),
                metadata=None,
            )
            if record is not None:
                documents.append(record)
        return documents

    def _build_json_documents(self, path: Path) -> list[DocumentRecord]:
        payload = read_json_payload(path)
        if not isinstance(payload, list):
            raise ValueError(f"Slack export must be a JSON array: {path}")

        threads: dict[str, list[dict[str, object]]] = defaultdict(list)
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = first_non_empty(item.get("text"))
            if not text:
                continue
            thread_id = first_non_empty(item.get("thread_ts"), item.get("ts"))
            if thread_id is None:
                continue
            threads[thread_id].append(item)

        documents: list[DocumentRecord] = []
        channel = path.parent.relative_to(self.root).as_posix() if path.parent != self.root else "channel"
        for thread_id, messages in sorted(threads.items()):
            messages.sort(key=lambda item: float(first_non_empty(item.get("ts"), "0") or "0"))
            root_message = messages[0]
            root_text = first_non_empty(root_message.get("text"), thread_id) or thread_id
            author = first_non_empty(
                root_message.get("user_profile", {}).get("display_name") if isinstance(root_message.get("user_profile"), dict) else None,
                root_message.get("username"),
                root_message.get("user"),
            )
            timestamp = parse_timestamp(root_message.get("ts"))
            lines = [f"# Slack Incident Thread: {root_text[:120]}", ""]
            lines.append(f"- Channel: {channel}")
            if author:
                lines.append(f"- Author: {author}")
            if timestamp:
                lines.append(f"- Timestamp: {timestamp.isoformat()}")
            lines.append("")
            lines.append("## Messages")
            for message in messages[:25]:
                message_author = first_non_empty(
                    message.get("user_profile", {}).get("display_name") if isinstance(message.get("user_profile"), dict) else None,
                    message.get("username"),
                    message.get("user"),
                    "unknown",
                )
                message_timestamp = parse_timestamp(message.get("ts"))
                stamp = message_timestamp.isoformat() if message_timestamp is not None else "unknown"
                lines.append(f"- [{stamp}] {message_author}: {first_non_empty(message.get('text'), '')}")
            metadata = ExternalMetadata(author=author, external_url=None, timestamp=timestamp)
            record = build_document_record(
                virtual_path=f"external_slack/{channel}/{slugify(thread_id)}.md",
                source_type=SourceType.INCIDENT,
                content=markdown_from_lines(*lines),
                metadata=metadata,
            )
            if record is not None:
                documents.append(record)
        return documents
