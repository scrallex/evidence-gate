"""Base ingestion interface for Evidence Gate corpora."""

from __future__ import annotations

from abc import ABC, abstractmethod

from evidence_gate.retrieval.repository import DocumentRecord


class BaseIngestor(ABC):
    """Produce normalized document records for the knowledge base."""

    @abstractmethod
    def collect_documents(self) -> list[DocumentRecord]:
        """Return normalized documents from this source."""
