"""Graph-backed summary ingestor for LSIF or SCIP sidecars."""

from __future__ import annotations

from pathlib import Path

from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.ingest.external_common import build_document_record, markdown_from_lines
from evidence_gate.native_graph import load_repository_native_graph
from evidence_gate.retrieval.repository import DocumentRecord, classify_source_type


class NativeGraphIngestor(BaseIngestor):
    """Convert native graph sidecars into file-aligned summary documents."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def collect_documents(self) -> list[DocumentRecord]:
        graph = load_repository_native_graph(self.repo_root)
        if not graph.has_edges():
            return []

        documents: list[DocumentRecord] = []
        exports = ", ".join(sorted(graph.exports))
        for source_path in sorted(graph.paths()):
            referenced_paths = sorted(graph.edges_by_source.get(source_path, set()))
            incoming_paths = sorted(graph.incoming_by_target.get(source_path, set()))
            symbols = sorted(graph.symbols_by_source.get(source_path, set()))
            edge_details = graph.edge_details_by_source.get(source_path, [])
            if not (referenced_paths or incoming_paths or symbols or edge_details):
                continue

            lines = [f"# Native Graph Summary: {source_path}", ""]
            lines.append(f"- Graph exports: {exports}")
            if symbols:
                lines.append(f"- Symbols: {', '.join(symbols[:12])}")
            if referenced_paths:
                lines.append(f"- References: {', '.join(referenced_paths[:12])}")
            if incoming_paths:
                lines.append(f"- Referenced by: {', '.join(incoming_paths[:12])}")
            excerpt = self._source_excerpt(source_path)
            if excerpt:
                lines.extend(["", "## Source context", *excerpt])
            lines.extend(["", "## Graph edges"])
            for edge in edge_details[:16]:
                relation = edge.symbol or edge.graph_kind
                lines.append(f"- {edge.source} -> {edge.target} via {relation} ({edge.graph_kind})")
            record = build_document_record(
                virtual_path=source_path,
                source_type=classify_source_type(source_path),
                content=markdown_from_lines(*lines),
                metadata=None,
            )
            if record is not None:
                documents.append(record)
        return documents

    def _source_excerpt(self, source_path: str) -> list[str]:
        path = self.repo_root / source_path
        if not path.exists() or not path.is_file():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        excerpt = [line.rstrip() for line in lines if line.strip()][:12]
        if not excerpt:
            return []
        return excerpt
