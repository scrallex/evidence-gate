from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import evidence_gate.retrieval.structural as structural
from evidence_gate.config import KnowledgeBaseMaintenanceConfig, Settings
from evidence_gate.retrieval.structural import (
    INCIDENT_SOURCE_KIND,
    KnowledgeBaseSourceSpec,
    apply_repository_knowledge_base_retention,
    clear_repository_knowledge_base_cache,
    delete_repository_knowledge_base,
    get_repository_knowledge_base_status,
    list_repository_knowledge_bases,
    materialize_repository_knowledge_base,
    prune_repository_knowledge_bases,
    search_repository,
)


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


def test_repository_kb_cache_persists_and_reuses_artifacts(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "sample_repo"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")

    clear_repository_knowledge_base_cache()
    first_hits = search_repository(
        repo_root,
        query="If we change auth or session handling, what is impacted?",
        top_k=5,
        settings=settings,
    )

    manifests = list(kb_root.rglob("manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["document_count"] >= 5
    assert manifest["span_count"] >= manifest["document_count"]

    clear_repository_knowledge_base_cache()

    def _fail_scan(*args, **kwargs):
        raise AssertionError("scan_repository should not be called on a warm knowledge-base cache")

    monkeypatch.setattr(structural, "scan_repository", _fail_scan)

    second_hits = search_repository(
        repo_root,
        query="If we change auth or session handling, what is impacted?",
        top_k=5,
        settings=settings,
    )

    assert [hit.path for hit in second_hits] == [hit.path for hit in first_hits]
    assert [hit.verified for hit in second_hits] == [hit.verified for hit in first_hits]


def test_repository_kb_cache_excludes_generated_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    audit_root = repo_root / "var" / "audit"
    kb_root = repo_root / "var" / "knowledge_bases"
    _build_sample_repo(repo_root)
    _write(
        audit_root / "decisions" / "fake.json",
        '{"note": "token refresh rollback audit sentinel leaked from generated artifacts"}',
    )

    settings = Settings(knowledge_root=kb_root, audit_root=audit_root)
    clear_repository_knowledge_base_cache()
    hits = search_repository(
        repo_root,
        query="token refresh rollback audit sentinel",
        top_k=5,
        settings=settings,
    )

    assert hits
    assert not any(hit.path.startswith("var/") for hit in hits)
    assert any(kb_root.rglob("manifest.json"))


def test_repository_kb_materialize_force_refresh_rebuilds(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "sample_repo"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")
    real_build_ingestors = structural._build_ingestors_for_source_specs

    clear_repository_knowledge_base_cache()
    built = materialize_repository_knowledge_base(repo_root, settings)
    assert built.status == "built"

    clear_repository_knowledge_base_cache()

    def _fail_build(*args, **kwargs):
        raise AssertionError("hybrid ingestors should not be rebuilt when reusing a cached knowledge base")

    monkeypatch.setattr(structural, "_build_ingestors_for_source_specs", _fail_build)
    reused = materialize_repository_knowledge_base(repo_root, settings)
    assert reused.status == "reused"

    build_calls = {"count": 0}

    def _counted_build(*args, **kwargs):
        build_calls["count"] += 1
        return real_build_ingestors(*args, **kwargs)

    monkeypatch.setattr(structural, "_build_ingestors_for_source_specs", _counted_build)
    refreshed = materialize_repository_knowledge_base(repo_root, settings, force_refresh=True)

    assert refreshed.status == "refreshed"
    assert build_calls["count"] == 1


def test_repository_kb_cache_reuses_hybrid_ingests_for_repo_only_searches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "sample_repo"
    incident_root = tmp_path / "external_incidents"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    _write(
        incident_root / "incident_1842.md",
        "# Incident 1842\n\nLegacy sentinel rollback required after the token refresh regression.\n",
    )
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")

    clear_repository_knowledge_base_cache()
    materialize_repository_knowledge_base(
        repo_root,
        settings,
        source_specs=[KnowledgeBaseSourceSpec(kind=INCIDENT_SOURCE_KIND, root=incident_root)],
    )

    clear_repository_knowledge_base_cache()

    def _fail_build(*args, **kwargs):
        raise AssertionError("hybrid ingestors should not be rebuilt when reusing a cached knowledge base")

    monkeypatch.setattr(structural, "_build_ingestors_for_source_specs", _fail_build)

    hits = search_repository(
        repo_root,
        query="legacy sentinel rollback",
        top_k=5,
        settings=settings,
    )

    assert any(hit.path == "external_incidents/incident_1842.md" for hit in hits)


def test_repository_kb_status_tracks_external_source_changes(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    incident_root = tmp_path / "external_incidents"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    _write(
        incident_root / "incident_1842.md",
        "# Incident 1842\n\nLegacy sentinel rollback required after the token refresh regression.\n",
    )
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")

    clear_repository_knowledge_base_cache()
    materialize_repository_knowledge_base(
        repo_root,
        settings,
        source_specs=[KnowledgeBaseSourceSpec(kind=INCIDENT_SOURCE_KIND, root=incident_root)],
    )

    ready = get_repository_knowledge_base_status(repo_root, settings)
    assert ready.status == "ready"

    (incident_root / "incident_1842.md").write_text(
        "# Incident 1842\n\nLegacy sentinel rollback expanded to include cache invalidation.\n",
        encoding="utf-8",
    )

    stale = get_repository_knowledge_base_status(repo_root, settings)
    assert stale.status == "stale"
    assert stale.current_repo_fingerprint != stale.cached_repo_fingerprint


def test_repository_kb_status_and_listing_track_freshness(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")

    clear_repository_knowledge_base_cache()
    missing = get_repository_knowledge_base_status(repo_root, settings)
    assert missing.status == "missing"
    assert missing.current_file_count >= 5

    materialize_repository_knowledge_base(repo_root, settings)

    statuses = list_repository_knowledge_bases(settings)
    assert len(statuses) == 1
    assert statuses[0].repo_root == repo_root.resolve()
    assert statuses[0].status == "ready"

    (repo_root / "docs" / "auth.md").write_text(
        "# Auth\n\nSession handling changes now also impact key rotation and audit flows.\n",
        encoding="utf-8",
    )

    stale = get_repository_knowledge_base_status(repo_root, settings)
    assert stale.status == "stale"
    assert stale.current_repo_fingerprint != stale.cached_repo_fingerprint


def test_repository_kb_delete_removes_cache_for_missing_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    kb_root = tmp_path / "knowledge_bases"
    _build_sample_repo(repo_root)
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")

    clear_repository_knowledge_base_cache()
    built = materialize_repository_knowledge_base(repo_root, settings)
    assert built.cache_dir.exists()

    shutil.rmtree(repo_root)

    removal = delete_repository_knowledge_base(repo_root, settings)
    assert removal.action == "deleted"
    assert removal.previous_status == "stale"
    assert not built.cache_dir.exists()


def test_repository_kb_prune_stale_only_supports_dry_run(tmp_path: Path) -> None:
    ready_repo = tmp_path / "ready_repo"
    stale_repo = tmp_path / "stale_repo"
    kb_root = tmp_path / "knowledge_bases"
    settings = Settings(knowledge_root=kb_root, audit_root=tmp_path / "audit")

    _build_sample_repo(ready_repo)
    _build_sample_repo(stale_repo)

    clear_repository_knowledge_base_cache()
    ready_materialization = materialize_repository_knowledge_base(ready_repo, settings)
    stale_materialization = materialize_repository_knowledge_base(stale_repo, settings)

    (stale_repo / "docs" / "auth.md").write_text(
        "# Auth\n\nStale cache signal for prune testing.\n",
        encoding="utf-8",
    )

    dry_run = prune_repository_knowledge_bases(settings, stale_only=True, dry_run=True)
    assert len(dry_run) == 1
    assert dry_run[0].action == "would_delete"
    assert dry_run[0].previous_status == "stale"
    assert ready_materialization.cache_dir.exists()
    assert stale_materialization.cache_dir.exists()

    removed = prune_repository_knowledge_bases(settings, stale_only=True, dry_run=False)
    assert len(removed) == 1
    assert removed[0].action == "deleted"
    assert removed[0].previous_status == "stale"
    assert ready_materialization.cache_dir.exists()
    assert not stale_materialization.cache_dir.exists()


def test_repository_kb_retention_removes_overflow_oldest_first(tmp_path: Path) -> None:
    older_repo = tmp_path / "older_repo"
    newer_repo = tmp_path / "newer_repo"
    kb_root = tmp_path / "knowledge_bases"
    settings = Settings(
        knowledge_root=kb_root,
        audit_root=tmp_path / "audit",
        maintenance=KnowledgeBaseMaintenanceConfig(
            enabled=True,
            prune_on_startup=False,
            max_age_hours=None,
            max_cache_entries=1,
        ),
    )

    _build_sample_repo(older_repo)
    _build_sample_repo(newer_repo)

    clear_repository_knowledge_base_cache()
    older_materialization = materialize_repository_knowledge_base(older_repo, settings)
    time.sleep(0.01)
    newer_materialization = materialize_repository_knowledge_base(newer_repo, settings)

    dry_run = apply_repository_knowledge_base_retention(settings, dry_run=True)
    assert dry_run.total_knowledge_bases == 2
    assert len(dry_run.removals) == 1
    assert dry_run.removals[0].action == "would_delete"
    assert dry_run.removals[0].reason == "overflow"
    assert dry_run.removals[0].repo_root == older_repo.resolve()
    assert older_materialization.cache_dir.exists()
    assert newer_materialization.cache_dir.exists()

    executed = apply_repository_knowledge_base_retention(settings, dry_run=False)
    assert len(executed.removals) == 1
    assert executed.removals[0].action == "deleted"
    assert executed.removals[0].reason == "overflow"
    assert not older_materialization.cache_dir.exists()
    assert newer_materialization.cache_dir.exists()
