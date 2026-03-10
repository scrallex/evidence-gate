"""PagerDuty incident export ingestor."""

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


class PagerDutyIncidentIngestor(BaseIngestor):
    """Convert PagerDuty incident exports into normalized incident documents."""

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
                virtual_path=f"external_pagerduty/{relative_path}",
                source_type=SourceType.INCIDENT,
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
            collection_keys=("incidents", "records", "events", "items"),
        )
        documents: list[DocumentRecord] = []
        for index, item in enumerate(records, start=1):
            record = self._build_incident_document(item, fallback_id=f"{path.stem}-{index}")
            if record is not None:
                documents.append(record)
        return documents

    def _build_incident_document(
        self,
        payload: dict[str, object],
        *,
        fallback_id: str,
    ) -> DocumentRecord | None:
        incident_id = first_non_empty(
            payload.get("incident_number"),
            payload.get("id"),
            fallback_id,
        )
        title = first_non_empty(
            payload.get("title"),
            payload.get("summary"),
            payload.get("name"),
            incident_id,
        )
        body = first_non_empty(
            payload.get("description"),
            payload.get("body"),
            payload.get("details"),
            payload.get("content"),
            "No incident body provided.",
        )
        body = strip_html(body)
        status = first_non_empty(payload.get("status"))
        service = first_non_empty(
            nested_text(payload, "service", "summary"),
            nested_text(payload, "service", "name"),
            payload.get("service"),
        )
        urgency = first_non_empty(payload.get("urgency"), payload.get("severity"))
        author = first_non_empty(
            nested_text(payload, "last_status_change_by", "summary"),
            nested_text(payload, "assigned_to_user", "summary"),
            nested_text(payload, "assignee", "summary"),
            payload.get("author"),
        )
        external_url = first_non_empty(
            payload.get("html_url"),
            payload.get("self"),
            payload.get("url"),
        )
        timestamp = parse_timestamp(
            payload.get("updated_at"),
            payload.get("created_at"),
            payload.get("last_status_change_at"),
        )

        metadata = ExternalMetadata(
            author=author,
            external_url=external_url,
            timestamp=timestamp,
        )
        lines = [f"# PagerDuty Incident: {title}", ""]
        lines.append(f"- Incident ID: {incident_id}")
        if status:
            lines.append(f"- Status: {status}")
        if service:
            lines.append(f"- Service: {service}")
        if urgency:
            lines.append(f"- Urgency: {urgency}")
        if author:
            lines.append(f"- Author: {author}")
        if external_url:
            lines.append(f"- External URL: {external_url}")
        if timestamp:
            lines.append(f"- Timestamp: {timestamp.isoformat()}")
        lines.extend(["", body])
        return build_document_record(
            virtual_path=f"external_pagerduty/{slugify(str(incident_id))}.md",
            source_type=SourceType.INCIDENT,
            content=markdown_from_lines(*lines),
            metadata=metadata,
        )
