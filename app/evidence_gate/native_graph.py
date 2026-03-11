"""Native LSIF and SCIP graph loading for blast radius and retrieval."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse


GRAPH_ROOT = ".evidence-gate/graphs"
GRAPH_RELATIVE_PREFIXES = (GRAPH_ROOT,)
_RESULT_EDGE_LABELS = frozenset(
    {
        "textDocument/declaration",
        "textDocument/definition",
        "textDocument/implementation",
        "textDocument/references",
        "textDocument/typeDefinition",
    }
)
_GRAPH_SUFFIXES = (
    ".json",
    ".lsif",
    ".ndjson",
)


@dataclass(frozen=True, slots=True)
class NativeGraphEdge:
    source: str
    target: str
    symbol: str | None
    graph_kind: str
    export_path: str


@dataclass(slots=True)
class NativeRepoGraph:
    """Repository-native file reference graph derived from LSIF or SCIP exports."""

    edges: list[NativeGraphEdge] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    edges_by_source: dict[str, set[str]] = field(default_factory=dict)
    incoming_by_target: dict[str, set[str]] = field(default_factory=dict)
    symbols_by_source: dict[str, set[str]] = field(default_factory=dict)
    edge_details_by_source: dict[str, list[NativeGraphEdge]] = field(default_factory=dict)

    def add_symbol(self, source_path: str, symbol: str | None) -> None:
        if not source_path or not symbol:
            return
        normalized = symbol.strip()
        if not normalized:
            return
        self.symbols_by_source.setdefault(source_path, set()).add(normalized)

    def add_edge(self, edge: NativeGraphEdge) -> None:
        if not edge.source or not edge.target:
            return
        if edge.source == edge.target:
            self.add_symbol(edge.source, edge.symbol)
            return
        existing_targets = self.edges_by_source.setdefault(edge.source, set())
        if edge.target in existing_targets and edge.symbol is None:
            return
        existing_targets.add(edge.target)
        self.incoming_by_target.setdefault(edge.target, set()).add(edge.source)
        self.edge_details_by_source.setdefault(edge.source, []).append(edge)
        self.add_symbol(edge.source, edge.symbol)
        self.edges.append(edge)

    def merge(self, other: "NativeRepoGraph") -> None:
        for export_path in other.exports:
            if export_path not in self.exports:
                self.exports.append(export_path)
        for edge in other.edges:
            self.add_edge(edge)

    def has_edges(self) -> bool:
        return bool(self.edges)

    def paths(self) -> set[str]:
        return {
            *self.edges_by_source.keys(),
            *self.incoming_by_target.keys(),
            *self.symbols_by_source.keys(),
        }


def native_graph_relative_prefixes() -> tuple[str, ...]:
    """Return repo-relative prefixes reserved for graph sidecars."""

    return GRAPH_RELATIVE_PREFIXES


def load_repository_native_graph(repo_root: Path) -> NativeRepoGraph:
    """Load LSIF or SCIP graph sidecars from the dedicated graph directory."""

    repo_root = Path(repo_root).resolve()
    graph_root = repo_root / GRAPH_ROOT
    graph = NativeRepoGraph()
    if not graph_root.exists() or not graph_root.is_dir():
        return graph

    for path in sorted(candidate for candidate in graph_root.rglob("*") if candidate.is_file()):
        if not _is_supported_graph_export(path):
            continue
        parsed = _load_graph_export(repo_root, path)
        if parsed is not None:
            graph.merge(parsed)
    return graph


def _is_supported_graph_export(path: Path) -> bool:
    lower = path.name.lower()
    return lower.endswith(_GRAPH_SUFFIXES) or ".lsif." in lower or ".scip." in lower


def _load_graph_export(repo_root: Path, path: Path) -> NativeRepoGraph | None:
    try:
        if _looks_like_lsif(path):
            entries = _read_json_stream(path)
            return _parse_lsif_graph(repo_root, path, entries)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None

    if _looks_like_scip_payload(payload):
        return _parse_scip_graph(repo_root, path, payload)
    return None


def _looks_like_lsif(path: Path) -> bool:
    lower = path.name.lower()
    return ".lsif" in lower or lower.endswith(".ndjson")


def _looks_like_scip_payload(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("documents"), list)
        and any(
            isinstance(item, dict) and any(key in item for key in ("relative_path", "path", "uri"))
            for item in payload.get("documents", [])
        )
    )


def _read_json_stream(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] == "[":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("Expected LSIF array payload.")
        return [item for item in payload if isinstance(item, dict)]

    entries: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            entries.append(item)
    return entries


def _parse_lsif_graph(
    repo_root: Path,
    path: Path,
    entries: list[dict[str, object]],
) -> NativeRepoGraph:
    graph = NativeRepoGraph(exports=[path.relative_to(repo_root).as_posix()])
    documents: dict[str, str] = {}
    range_labels: dict[str, str] = {}
    range_to_doc: dict[str, str] = {}
    next_edges: dict[str, str] = {}
    result_edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
    items: dict[str, list[str]] = defaultdict(list)

    for entry in entries:
        entry_type = str(entry.get("type", "")).lower()
        label = str(entry.get("label", ""))
        entry_id = _graph_id(entry.get("id"))
        if entry_type == "vertex" and label == "document" and entry_id is not None:
            document_path = _normalize_graph_path(repo_root, entry.get("uri"))
            if document_path is not None:
                documents[entry_id] = document_path
            continue
        if entry_type == "vertex" and label == "range" and entry_id is not None:
            range_labels[entry_id] = _lsif_symbol_label(entry)
            continue
        if entry_type != "edge":
            continue
        out_v = _graph_id(entry.get("outV"))
        in_v = _graph_id(entry.get("inV"))
        if label == "contains" and out_v is not None:
            document_path = documents.get(out_v)
            if document_path is None:
                continue
            for target_id in _graph_edge_targets(entry):
                range_to_doc[target_id] = document_path
            continue
        if label == "next" and out_v is not None and in_v is not None:
            next_edges[out_v] = in_v
            continue
        if label in _RESULT_EDGE_LABELS and out_v is not None and in_v is not None:
            result_edges[out_v].append((label, in_v))
            continue
        if label == "item" and out_v is not None:
            items[out_v].extend(_graph_edge_targets(entry))

    for range_id, source_path in range_to_doc.items():
        graph.add_symbol(source_path, range_labels.get(range_id))
        owner_id = _resolve_next_chain(range_id, next_edges)
        candidate_results = [*result_edges.get(range_id, ()), *result_edges.get(owner_id, ())]
        for label, result_id in candidate_results:
            for target_range_id in items.get(result_id, ()):
                target_path = range_to_doc.get(target_range_id)
                if target_path is None:
                    continue
                graph.add_symbol(target_path, range_labels.get(target_range_id))
                graph.add_edge(
                    NativeGraphEdge(
                        source=source_path,
                        target=target_path,
                        symbol=range_labels.get(range_id) or range_labels.get(target_range_id),
                        graph_kind=f"lsif:{label}",
                        export_path=path.relative_to(repo_root).as_posix(),
                    )
                )

    return graph


def _parse_scip_graph(
    repo_root: Path,
    path: Path,
    payload: dict[str, object],
) -> NativeRepoGraph:
    graph = NativeRepoGraph(exports=[path.relative_to(repo_root).as_posix()])
    symbol_paths: dict[str, set[str]] = defaultdict(set)
    symbol_labels: dict[str, str] = {}
    relationships: list[tuple[str, str, dict[str, object]]] = []

    for document in payload.get("documents", []):
        if not isinstance(document, dict):
            continue
        source_path = _normalize_graph_path(
            repo_root,
            document.get("relative_path") or document.get("path") or document.get("uri"),
        )
        if source_path is None:
            continue
        for occurrence in document.get("occurrences", []):
            if not isinstance(occurrence, dict):
                continue
            symbol = occurrence.get("symbol")
            if not isinstance(symbol, str) or not symbol.strip():
                continue
            symbol_paths[symbol].add(source_path)
            label = _scip_symbol_label(symbol)
            symbol_labels.setdefault(symbol, label)
            graph.add_symbol(source_path, label)
        for symbol_payload in document.get("symbols", []):
            if not isinstance(symbol_payload, dict):
                continue
            source_symbol = symbol_payload.get("symbol")
            if not isinstance(source_symbol, str) or not source_symbol.strip():
                continue
            label = _scip_symbol_label(source_symbol)
            symbol_labels.setdefault(source_symbol, label)
            graph.add_symbol(source_path, label)
            for relationship in symbol_payload.get("relationships", []):
                if isinstance(relationship, dict):
                    relationships.append((source_path, source_symbol, relationship))

    for source_path, source_symbol, relationship in relationships:
        target_symbol = relationship.get("symbol")
        if not isinstance(target_symbol, str) or not target_symbol.strip():
            continue
        target_paths = symbol_paths.get(target_symbol)
        if not target_paths:
            continue
        relation_kind = _scip_relationship_kind(relationship)
        symbol = symbol_labels.get(target_symbol) or symbol_labels.get(source_symbol)
        for target_path in target_paths:
            graph.add_symbol(target_path, symbol_labels.get(target_symbol))
            graph.add_edge(
                NativeGraphEdge(
                    source=source_path,
                    target=target_path,
                    symbol=symbol,
                    graph_kind=f"scip:{relation_kind}",
                    export_path=path.relative_to(repo_root).as_posix(),
                )
            )

    return graph


def _graph_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _graph_edge_targets(payload: dict[str, object]) -> list[str]:
    targets: list[str] = []
    in_v = _graph_id(payload.get("inV"))
    if in_v is not None:
        targets.append(in_v)
    for item in payload.get("inVs", []):
        target = _graph_id(item)
        if target is not None:
            targets.append(target)
    return targets


def _resolve_next_chain(start_id: str, next_edges: dict[str, str]) -> str:
    current = start_id
    seen = {start_id}
    while current in next_edges and next_edges[current] not in seen:
        current = next_edges[current]
        seen.add(current)
    return current


def _lsif_symbol_label(payload: dict[str, object]) -> str:
    tag = payload.get("tag")
    if isinstance(tag, dict):
        for key in ("text", "symbol", "detail"):
            value = tag.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        kind = tag.get("type")
        if isinstance(kind, str) and kind.strip():
            return kind.strip()
    return "graph reference"


def _scip_relationship_kind(payload: dict[str, object]) -> str:
    for key in (
        "is_reference",
        "is_implementation",
        "is_type_definition",
        "is_definition",
    ):
        if payload.get(key):
            return key.removeprefix("is_").replace("_", "-")
    return "relationship"


def _scip_symbol_label(symbol: str) -> str:
    text = symbol.strip()
    if not text:
        return "graph symbol"
    if " " in text:
        text = text.rsplit(" ", maxsplit=1)[-1]
    if "/" in text:
        text = text.rsplit("/", maxsplit=1)[-1]
    text = text.strip("`#().;:,")
    return text or "graph symbol"


def _normalize_graph_path(repo_root: Path, value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    if raw.startswith("file://"):
        parsed = urlparse(raw)
        candidate = Path(unquote(parsed.path))
    else:
        candidate = Path(raw)

    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            return None

    normalized = candidate.as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or None


__all__ = [
    "GRAPH_RELATIVE_PREFIXES",
    "GRAPH_ROOT",
    "NativeGraphEdge",
    "NativeRepoGraph",
    "load_repository_native_graph",
    "native_graph_relative_prefixes",
]
