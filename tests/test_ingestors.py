from __future__ import annotations

import json
from pathlib import Path

from evidence_gate.config import Settings
from evidence_gate.ingest.local_repo import LocalRepoIngestor
from evidence_gate.ingest.markdown_incident import MarkdownIncidentIngestor
from evidence_gate.retrieval.structural import build_knowledge_base_from_ingestors


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_local_repo_ingestor_collects_repository_documents(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / "docs" / "auth.md", "# Auth\n\nAuth rollback details.\n")
    _write(repo_root / "src" / "auth.py", "def refresh_token():\n    return 'ok'\n")

    documents = LocalRepoIngestor(repo_root).collect_documents()

    assert len(documents) == 2
    assert any(document.path == "docs/auth.md" for document in documents)
    assert any(document.path == "src/auth.py" for document in documents)


def test_markdown_incident_ingestor_maps_json_exports_to_incident_documents(tmp_path: Path) -> None:
    incident_root = tmp_path / "incidents"
    incident_root.mkdir(parents=True)
    payload = {
        "title": "Session rollback required",
        "description": "Token refresh failures required a rollback.",
        "author": "incident-bot",
        "url": "https://example.com/incidents/1842",
        "created_at": "2026-03-10T12:00:00+00:00",
    }
    (incident_root / "incident_1842.json").write_text(json.dumps(payload), encoding="utf-8")

    documents = MarkdownIncidentIngestor(incident_root).collect_documents()

    assert len(documents) == 1
    assert documents[0].source_type.value == "incident"
    assert documents[0].metadata is not None
    assert documents[0].metadata.author == "incident-bot"
    assert documents[0].metadata.external_url == "https://example.com/incidents/1842"


def test_hybrid_ingestors_build_knowledge_base_with_external_incident_support(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    incident_root = tmp_path / "incidents"
    _write(repo_root / "docs" / "auth.md", "# Auth\n\nToken refresh and rollback flows.\n")
    _write(repo_root / "src" / "session.py", "def session_guard():\n    return 'ok'\n")
    incident_root.mkdir(parents=True)
    (incident_root / "incident_1842.md").write_text(
        "# Incident 1842\n\nSession rollback was required after auth cache issues.\n",
        encoding="utf-8",
    )

    knowledge_base = build_knowledge_base_from_ingestors(
        [LocalRepoIngestor(repo_root), MarkdownIncidentIngestor(incident_root)],
        Settings(),
    )
    matches = knowledge_base.truth_pack.structural_search(
        "Which auth incident required session rollback?",
        top_k=5,
    )

    assert any(match.span.source.startswith("external_incidents/") for match in matches)
