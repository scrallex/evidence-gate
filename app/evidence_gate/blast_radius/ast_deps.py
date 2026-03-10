"""AST-based dependency analysis for initial blast radius scoring."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from evidence_gate.decision.models import BlastRadius
from evidence_gate.retrieval.repository import SKIP_DIRS, classify_source_type


@dataclass
class DependencyInfo:
    file_path: str
    imports: set[str] = field(default_factory=set)
    imported_by: set[str] = field(default_factory=set)


class ASTDependencyAnalyzer:
    """Analyze repo imports and derive a conservative blast radius."""

    valid_extensions = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
    }

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.dependencies: dict[str, DependencyInfo] = {}
        self.module_to_file: dict[str, str] = {}
        self.workspace_roots: dict[str, str] = {}

    def build_dependency_graph(self) -> None:
        self.workspace_roots = self._discover_workspace_roots()
        source_files = [
            path
            for path in self.repo_root.rglob("*")
            if path.is_file()
            and path.suffix in self.valid_extensions
            and not any(part in SKIP_DIRS for part in path.parts)
        ]

        for source_file in source_files:
            rel_path = source_file.relative_to(self.repo_root).as_posix()
            module_name = self._file_to_module(source_file)
            self.module_to_file[module_name] = rel_path
            self.dependencies[rel_path] = DependencyInfo(
                file_path=rel_path,
                imports=self._extract_imports(source_file),
            )

        for file_path, dependency in self.dependencies.items():
            for imported_module in dependency.imports:
                target_file = self._resolve_import(imported_module)
                if target_file and target_file in self.dependencies:
                    self.dependencies[target_file].imported_by.add(file_path)

    def impacted_files(self, file_path: str) -> set[str]:
        if file_path not in self.dependencies:
            return {file_path}

        visited: set[str] = set()
        queue = [file_path]
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            dependency = self.dependencies.get(current)
            if dependency is None:
                continue
            for importer in dependency.imported_by:
                if importer not in visited:
                    queue.append(importer)
        return visited

    def dependency_depth(self, file_path: str) -> int:
        if file_path not in self.dependencies:
            return 0

        def _walk(current: str, seen: set[str]) -> int:
            dependency = self.dependencies.get(current)
            if dependency is None:
                return 0
            depth = 0
            for importer in dependency.imported_by:
                if importer in seen:
                    continue
                depth = max(depth, 1 + _walk(importer, seen | {importer}))
            return depth

        return _walk(file_path, {file_path})

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

    def _extract_imports(self, file_path: Path) -> set[str]:
        if file_path.suffix == ".py":
            return self._extract_python_imports(file_path)
        if file_path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            return self._extract_js_imports(file_path)
        if file_path.suffix in {".c", ".cc", ".cpp", ".h", ".hpp"}:
            return self._extract_cpp_imports(file_path)
        return set()

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

    def _resolve_import(self, imported_module: str) -> str | None:
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
