"""Repository-backed ingestor for local source trees."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.retrieval.repository import (
    DocumentRecord,
    classify_source_type,
    iter_repository_files,
    tokenize,
)


class LocalRepoIngestor(BaseIngestor):
    """Scan a local repository into normalized document records."""

    def __init__(
        self,
        repo_root: Path,
        *,
        exclude_relative_prefixes: tuple[str, ...] = (),
    ) -> None:
        self.repo_root = Path(repo_root)
        self.exclude_relative_prefixes = exclude_relative_prefixes

    def collect_documents(self) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        for path in iter_repository_files(
            self.repo_root,
            exclude_relative_prefixes=self.exclude_relative_prefixes,
        ):
            content = path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue
            rel_path = path.relative_to(self.repo_root).as_posix()
            documents.append(
                DocumentRecord(
                    path=rel_path,
                    source_type=classify_source_type(rel_path),
                    content=content,
                    lines=tuple(content.splitlines()),
                    token_counts=Counter(tokenize(content)),
                    path_token_counts=Counter(tokenize(rel_path.replace("/", " "))),
                )
            )
        return documents
