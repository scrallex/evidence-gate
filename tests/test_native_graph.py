from __future__ import annotations

import json
from pathlib import Path

from evidence_gate.blast_radius.ast_deps import ASTDependencyAnalyzer
from evidence_gate.config import Settings
from evidence_gate.ingest.native_graph import NativeGraphIngestor
from evidence_gate.native_graph import load_repository_native_graph
from evidence_gate.retrieval.structural import search_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_dynamic_ts_repo(root: Path) -> None:
    _write(
        root / "src" / "entry.ts",
        "export async function loadFeature(kind: string) {\n"
        "  const loader = registry[kind];\n"
        "  return loader();\n"
        "}\n"
        "const registry: Record<string, () => Promise<unknown>> = {\n"
        "  foo: () => import(modulePath),\n"
        "};\n"
        "const modulePath = './features/runtime-target';\n",
    )
    _write(
        root / "src" / "features" / "runtime-target.ts",
        "export function fooFeature() {\n"
        "  return 'ok';\n"
        "}\n",
    )
    _write(
        root / "tests" / "entry.spec.ts",
        "import {loadFeature} from '../src/entry';\n"
        "test('loadFeature', async () => {\n"
        "  await loadFeature('foo');\n"
        "});\n",
    )


def test_ast_dependency_analyzer_uses_lsif_graph_for_dynamic_import_edges(tmp_path: Path) -> None:
    repo_root = tmp_path / "vite_like"
    _build_dynamic_ts_repo(repo_root)
    graph_root = repo_root / ".evidence-gate" / "graphs"
    entries = [
        {"id": 1, "type": "vertex", "label": "document", "uri": "src/entry.ts"},
        {"id": 2, "type": "vertex", "label": "document", "uri": "src/features/runtime-target.ts"},
        {"id": 3, "type": "vertex", "label": "range", "tag": {"text": "fooFeature"}},
        {"id": 4, "type": "vertex", "label": "range", "tag": {"text": "fooFeature"}},
        {"id": 5, "type": "vertex", "label": "resultSet"},
        {"id": 6, "type": "vertex", "label": "referenceResult"},
        {"id": 7, "type": "edge", "label": "contains", "outV": 1, "inVs": [3]},
        {"id": 8, "type": "edge", "label": "contains", "outV": 2, "inVs": [4]},
        {"id": 9, "type": "edge", "label": "next", "outV": 3, "inV": 5},
        {"id": 10, "type": "edge", "label": "textDocument/references", "outV": 5, "inV": 6},
        {"id": 11, "type": "edge", "label": "item", "outV": 6, "inVs": [4], "property": "references"},
    ]
    _write(
        graph_root / "vite.lsif.ndjson",
        "\n".join(json.dumps(entry) for entry in entries) + "\n",
    )

    analyzer = ASTDependencyAnalyzer(repo_root)
    analyzer.build_dependency_graph()

    impacted = analyzer.impacted_files("src/features/runtime-target.ts")

    assert "src/entry.ts" in impacted


def test_native_graph_ingestor_adds_graph_backed_retrieval_support(tmp_path: Path) -> None:
    repo_root = tmp_path / "vite_like"
    _build_dynamic_ts_repo(repo_root)
    graph_root = repo_root / ".evidence-gate" / "graphs"
    scip_payload = {
        "metadata": {"toolInfo": {"name": "scip-typescript"}},
        "documents": [
            {
                "relative_path": "src/entry.ts",
                "occurrences": [{"symbol": "fooFeature"}],
                "symbols": [
                    {
                        "symbol": "entryLoader",
                        "relationships": [
                            {"symbol": "fooFeature", "is_reference": True},
                        ],
                    }
                ],
            },
            {
                "relative_path": "src/features/runtime-target.ts",
                "occurrences": [{"symbol": "fooFeature"}],
                "symbols": [{"symbol": "fooFeature", "relationships": []}],
            },
        ],
    }
    _write(graph_root / "vite.scip.json", json.dumps(scip_payload, indent=2))

    graph = load_repository_native_graph(repo_root)
    assert graph.has_edges()
    assert "src/features/runtime-target.ts" in graph.edges_by_source["src/entry.ts"]

    documents = NativeGraphIngestor(repo_root).collect_documents()
    assert any(document.path == "src/entry.ts" and "fooFeature" in document.content for document in documents)

    hits = search_repository(
        repo_root,
        query="Review the fooFeature dynamic loader before merge.",
        top_k=5,
        settings=Settings(),
    )

    assert hits
    assert hits[0].path == "src/entry.ts"
    assert not any(hit.path.startswith(".evidence-gate/graphs") for hit in hits)


def test_search_repository_uses_native_graph_neighbors_for_changed_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "vite_like"
    _build_dynamic_ts_repo(repo_root)
    graph_root = repo_root / ".evidence-gate" / "graphs"
    scip_payload = {
        "metadata": {"toolInfo": {"name": "scip-typescript"}},
        "documents": [
            {
                "relative_path": "src/entry.ts",
                "occurrences": [{"symbol": "fooFeature"}],
                "symbols": [
                    {
                        "symbol": "entryLoader",
                        "relationships": [
                            {"symbol": "fooFeature", "is_reference": True},
                        ],
                    }
                ],
            },
            {
                "relative_path": "src/features/runtime-target.ts",
                "occurrences": [{"symbol": "fooFeature"}],
                "symbols": [{"symbol": "fooFeature", "relationships": []}],
            },
        ],
    }
    _write(graph_root / "vite.scip.json", json.dumps(scip_payload, indent=2))

    plain_hits = search_repository(
        repo_root,
        query="Review the runtime feature change before merge.",
        top_k=5,
        settings=Settings(),
    )
    boosted_hits = search_repository(
        repo_root,
        query="Review the runtime feature change before merge.",
        top_k=5,
        settings=Settings(),
        changed_paths=["src/features/runtime-target.ts"],
    )

    assert "tests/entry.spec.ts" not in {hit.path for hit in plain_hits[:5]}
    assert "tests/entry.spec.ts" in {hit.path for hit in boosted_hits[:5]}
