"""Jira ticket and epic export ingestor."""

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


class JiraExportIngestor(BaseIngestor):
    """Convert Jira issue and epic exports into normalized ticket documents."""

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
                virtual_path=f"external_jira/{relative_path}",
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
            collection_keys=("issues", "tickets", "items", "results"),
        )
        documents: list[DocumentRecord] = []
        for index, item in enumerate(records, start=1):
            record = self._build_issue_document(item, fallback_key=f"{path.stem}-{index}")
            if record is not None:
                documents.append(record)
        return documents

    def _build_issue_document(
        self,
        payload: dict[str, object],
        *,
        fallback_key: str,
    ) -> DocumentRecord | None:
        key = first_non_empty(
            payload.get("key"),
            payload.get("issue_key"),
            payload.get("id"),
            fallback_key,
        )
        summary = first_non_empty(
            payload.get("summary"),
            payload.get("title"),
            payload.get("name"),
            key,
        )
        body = first_non_empty(
            payload.get("description"),
            payload.get("body"),
            payload.get("content"),
            "No ticket description provided.",
        )
        body = strip_html(body)
        status = first_non_empty(
            payload.get("status"),
            nested_text(payload, "status", "name"),
        )
        issue_type = first_non_empty(
            payload.get("issue_type"),
            payload.get("issuetype"),
            nested_text(payload, "issuetype", "name"),
        )
        epic = first_non_empty(
            payload.get("epic"),
            nested_text(payload, "epic", "key"),
            nested_text(payload, "epic", "name"),
        )
        author = first_non_empty(
            nested_text(payload, "creator", "displayName"),
            nested_text(payload, "creator", "name"),
            nested_text(payload, "reporter", "displayName"),
            nested_text(payload, "reporter", "name"),
            payload.get("author"),
        )
        external_url = first_non_empty(
            payload.get("browse_url"),
            payload.get("url"),
            payload.get("html_url"),
            payload.get("self"),
        )
        timestamp = parse_timestamp(
            payload.get("updated_at"),
            payload.get("updated"),
            payload.get("created_at"),
            payload.get("created"),
        )

        labels = payload.get("labels")
        label_text = None
        if isinstance(labels, list):
            label_text = ", ".join(str(label).strip() for label in labels if str(label).strip()) or None

        metadata = ExternalMetadata(
            author=author,
            external_url=external_url,
            timestamp=timestamp,
        )
        lines = [f"# Jira Ticket: {summary}", ""]
        lines.append(f"- Key: {key}")
        if status:
            lines.append(f"- Status: {status}")
        if issue_type:
            lines.append(f"- Type: {issue_type}")
        if epic:
            lines.append(f"- Epic: {epic}")
        if label_text:
            lines.append(f"- Labels: {label_text}")
        if author:
            lines.append(f"- Author: {author}")
        if external_url:
            lines.append(f"- External URL: {external_url}")
        if timestamp:
            lines.append(f"- Timestamp: {timestamp.isoformat()}")
        lines.extend(["", body])
        return build_document_record(
            virtual_path=f"external_jira/{slugify(key)}.md",
            source_type=SourceType.DOC,
            content=markdown_from_lines(*lines),
            metadata=metadata,
        )
