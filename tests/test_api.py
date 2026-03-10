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


def _build_billing_repo(root: Path) -> None:
    _write(
        root / "services" / "billing.py",
        "from services.gateway import authorize_charge\n\n"
        "def submit_invoice(amount: int) -> str:\n"
        "    return authorize_charge(amount)\n",
    )
    _write(
        root / "services" / "gateway.py",
        "def authorize_charge(amount: int) -> str:\n"
        "    return 'ok'\n",
    )
    _write(
        root / "services" / "email.py",
        "def send_receipt(invoice_id: str) -> str:\n"
        "    return invoice_id\n",
    )
    _write(
        root / "tests" / "test_billing.py",
        "from services.billing import submit_invoice\n\n"
        "def test_submit_invoice() -> None:\n"
        "    assert submit_invoice(100) == 'ok'\n",
    )
    _write(
        root / "docs" / "billing.md",
        "# Billing\n\nBilling changes affect duplicate-charge safeguards, refunds, and rollback flows.\n",
    )
    _write(
        root / "runbooks" / "billing_rollback.md",
        "# Billing rollback\n\nDisable retries and run the billing rollback when duplicate-charge guards fail.\n",
    )
    _write(
        root / "prs" / "pr_2201.md",
        "# PR 2201\n\nHardened billing duplicate-charge safeguards during a prior rollout.\n",
    )


def _build_open_source_repo(root: Path) -> None:
    _write(
        root / "lib" / "cache.js",
        "export function loadCache(key) {\n"
        "  return `value:${key}`;\n"
        "}\n",
    )
    _write(
        root / "tests" / "cache.test.js",
        "import {loadCache} from '../lib/cache.js';\n\n"
        "test('loadCache returns the keyed value', () => {\n"
        "  expect(loadCache('abc')).toBe('value:abc');\n"
        "});\n",
    )
    _write(
        root / "docs" / "cache.md",
        "# Cache\n\nCache changes require matching test updates in the open-source workflow.\n",
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


def test_action_decision_endpoint_returns_200_for_allowed_and_403_for_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
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

    allowed = client.post(
        "/v1/decide/action",
        json={
            "repo_path": str(repo_root),
            "action_summary": "Before changing auth/session handling, verify the action is safe.",
            "changed_paths": ["src/session.py"],
        },
    )
    assert allowed.status_code == 200
    allowed_payload = allowed.json()
    assert allowed_payload["allowed"] is True
    assert allowed_payload["status"] == "allow"
    assert allowed_payload["decision_record"]["decision"] == "admit"

    blocked = client.post(
        "/v1/decide/action",
        json={
            "repo_path": str(repo_root),
            "action_summary": "Before changing auth/session handling, verify the action is safe.",
            "changed_paths": ["src/session.py"],
            "block_on": ["admit"],
        },
    )
    assert blocked.status_code == 403
    blocked_payload = blocked.json()
    assert blocked_payload["allowed"] is False
    assert blocked_payload["status"] == "block"
    assert blocked_payload["decision_record"]["decision"] == "admit"
    assert blocked_payload["failure_reason"]


def test_action_decision_endpoint_open_source_policy_ignores_enterprise_only_gaps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "oss_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_open_source_repo(repo_root)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    blocked = client.post(
        "/v1/decide/action",
        json={
            "repo_path": str(repo_root),
            "action_summary": "Review the cache behavior change before merge.",
            "changed_paths": ["lib/cache.js"],
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["decision_record"]["decision"] == "escalate"

    allowed = client.post(
        "/v1/decide/action",
        json={
            "repo_path": str(repo_root),
            "action_summary": "Review the cache behavior change before merge.",
            "changed_paths": ["lib/cache.js"],
            "safety_policy": {
                "corpus_profile": "open_source",
                "require_test_evidence": True,
            },
        },
    )
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["allowed"] is True
    assert payload["decision_record"]["decision"] == "admit"
    assert "No runbook or operational handling evidence was found." not in payload["decision_record"]["missing_evidence"]
    assert "No prior PR or incident precedent was found." not in payload["decision_record"]["missing_evidence"]


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


def test_knowledge_base_ingest_endpoint_supports_external_incident_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "sample_repo"
    incident_root = tmp_path / "external_incidents"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _write(repo_root / "src" / "auth.py", "def refresh_token():\n    return 'ok'\n")
    _write(repo_root / "docs" / "auth.md", "# Auth\n\nToken refresh details.\n")
    _write(
        incident_root / "incident_1842.md",
        "# Incident 1842\n\nLegacy sentinel rollback required after the token refresh regression.\n",
    )

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    built = client.post(
        "/v1/knowledge-bases/ingest",
        json={
            "repo_path": str(repo_root),
            "external_sources": [
                {
                    "type": "incidents",
                    "path": str(incident_root),
                }
            ],
        },
    )
    assert built.status_code == 200

    decision = client.post(
        "/v1/decide/query",
        json={
            "repo_path": str(repo_root),
            "query": "Which incident mentioned legacy sentinel rollback?",
        },
    )
    assert decision.status_code == 200
    payload = decision.json()
    assert any(twin["source"] == "external_incidents/incident_1842.md" for twin in payload["twin_cases"])


def test_action_decision_endpoint_enforces_safety_policy_with_external_connector_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "billing_repo"
    pagerduty_root = tmp_path / "pagerduty"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_billing_repo(repo_root)
    _write(
        pagerduty_root / "incidents.json",
        (
            '[{"incident_number": 4417, "title": "Billing duplicate-charge incident", '
            '"description": "Duplicate-charge safeguards failed after a billing authorization change.", '
            '"status": "resolved", "service": {"summary": "billing"}, '
            '"html_url": "https://pagerduty.example.com/incidents/4417", '
            '"created_at": "2026-03-10T12:00:00+00:00"}]'
        ),
    )

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    built = client.post(
        "/v1/knowledge-bases/ingest",
        json={
            "repo_path": str(repo_root),
            "external_sources": [
                {
                    "type": "pagerduty",
                    "path": str(pagerduty_root),
                }
            ],
        },
    )
    assert built.status_code == 200

    blocked = client.post(
        "/v1/decide/action",
        json={
            "repo_path": str(repo_root),
            "action_summary": "Review the billing service PR before merge.",
            "changed_paths": ["services/billing.py"],
            "diff_summary": "Removed duplicate-charge safeguards from the billing authorization flow.",
            "top_k": 10,
            "safety_policy": {
                "require_test_evidence": True,
                "require_precedent": True,
                "require_incident_precedent": True,
                "escalate_on_incident_match": True,
            },
        },
    )
    assert blocked.status_code == 403
    payload = blocked.json()
    assert payload["allowed"] is False
    assert payload["status"] == "block"
    assert payload["decision_record"]["decision"] == "escalate"
    assert payload["failure_reason"].startswith(
        "Action blocked because Evidence Gate safety thresholds were violated:"
    )
    assert payload["policy_violations"] == [
        "Policy blocks changes that match prior incident precedent."
    ]
    assert any(
        twin["source"].startswith("external_pagerduty/")
        for twin in payload["decision_record"]["twin_cases"]
    )
    assert payload["decision_record"]["request_payload"]["diff_summary"] == (
        "Removed duplicate-charge safeguards from the billing authorization flow."
    )


def test_action_decision_endpoint_escalates_when_changed_paths_do_not_match_retrieved_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "billing_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_billing_repo(repo_root)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    response = client.post(
        "/v1/decide/action",
        json={
            "repo_path": str(repo_root),
            "action_summary": "Review the billing service PR before merge.",
            "changed_paths": ["services/email.py"],
            "diff_summary": "Removed duplicate-charge safeguards from the billing authorization flow.",
            "top_k": 10,
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["decision_record"]["decision"] == "escalate"
    assert any(
        "proposed changed paths were not directly supported" in item.lower()
        for item in payload["decision_record"]["missing_evidence"]
    )


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


def test_knowledge_base_delete_and_prune_endpoints(tmp_path: Path, monkeypatch) -> None:
    ready_repo = tmp_path / "ready_repo"
    stale_repo = tmp_path / "stale_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(ready_repo)
    _build_sample_repo(stale_repo)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    ready_built = client.post("/v1/knowledge-bases/ingest", json={"repo_path": str(ready_repo)})
    stale_built = client.post("/v1/knowledge-bases/ingest", json={"repo_path": str(stale_repo)})
    assert ready_built.status_code == 200
    assert stale_built.status_code == 200

    (stale_repo / "docs" / "auth.md").write_text(
        "# Auth\n\nThis repo is intentionally stale for prune endpoint coverage.\n",
        encoding="utf-8",
    )

    dry_run = client.post(
        "/v1/knowledge-bases/prune",
        json={"stale_only": True, "dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_run_payload = dry_run.json()
    assert dry_run_payload["removed_count"] == 1
    assert dry_run_payload["results"][0]["action"] == "would_delete"
    assert Path(dry_run_payload["results"][0]["knowledge_base_path"]).exists()

    pruned = client.post(
        "/v1/knowledge-bases/prune",
        json={"stale_only": True, "dry_run": False},
    )
    assert pruned.status_code == 200
    pruned_payload = pruned.json()
    assert pruned_payload["removed_count"] == 1
    assert pruned_payload["results"][0]["action"] == "deleted"
    assert not Path(pruned_payload["results"][0]["knowledge_base_path"]).exists()

    delete_ready = client.delete("/v1/knowledge-bases", params={"repo_path": str(ready_repo)})
    assert delete_ready.status_code == 200
    delete_ready_payload = delete_ready.json()
    assert delete_ready_payload["action"] == "deleted"
    assert delete_ready_payload["previous_status"] == "ready"
    assert not Path(delete_ready_payload["knowledge_base_path"]).exists()

    delete_missing = client.delete("/v1/knowledge-bases", params={"repo_path": str(ready_repo)})
    assert delete_missing.status_code == 200
    assert delete_missing.json()["action"] == "missing"


def test_knowledge_base_maintenance_run_and_status_endpoints(tmp_path: Path, monkeypatch) -> None:
    older_repo = tmp_path / "older_repo"
    newer_repo = tmp_path / "newer_repo"
    audit_root = tmp_path / "audit"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(older_repo)
    _build_sample_repo(newer_repo)

    monkeypatch.setenv("EVIDENCE_GATE_AUDIT_ROOT", str(audit_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_ROOT", str(kb_root))
    monkeypatch.setenv("EVIDENCE_GATE_KB_PRUNE_ON_STARTUP", "false")
    monkeypatch.setenv("EVIDENCE_GATE_KB_MAX_CACHE_ENTRIES", "1")
    get_settings.cache_clear()
    get_audit_store.cache_clear()
    get_decision_service.cache_clear()

    client = TestClient(create_app())

    status_before = client.get("/v1/knowledge-bases/maintenance/status")
    assert status_before.status_code == 200
    status_before_payload = status_before.json()
    assert status_before_payload["prune_on_startup"] is False
    assert status_before_payload["max_cache_entries"] == 1
    assert status_before_payload["last_run"] is None

    built_older = client.post("/v1/knowledge-bases/ingest", json={"repo_path": str(older_repo)})
    built_newer = client.post("/v1/knowledge-bases/ingest", json={"repo_path": str(newer_repo)})
    assert built_older.status_code == 200
    assert built_newer.status_code == 200

    dry_run = client.post(
        "/v1/knowledge-bases/maintenance/run",
        json={"dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_run_payload = dry_run.json()
    assert dry_run_payload["removed_count"] == 1
    assert dry_run_payload["overflow_count"] == 1
    assert dry_run_payload["results"][0]["action"] == "would_delete"
    assert dry_run_payload["results"][0]["reason"] == "overflow"

    executed = client.post(
        "/v1/knowledge-bases/maintenance/run",
        json={"dry_run": False},
    )
    assert executed.status_code == 200
    executed_payload = executed.json()
    assert executed_payload["removed_count"] == 1
    assert executed_payload["results"][0]["action"] == "deleted"
    assert executed_payload["results"][0]["reason"] == "overflow"

    status_after = client.get("/v1/knowledge-bases/maintenance/status")
    assert status_after.status_code == 200
    status_after_payload = status_after.json()
    assert status_after_payload["last_run"]["removed_count"] == 1
    assert status_after_payload["last_run"]["overflow_count"] == 1
