from __future__ import annotations

from pathlib import Path

from evidence_gate.blast_radius.ast_deps import ASTDependencyAnalyzer
from evidence_gate.config import Settings
from evidence_gate.retrieval.repository import SourceType, classify_source_type
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


def test_classify_source_type_recognizes_js_ts_test_conventions() -> None:
    assert classify_source_type("packages/react-art/src/__tests__/ReactART-test.js") == SourceType.TEST
    assert classify_source_type("playground/alias/__tests__/alias.spec.ts") == SourceType.TEST
    assert classify_source_type("apps/web/e2e/login.test.ts") == SourceType.TEST


def test_ast_dependency_analyzer_resolves_workspace_package_aliases(tmp_path: Path) -> None:
    repo_root = tmp_path / "monorepo"
    _write(
        repo_root / "packages" / "cache-kit" / "package.json",
        '{\n  "name": "cache-kit"\n}\n',
    )
    _write(
        repo_root / "packages" / "cache-kit" / "src" / "index.ts",
        "export {loadCache} from './store';\n",
    )
    _write(
        repo_root / "packages" / "cache-kit" / "src" / "store.ts",
        "export function loadCache(key: string) {\n  return key;\n}\n",
    )
    _write(
        repo_root / "packages" / "cache-kit" / "__tests__" / "cache.spec.ts",
        "import {loadCache} from 'cache-kit';\n\n"
        "test('loadCache', () => {\n"
        "  expect(loadCache('abc')).toBe('abc');\n"
        "});\n",
    )

    analyzer = ASTDependencyAnalyzer(repo_root)
    analyzer.build_dependency_graph()

    impacted = analyzer.impacted_files("packages/cache-kit/src/store.ts")

    assert "packages/cache-kit/__tests__/cache.spec.ts" in impacted


def test_ast_dependency_analyzer_dependency_depth_handles_cycles(tmp_path: Path) -> None:
    repo_root = tmp_path / "cyclic_repo"
    _write(
        repo_root / "pkg" / "a.py",
        "from pkg.c import c\n\n"
        "def a():\n"
        "    return c()\n",
    )
    _write(
        repo_root / "pkg" / "b.py",
        "from pkg.a import a\n\n"
        "def b():\n"
        "    return a()\n",
    )
    _write(
        repo_root / "pkg" / "c.py",
        "from pkg.b import b\n\n"
        "def c():\n"
        "    return b()\n",
    )
    _write(
        repo_root / "pkg" / "d.py",
        "from pkg.c import c\n\n"
        "def d():\n"
        "    return c()\n",
    )

    analyzer = ASTDependencyAnalyzer(repo_root)
    analyzer.build_dependency_graph()

    impacted = analyzer.impacted_files("pkg/a.py")
    depth = analyzer.dependency_depth("pkg/a.py")

    assert impacted == {"pkg/a.py", "pkg/b.py", "pkg/c.py", "pkg/d.py"}
    assert depth == 3
