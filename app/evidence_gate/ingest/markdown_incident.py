"""External incident ingestor for markdown or JSON exports."""

from __future__ import annotations

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
)
from evidence_gate.retrieval.repository import DocumentRecord


class MarkdownIncidentIngestor(BaseIngestor):
    """Convert exported incident files into normalized incident documents."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def collect_documents(self) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        for path in iter_external_export_files(self.root):
            record = self._build_document(path)
            if record is not None:
                documents.append(record)
        return documents

    def _build_document(self, path: Path) -> DocumentRecord | None:
        relative_path = path.relative_to(self.root).as_posix()
        if path.suffix.lower() == ".json":
            content, metadata = _incident_markdown_from_json(path)
            virtual_path = f"external_incidents/{Path(relative_path).with_suffix('.md').as_posix()}"
        else:
            content = path.read_text(encoding="utf-8", errors="ignore")
            metadata = None
            virtual_path = f"external_incidents/{relative_path}"
        return build_document_record(
            virtual_path=virtual_path,
            source_type=SourceType.INCIDENT,
            content=content,
            metadata=metadata,
        )


def _incident_markdown_from_json(path: Path) -> tuple[str, ExternalMetadata]:
    payload = read_json_payload(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Incident export must be a JSON object: {path}")

    title = first_non_empty(
        payload.get("title"),
        payload.get("summary"),
        payload.get("name"),
        payload.get("key"),
        path.stem,
    )
    body = first_non_empty(
        payload.get("body"),
        payload.get("description"),
        payload.get("content"),
        payload.get("details"),
        "No incident body provided.",
    )
    author = first_non_empty(
        payload.get("author"),
        payload.get("owner"),
        payload.get("reporter"),
        payload.get("created_by"),
    )
    external_url = first_non_empty(
        payload.get("external_url"),
        payload.get("url"),
        payload.get("html_url"),
        payload.get("link"),
    )
    timestamp = parse_timestamp(
        payload.get("timestamp"),
        payload.get("created_at"),
        payload.get("updated_at"),
        payload.get("occurred_at"),
    )

    metadata = ExternalMetadata(
        author=author,
        external_url=external_url,
        timestamp=timestamp,
    )

    lines = [f"# Incident: {title}", ""]
    if author:
        lines.append(f"- Author: {author}")
    if external_url:
        lines.append(f"- External URL: {external_url}")
    if timestamp:
        lines.append(f"- Timestamp: {timestamp.isoformat()}")
    if len(lines) > 2:
        lines.append("")
    lines.append(str(body).strip())
    return markdown_from_lines(*lines), metadata
