from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from evidence_gate.api.main import create_app, get_audit_store, get_decision_service
from evidence_gate.config import get_settings


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_sample_repo(root: Path) -> None:
    _write(
        root / "src" / "session.py",
        "from src.auth import refresh_token\n\n"
        "def session_guard():\n"
        "    return refresh_token()\n",
    )
    _write(
        root / "src" / "auth.py",
        "def refresh_token():\n"
        "    return 'ok'\n",
    )
    _write(
        root / "tests" / "test_auth.py",
        "from src.session import session_guard\n\n"
        "def test_session_guard():\n"
        "    assert session_guard() == 'ok'\n",
    )
    _write(
        root / "docs" / "auth.md",
        "# Auth\n\nChanging auth or session handling impacts token refresh and rollback flows.\n",
    )
    _write(
        root / "runbooks" / "session_rollback.md",
        "# Session Rollback\n\nIf token refresh fails, use the session rollback procedure.\n",
    )
    _write(
        root / "prs" / "pr_1842.md",
        "# PR 1842\n\nAdjusted token refresh behavior during the auth session rollout.\n",
    )
    _write(
        root / "incidents" / "incident_2025_09_17.md",
        "# Incident\n\nSession refresh failures required rollback and auth cache cleanup.\n",
    )


def test_health_endpoint() -> None:
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_change_impact_decision_flow(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "sample_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())
    response = client.post(
        "/v1/decide/change-impact",
        json={
            "repo_path": str(repo_root),
            "change_summary": "If we change auth or session handling, what is impacted?",
            "changed_paths": ["src/session.py"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "admit"
    assert payload["blast_radius"]["files"] >= 2
    assert payload["blast_radius"]["tests"] >= 1
    assert any(span["source"] == "docs/auth.md" for span in payload["evidence_spans"])
    assert any(span["verified"] for span in payload["evidence_spans"])
    assert any(twin["source"] == "prs/pr_1842.md" for twin in payload["twin_cases"])

    decision_id = payload["decision_id"]
    stored = client.get(f"/v1/decisions/{decision_id}")
    assert stored.status_code == 200
    assert stored.json()["decision_id"] == decision_id
    assert (audit_root / "decisions" / f"{decision_id}.json").exists()
    assert any(kb_root.rglob("manifest.json"))


def test_knowledge_base_ingest_endpoint_builds_reuses_and_refreshes(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "sample_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    built = client.post(
        "/v1/knowledge-bases/ingest",
        json={"repo_path": str(repo_root)},
    )
    assert built.status_code == 200
    built_payload = built.json()
    assert built_payload["status"] == "built"
    assert built_payload["document_count"] >= 5
    assert built_payload["span_count"] >= built_payload["document_count"]
    assert Path(built_payload["knowledge_base_path"]).exists()

    reused = client.post(
        "/v1/knowledge-bases/ingest",
        json={"repo_path": str(repo_root)},
    )
    assert reused.status_code == 200
    reused_payload = reused.json()
    assert reused_payload["status"] == "reused"
    assert reused_payload["repo_fingerprint"] == built_payload["repo_fingerprint"]

    refreshed = client.post(
        "/v1/knowledge-bases/ingest",
        json={"repo_path": str(repo_root), "refresh": True},
    )
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()
    assert refreshed_payload["status"] == "refreshed"
    assert refreshed_payload["repo_fingerprint"] == built_payload["repo_fingerprint"]


def test_knowledge_base_status_and_listing_endpoints(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "sample_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    missing = client.get("/v1/knowledge-bases/status", params={"repo_path": str(repo_root)})
    assert missing.status_code == 200
    missing_payload = missing.json()
    assert missing_payload["status"] == "missing"
    assert missing_payload["current_file_count"] >= 5

    built = client.post(
        "/v1/knowledge-bases/ingest",
        json={"repo_path": str(repo_root)},
    )
    assert built.status_code == 200

    listed = client.get("/v1/knowledge-bases")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert len(listed_payload["knowledge_bases"]) == 1
    assert listed_payload["knowledge_bases"][0]["repo_path"] == str(repo_root.resolve())
    assert listed_payload["knowledge_bases"][0]["status"] == "ready"

    ready = client.get("/v1/knowledge-bases/status", params={"repo_path": str(repo_root)})
    assert ready.status_code == 200
    ready_payload = ready.json()
    assert ready_payload["status"] == "ready"
    assert ready_payload["settings_match"] is True
    assert ready_payload["cached_repo_fingerprint"] == ready_payload["current_repo_fingerprint"]

    (repo_root / "docs" / "auth.md").write_text(
        "# Auth\n\nChanging auth, session handling, and key rotation impacts rollback flows.\n",
        encoding="utf-8",
    )

    stale = client.get("/v1/knowledge-bases/status", params={"repo_path": str(repo_root)})
    assert stale.status_code == 200
    stale_payload = stale.json()
    assert stale_payload["status"] == "stale"
    assert stale_payload["cached_repo_fingerprint"] != stale_payload["current_repo_fingerprint"]
