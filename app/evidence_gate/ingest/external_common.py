"""Helpers shared by external export ingestors."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from html import unescape
from pathlib import Path

from evidence_gate.decision.models import ExternalMetadata, SourceType
from evidence_gate.retrieval.repository import DocumentRecord, tokenize

SUPPORTED_EXPORT_EXTENSIONS = (".json", ".md", ".rst", ".txt")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def iter_external_export_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXPORT_EXTENSIONS:
            files.append(path)
    return files


def build_document_record(
    *,
    virtual_path: str,
    source_type: SourceType,
    content: str,
    metadata: ExternalMetadata | None,
) -> DocumentRecord | None:
    if not content.strip():
        return None
    return DocumentRecord(
        path=virtual_path,
        source_type=source_type,
        content=content,
        lines=tuple(content.splitlines()),
        token_counts=Counter(tokenize(content)),
        path_token_counts=Counter(tokenize(virtual_path.replace("/", " "))),
        metadata=metadata,
    )


def read_json_payload(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_export_records(payload: object, *, collection_keys: tuple[str, ...]) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("Export payload must be a JSON object or array.")
    for key in collection_keys:
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return [payload]


def first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def nested_text(payload: dict[str, object], *keys: str) -> str | None:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return first_non_empty(current)


def parse_timestamp(*values: object) -> datetime | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=UTC)
        text = str(value).strip()
        if not text:
            continue
        if text.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(text), tz=UTC)
        candidate = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def markdown_from_lines(*lines: str) -> str:
    normalized = [line.rstrip() for line in lines if line is not None]
    return "\n".join(normalized).strip() + "\n"


def strip_html(text: str) -> str:
    return unescape(_HTML_TAG_RE.sub(" ", text))


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return slug or "record"
