from __future__ import annotations

from pathlib import Path

from evidence_gate.config import Settings
from evidence_gate.retrieval.structural import search_repository


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


def test_structural_search_surfaces_verified_and_diverse_hits(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample_repo"
    _build_sample_repo(repo_root)

    hits = search_repository(
        repo_root,
        query="If we change auth or session handling, what is impacted?",
        top_k=5,
        settings=Settings(),
    )

    assert hits
    assert hits[0].path == "docs/auth.md"
    assert any(hit.path == "tests/test_auth.py" for hit in hits)
    assert any(hit.path == "runbooks/session_rollback.md" for hit in hits)
    assert any(hit.path == "prs/pr_1842.md" for hit in hits)
    assert len({hit.path for hit in hits}) == len(hits)
    assert any(hit.verified for hit in hits)
