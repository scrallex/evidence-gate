"""Confluence page export ingestor."""

from __future__ import annotations

from pathlib import Path

from evidence_gate.decision.models import ExternalMetadata, SourceType
from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.ingest.external_common import (
    build_document_record,
    first_non_empty,
    iter_export_records,
    iter_external_export_files,
    markdown_from_lines,
    nested_text,
    parse_timestamp,
    read_json_payload,
    slugify,
    strip_html,
)
from evidence_gate.retrieval.repository import DocumentRecord


class ConfluenceExportIngestor(BaseIngestor):
    """Convert Confluence page exports into normalized documentation records."""

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
                virtual_path=f"external_confluence/{relative_path}",
                source_type=SourceType.DOC,
                content=path.read_text(encoding="utf-8", errors="ignore"),
                metadata=None,
            )
            if record is not None:
                documents.append(record)
        return documents

    def _build_json_documents(self, path: Path) -> list[DocumentRecord]:
        payload = read_json_payload(path)
        records = iter_export_records(
            payload,
            collection_keys=("pages", "results", "items"),
        )
        documents: list[DocumentRecord] = []
        for index, item in enumerate(records, start=1):
            record = self._build_page_document(item, fallback_title=f"{path.stem}-{index}")
            if record is not None:
                documents.append(record)
        return documents

    def _build_page_document(
        self,
        payload: dict[str, object],
        *,
        fallback_title: str,
    ) -> DocumentRecord | None:
        title = first_non_empty(payload.get("title"), payload.get("name"), fallback_title) or fallback_title
        body = first_non_empty(
            nested_text(payload, "body", "storage", "value"),
            nested_text(payload, "body", "view", "value"),
            payload.get("content"),
            payload.get("body"),
            "No page body provided.",
        )
        body = strip_html(body)
        space = first_non_empty(
            nested_text(payload, "space", "key"),
            nested_text(payload, "space", "name"),
            payload.get("space"),
            "space",
        )
        author = first_non_empty(
            nested_text(payload, "version", "by", "displayName"),
            nested_text(payload, "history", "createdBy", "displayName"),
            payload.get("author"),
        )
        external_url = first_non_empty(
            nested_text(payload, "_links", "base"),
            payload.get("url"),
            payload.get("webui"),
        )
        if external_url and isinstance(payload.get("_links"), dict):
            webui = first_non_empty(payload.get("_links", {}).get("webui"))
            if webui and not external_url.endswith(webui):
                external_url = external_url.rstrip("/") + "/" + webui.lstrip("/")
        timestamp = parse_timestamp(
            nested_text(payload, "version", "when"),
            payload.get("updated_at"),
            payload.get("created_at"),
        )
        metadata = ExternalMetadata(
            author=author,
            external_url=external_url,
            timestamp=timestamp,
        )
        lines = [f"# Confluence Page: {title}", ""]
        lines.append(f"- Space: {space}")
        if author:
            lines.append(f"- Author: {author}")
        if external_url:
            lines.append(f"- External URL: {external_url}")
        if timestamp:
            lines.append(f"- Timestamp: {timestamp.isoformat()}")
        lines.extend(["", body])
        return build_document_record(
            virtual_path=f"external_confluence/{slugify(space)}/{slugify(title)}.md",
            source_type=SourceType.DOC,
            content=markdown_from_lines(*lines),
            metadata=metadata,
        )
