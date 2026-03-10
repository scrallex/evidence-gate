"""Ingestion abstractions for repository and external evidence sources."""

from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.ingest.local_repo import LocalRepoIngestor
from evidence_gate.ingest.markdown_incident import MarkdownIncidentIngestor

__all__ = [
    "BaseIngestor",
    "LocalRepoIngestor",
    "MarkdownIncidentIngestor",
]
