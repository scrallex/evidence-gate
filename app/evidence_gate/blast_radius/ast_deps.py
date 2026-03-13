"""Dependency analysis for blast radius using native graphs plus lightweight fallbacks."""

from __future__ import annotations

import ast
import hashlib
import json
import posixpath
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evidence_gate.decision.models import BlastRadius
from evidence_gate.native_graph import load_repository_native_graph
from evidence_gate.retrieval.repository import SKIP_DIRS, classify_source_type
from evidence_gate.structural.test_links import TestPathIndex
from evidence_gate.structural.tree_sitter_support import (
    analyze_js_ts_file,
    frontend_anchor_tokens,
    is_frontend_code_path,
)

AST_PARSE_CACHE_VERSION = 1


@dataclass
class DependencyInfo:
    file_path: str
    imports: set[str] = field(default_factory=set)
    imported_by: set[str] = field(default_factory=set)
    defined_symbols: set[str] = field(default_factory=set)
    referenced_symbols: set[str] = field(default_factory=set)
    frontend_tokens: set[str] = field(default_factory=set)


class ASTDependencyAnalyzer:
    """Analyze repo imports and derive a conservative blast radius."""

    valid_extensions = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".mts",
        ".cts",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
    }

    def __init__(self, repo_root: Path, *, cache_root: Path | None = None):
        self.repo_root = Path(repo_root)
        self.cache_root = cache_root.resolve() if cache_root is not None else None
        self.dependencies: dict[str, DependencyInfo] = {}
        self.module_to_file: dict[str, str] = {}
        self.workspace_roots: dict[str, str] = {}
        self.native_graph = load_repository_native_graph(self.repo_root)

    def build_dependency_graph(self) -> None:
        self.dependencies = {}
        self.module_to_file = {}
        self.workspace_roots = self._discover_workspace_roots()
        parse_cache = self._load_parse_cache()
        next_cache: dict[str, dict[str, Any]] = {}
        source_files = [
            path
            for path in self.repo_root.rglob("*")
            if path.is_file()
            and path.suffix in self.valid_extensions
            and not any(part in SKIP_DIRS for part in path.parts)
        ]

        for source_file in source_files:
            rel_path = source_file.relative_to(self.repo_root).as_posix()
            stat = source_file.stat()
            cache_entry = parse_cache.get(rel_path)
            cache_hit = self._cache_entry_matches(cache_entry, stat.st_size, stat.st_mtime_ns)
            if cache_hit:
                module_name = str(cache_entry.get("module_name", ""))
                imports = {
                    str(item)
                    for item in cache_entry.get("imports", [])
                    if isinstance(item, str)
                }
                defined_symbols = {
                    str(item)
                    for item in cache_entry.get("defined_symbols", [])
                    if isinstance(item, str)
                }
                referenced_symbols = {
                    str(item)
                    for item in cache_entry.get("referenced_symbols", [])
                    if isinstance(item, str)
                }
            else:
                module_name = self._file_to_module(source_file)
                imports = self._extract_imports(source_file)
                defined_symbols: set[str] = set()
                referenced_symbols: set[str] = set()
                tree_sitter_analysis = analyze_js_ts_file(source_file)
                if tree_sitter_analysis is not None:
                    imports |= tree_sitter_analysis.imports
                    defined_symbols = tree_sitter_analysis.defined_symbols
                    referenced_symbols = tree_sitter_analysis.referenced_symbols
            self.module_to_file[module_name] = rel_path
            self.dependencies[rel_path] = DependencyInfo(
                file_path=rel_path,
                imports=imports,
                defined_symbols=defined_symbols,
                referenced_symbols=referenced_symbols,
                frontend_tokens=frontend_anchor_tokens(rel_path),
            )
            next_cache[rel_path] = {
                "module_name": module_name,
                "imports": sorted(imports),
                "defined_symbols": sorted(defined_symbols),
                "referenced_symbols": sorted(referenced_symbols),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }

        for file_path, dependency in self.dependencies.items():
            for imported_module in dependency.imports:
                target_file = self._resolve_import(imported_module, source_path=file_path)
                if target_file and target_file in self.dependencies:
                    self.dependencies[target_file].imported_by.add(file_path)

        self._apply_native_graph_edges()
        self._apply_symbol_reference_edges()
        self._apply_frontend_test_edges()
        self._apply_path_linked_test_edges()
        self._persist_parse_cache(next_cache)

    def impacted_files(self, file_path: str) -> set[str]:
        return set(self._importer_depths(file_path))

    def dependency_depth(self, file_path: str) -> int:
        importer_depths = self._importer_depths(file_path)
        if not importer_depths:
            return 0
        return max(importer_depths.values())

    def summarize(self, changed_paths: list[str]) -> BlastRadius:
        impacted: set[str] = set()
        max_depth = 0
        for file_path in changed_paths:
            impacted |= self.impacted_files(file_path)
            max_depth = max(max_depth, self.dependency_depth(file_path))

        tests = 0
        docs = 0
        runbooks = 0
        for path in impacted:
            source_type = classify_source_type(path)
            if source_type.value == "test":
                tests += 1
            elif source_type.value == "doc":
                docs += 1
            elif source_type.value == "runbook":
                runbooks += 1

        return BlastRadius(
            files=len(impacted),
            tests=tests,
            docs=docs,
            runbooks=runbooks,
            max_dependency_depth=max_depth,
            impacted_paths=sorted(impacted),
        )

    def _importer_depths(self, file_path: str) -> dict[str, int]:
        if file_path not in self.dependencies:
            return {file_path: 0}

        # Use shortest importer distance rather than exploring all simple paths.
        # Dense or cyclic graphs can make recursive longest-path walks explode.
        depths = {file_path: 0}
        queue: deque[str] = deque([file_path])
        while queue:
            current = queue.popleft()
            dependency = self.dependencies.get(current)
            if dependency is None:
                continue
            next_depth = depths[current] + 1
            for importer in dependency.imported_by:
                if importer in depths:
                    continue
                depths[importer] = next_depth
                queue.append(importer)
        return depths

    def _extract_imports(self, file_path: Path) -> set[str]:
        if file_path.suffix == ".py":
            return self._extract_python_imports(file_path)
        if file_path.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}:
            return self._extract_js_imports(file_path)
        if file_path.suffix in {".c", ".cc", ".cpp", ".h", ".hpp"}:
            return self._extract_cpp_imports(file_path)
        return set()

    def _apply_native_graph_edges(self) -> None:
        if not self.native_graph.has_edges():
            return
        for source_path, target_paths in self.native_graph.edges_by_source.items():
            source_dependency = self.dependencies.get(source_path)
            if source_dependency is None:
                continue
            for target_path in target_paths:
                target_dependency = self.dependencies.get(target_path)
                if target_dependency is None:
                    continue
                source_dependency.imports.add(target_path)
                target_dependency.imported_by.add(source_path)

    def _extract_python_imports(self, file_path: Path) -> set[str]:
        imports: set[str] = set()
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        return imports

    def _extract_js_imports(self, file_path: Path) -> set[str]:
        patterns = [
            r"import\s+(?:.*?\s+from\s+)?['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            r"export\s+(?:.*?\s+from\s+)?['\"]([^'\"]+)['\"]",
        ]
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return set()
        imports: set[str] = set()
        for pattern in patterns:
            imports.update(match.group(1) for match in re.finditer(pattern, content))
        return imports

    def _extract_cpp_imports(self, file_path: Path) -> set[str]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return set()
        return {match.group(1) for match in re.finditer(r'#include\s+["<]([^">]+)[">]', content)}

    def _file_to_module(self, file_path: Path) -> str:
        rel_path = file_path.relative_to(self.repo_root)
        parts = list(rel_path.parts)
        if parts:
            parts[-1] = Path(parts[-1]).stem
        if parts and parts[-1] in {"__init__", "index"}:
            parts = parts[:-1]
        return ".".join(parts)

    def _resolve_import(self, imported_module: str, source_path: str | None = None) -> str | None:
        if source_path is not None and imported_module.startswith("."):
            relative_match = self._resolve_relative_import(source_path, imported_module)
            if relative_match is not None:
                return relative_match
        normalized = imported_module.replace("./", "").replace("../", "").replace("/", ".")
        if normalized in self.module_to_file:
            return self.module_to_file[normalized]
        for module_name, module_file in self.module_to_file.items():
            if module_name == normalized or module_name.startswith(normalized + ".") or module_name.endswith("." + normalized):
                return module_file
        workspace_match = self._resolve_workspace_import(imported_module)
        if workspace_match is not None:
            return workspace_match
        return None

    def _resolve_relative_import(self, source_path: str, imported_module: str) -> str | None:
        source_dir = posixpath.dirname(source_path)
        candidate_root = posixpath.normpath(posixpath.join(source_dir, imported_module))
        candidate_paths = [candidate_root]
        if posixpath.splitext(candidate_root)[1]:
            candidate_paths.append(candidate_root)
        else:
            for suffix in self.valid_extensions:
                candidate_paths.append(candidate_root + suffix)
                candidate_paths.append(posixpath.join(candidate_root, "index" + suffix))
        for candidate in candidate_paths:
            if candidate in self.dependencies:
                return candidate
        return None

    def _discover_workspace_roots(self) -> dict[str, str]:
        workspace_roots: dict[str, str] = {}
        for package_json in self.repo_root.rglob("package.json"):
            if any(part in SKIP_DIRS for part in package_json.parts):
                continue
            rel_dir = package_json.parent.relative_to(self.repo_root).as_posix()
            for alias in self._workspace_aliases_for_package_json(package_json, rel_dir):
                workspace_roots.setdefault(alias, rel_dir)
        return workspace_roots

    def _workspace_aliases_for_package_json(self, package_json: Path, rel_dir: str) -> set[str]:
        aliases: set[str] = set()
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        package_name = payload.get("name")
        if isinstance(package_name, str) and package_name.strip():
            aliases.add(package_name.strip())
            if package_name.startswith("@") and "/" in package_name:
                aliases.add(package_name.split("/", maxsplit=1)[1])
        parts = Path(rel_dir).parts
        if len(parts) >= 2 and parts[0] in {"packages", "apps", "libs", "playground"}:
            aliases.add(parts[1])
        return aliases

    def _resolve_workspace_import(self, imported_module: str) -> str | None:
        package_name, remainder = self._split_workspace_import(imported_module)
        if not package_name:
            return None
        workspace_root = self.workspace_roots.get(package_name)
        if workspace_root is None and package_name.startswith("@") and "/" in package_name:
            workspace_root = self.workspace_roots.get(package_name.split("/", maxsplit=1)[1])
        if workspace_root is None:
            return None

        if remainder:
            normalized_remainder = remainder.replace("./", "").replace("/", ".")
            candidates = [
                module_file
                for module_name, module_file in self.module_to_file.items()
                if module_file.startswith(f"{workspace_root}/")
                and (
                    module_name.endswith("." + normalized_remainder)
                    or module_name.endswith(normalized_remainder)
                    or Path(module_file).stem == Path(remainder).stem
                )
            ]
            if candidates:
                return min(candidates, key=lambda path: (path.count("/"), len(path)))
        return self._preferred_workspace_entry(workspace_root)

    def _split_workspace_import(self, imported_module: str) -> tuple[str, str]:
        if not imported_module or imported_module.startswith("."):
            return "", ""
        if imported_module.startswith("@"):
            parts = imported_module.split("/")
            if len(parts) < 2:
                return imported_module, ""
            return "/".join(parts[:2]), "/".join(parts[2:])
        package_name, _, remainder = imported_module.partition("/")
        return package_name, remainder

    def _preferred_workspace_entry(self, workspace_root: str) -> str | None:
        preferred_suffixes = (
            "/src/index.ts",
            "/src/index.tsx",
            "/src/index.js",
            "/src/index.jsx",
            "/index.ts",
            "/index.tsx",
            "/index.js",
            "/index.jsx",
        )
        for suffix in preferred_suffixes:
            candidate = f"{workspace_root}{suffix}"
            if candidate in self.dependencies:
                return candidate
        candidates = [
            path
            for path in self.dependencies
            if path.startswith(f"{workspace_root}/")
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda path: ("/src/" not in path, path.count("/"), len(path)))

    def _apply_symbol_reference_edges(self) -> None:
        symbol_to_files: dict[str, set[str]] = {}
        for file_path, dependency in self.dependencies.items():
            if classify_source_type(file_path).value == "test":
                continue
            for symbol in dependency.defined_symbols:
                symbol_to_files.setdefault(symbol, set()).add(file_path)

        for file_path, dependency in self.dependencies.items():
            for symbol in dependency.referenced_symbols:
                candidates = {
                    candidate
                    for candidate in symbol_to_files.get(symbol, set())
                    if candidate != file_path
                }
                target_file = self._pick_symbol_target(file_path, candidates)
                if target_file is None:
                    continue
                dependency.imports.add(target_file)
                self.dependencies[target_file].imported_by.add(file_path)

    def _pick_symbol_target(self, source_path: str, candidates: set[str]) -> str | None:
        if not candidates:
            return None
        if len(candidates) == 1:
            return next(iter(candidates))
        source_parts = Path(source_path).parts
        return min(
            candidates,
            key=lambda candidate: (
                -len(set(source_parts[:-1]) & set(Path(candidate).parts[:-1])),
                candidate.count("/"),
                len(candidate),
            ),
        )

    def _apply_frontend_test_edges(self) -> None:
        tests_by_token: dict[str, set[str]] = {}
        for file_path, dependency in self.dependencies.items():
            if classify_source_type(file_path).value != "test":
                continue
            for token in dependency.frontend_tokens:
                tests_by_token.setdefault(token, set()).add(file_path)

        for file_path, dependency in self.dependencies.items():
            if classify_source_type(file_path).value == "test" or not is_frontend_code_path(file_path):
                continue
            candidate_tests: set[str] = set()
            for token in dependency.frontend_tokens:
                candidate_tests.update(tests_by_token.get(token, set()))
            for test_path in candidate_tests:
                if not self._frontend_test_matches(file_path, test_path):
                    continue
                dependency.imported_by.add(test_path)
                self.dependencies[test_path].imports.add(file_path)

    def _frontend_test_matches(self, source_path: str, test_path: str) -> bool:
        source_tokens = self.dependencies[source_path].frontend_tokens
        test_tokens = self.dependencies[test_path].frontend_tokens
        overlap = source_tokens & test_tokens
        if not overlap:
            return False
        source_stem = Path(source_path).stem.lower()
        if source_stem not in {"index", "page", "route", "layout", "loading", "error"} and source_stem in test_tokens:
            return True
        source_name = Path(source_path).stem.lower()
        if source_name in {"index", "page", "route", "layout", "loading", "error"}:
            parent_name = Path(source_path).parent.name.lower()
            if parent_name and parent_name in overlap:
                return True
        return len(overlap) >= 2 or len(source_tokens) == 1

    def _apply_path_linked_test_edges(self) -> None:
        test_paths = [
            file_path
            for file_path in self.dependencies
            if classify_source_type(file_path).value == "test"
        ]
        if not test_paths:
            return
        test_index = TestPathIndex.from_paths(test_paths)
        if not test_index.tokens_by_path:
            return

        for file_path, dependency in self.dependencies.items():
            if classify_source_type(file_path).value == "test":
                continue
            min_score = 0.45 if is_frontend_code_path(file_path) else 0.6
            for test_path, _score in test_index.linked_tests(
                file_path,
                native_graph=self.native_graph,
                max_results=3,
                min_score=min_score,
            ):
                dependency.imported_by.add(test_path)
                self.dependencies[test_path].imports.add(file_path)

    def _load_parse_cache(self) -> dict[str, dict[str, Any]]:
        cache_path = self._cache_file_path()
        if cache_path is None or not cache_path.exists():
            return {}
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        if payload.get("version") != AST_PARSE_CACHE_VERSION:
            return {}
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return {}
        normalized: dict[str, dict[str, Any]] = {}
        for key, value in entries.items():
            if isinstance(key, str) and isinstance(value, dict):
                normalized[key] = value
        return normalized

    def _persist_parse_cache(self, entries: dict[str, dict[str, Any]]) -> None:
        cache_path = self._cache_file_path()
        if cache_path is None:
            return
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": AST_PARSE_CACHE_VERSION,
            "repo_root": str(self.repo_root.resolve()),
            "entries": entries,
        }
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(cache_path)

    def _cache_file_path(self) -> Path | None:
        if self.cache_root is None:
            return None
        repo_hash = hashlib.sha256(str(self.repo_root.resolve()).encode("utf-8")).hexdigest()[:16]
        return self.cache_root / f"{repo_hash}.json"

    def _cache_entry_matches(
        self,
        cache_entry: dict[str, Any] | None,
        size: int,
        mtime_ns: int,
    ) -> bool:
        if not isinstance(cache_entry, dict):
            return False
        return cache_entry.get("size") == size and cache_entry.get("mtime_ns") == mtime_ns
