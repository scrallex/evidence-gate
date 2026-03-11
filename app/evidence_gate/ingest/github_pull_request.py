"""GitHub pull request export ingestor."""

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


class GitHubPullRequestIngestor(BaseIngestor):
    """Convert GitHub pull request exports into normalized PR documents."""

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
                virtual_path=f"external_github_prs/{relative_path}",
                source_type=SourceType.PR,
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
            collection_keys=("pulls", "pull_requests", "items", "results"),
        )
        documents: list[DocumentRecord] = []
        for index, item in enumerate(records, start=1):
            record = self._build_pull_request_document(item, fallback_id=f"{path.stem}-{index}")
            if record is not None:
                documents.append(record)
        return documents

    def _build_pull_request_document(
        self,
        payload: dict[str, object],
        *,
        fallback_id: str,
    ) -> DocumentRecord | None:
        number = first_non_empty(payload.get("number"), payload.get("id"), fallback_id)
        title = first_non_empty(payload.get("title"), payload.get("summary"), payload.get("name"), number)
        body = first_non_empty(
            payload.get("body"),
            payload.get("description"),
            payload.get("content"),
            "No pull request description provided.",
        )
        body = strip_html(body)
        state = first_non_empty(payload.get("state"), payload.get("status"))
        base_ref = first_non_empty(
            nested_text(payload, "base", "ref"),
            nested_text(payload, "base", "label"),
        )
        head_ref = first_non_empty(
            nested_text(payload, "head", "ref"),
            nested_text(payload, "head", "label"),
        )
        repository = first_non_empty(
            nested_text(payload, "base", "repo", "full_name"),
            nested_text(payload, "head", "repo", "full_name"),
            payload.get("repository"),
        )
        author = first_non_empty(
            nested_text(payload, "user", "login"),
            nested_text(payload, "author", "login"),
            payload.get("author"),
        )
        external_url = first_non_empty(
            payload.get("html_url"),
            payload.get("url"),
        )
        timestamp = parse_timestamp(
            payload.get("updated_at"),
            payload.get("merged_at"),
            payload.get("closed_at"),
            payload.get("created_at"),
        )
        merged_at = parse_timestamp(payload.get("merged_at"))
        labels = payload.get("labels")
        label_text = None
        if isinstance(labels, list):
            normalized_labels: list[str] = []
            for label in labels:
                if isinstance(label, dict):
                    value = first_non_empty(label.get("name"))
                else:
                    value = first_non_empty(label)
                if value:
                    normalized_labels.append(value)
            label_text = ", ".join(normalized_labels) or None
        file_paths = _extract_pull_request_paths(payload)

        metadata = ExternalMetadata(
            author=author,
            external_url=external_url,
            timestamp=timestamp,
        )
        lines = [f"# GitHub Pull Request: {title}", ""]
        lines.append(f"- PR Number: {number}")
        if repository:
            lines.append(f"- Repository: {repository}")
        if state:
            lines.append(f"- State: {state}")
        if payload.get("draft") is True:
            lines.append("- Draft: true")
        if base_ref:
            lines.append(f"- Base: {base_ref}")
        if head_ref:
            lines.append(f"- Head: {head_ref}")
        if label_text:
            lines.append(f"- Labels: {label_text}")
        if author:
            lines.append(f"- Author: {author}")
        if external_url:
            lines.append(f"- External URL: {external_url}")
        if timestamp:
            lines.append(f"- Timestamp: {timestamp.isoformat()}")
        if merged_at is not None:
            lines.append(f"- Merged At: {merged_at.isoformat()}")
        if file_paths:
            lines.append(f"- Changed Paths: {', '.join(file_paths[:25])}")
        lines.extend(["", body])
        return build_document_record(
            virtual_path=f"external_github_prs/{slugify(f'pr_{number}')}.md",
            source_type=SourceType.PR,
            content=markdown_from_lines(*lines),
            metadata=metadata,
        )


def _extract_pull_request_paths(payload: dict[str, object]) -> list[str]:
    candidates = payload.get("files")
    if not isinstance(candidates, list):
        return []
    paths: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        filename = first_non_empty(item.get("filename"), item.get("path"))
        if filename:
            paths.append(filename)
    return paths
