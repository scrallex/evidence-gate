"""External incident ingestor for markdown or JSON exports."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from evidence_gate.decision.models import ExternalMetadata, SourceType
from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.retrieval.repository import DocumentRecord, tokenize


class MarkdownIncidentIngestor(BaseIngestor):
    """Convert exported incident files into normalized incident documents."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def collect_documents(self) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in (".json", ".md", ".txt", ".rst"):
                continue
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

        if not content.strip():
            return None

        return DocumentRecord(
            path=virtual_path,
            source_type=SourceType.INCIDENT,
            content=content,
            lines=tuple(content.splitlines()),
            token_counts=Counter(tokenize(content)),
            path_token_counts=Counter(tokenize(virtual_path.replace("/", " "))),
            metadata=metadata,
        )


def _incident_markdown_from_json(path: Path) -> tuple[str, ExternalMetadata]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Incident export must be a JSON object: {path}")

    title = _first_non_empty(
        payload.get("title"),
        payload.get("summary"),
        payload.get("name"),
        payload.get("key"),
        path.stem,
    )
    body = _first_non_empty(
        payload.get("body"),
        payload.get("description"),
        payload.get("content"),
        payload.get("details"),
        "No incident body provided.",
    )
    author = _first_non_empty(
        payload.get("author"),
        payload.get("owner"),
        payload.get("reporter"),
        payload.get("created_by"),
    )
    external_url = _first_non_empty(
        payload.get("external_url"),
        payload.get("url"),
        payload.get("html_url"),
        payload.get("link"),
    )
    timestamp = _parse_timestamp(
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
    return "\n".join(lines).strip() + "\n", metadata


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_timestamp(*values: object) -> datetime | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        candidate = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None
