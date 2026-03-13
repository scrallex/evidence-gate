"""Path-based code-to-test linking helpers for retrieval and blast radius."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evidence_gate.native_graph import NativeRepoGraph

_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_GENERIC_PATH_TOKENS = frozenset(
    {
        "__tests__",
        "app",
        "apps",
        "build",
        "component",
        "components",
        "dist",
        "e2e",
        "frontend",
        "lib",
        "libs",
        "page",
        "pages",
        "pkg",
        "packages",
        "public",
        "route",
        "routes",
        "screen",
        "screens",
        "service",
        "services",
        "shared",
        "spec",
        "src",
        "test",
        "tests",
        "ui",
        "utils",
        "view",
        "views",
        "web",
    }
)
_GENERIC_SOURCE_STEMS = frozenset({"index", "layout", "loading", "error", "page", "route", "main", "__init__"})


def looks_like_test_path(relative_path: str) -> bool:
    lower = relative_path.lower()
    name = Path(lower).name
    return (
        "/tests/" in f"/{lower}"
        or lower.startswith("tests/")
        or "/__tests__/" in f"/{lower}"
        or lower.endswith("/__tests__")
        or "/e2e/" in f"/{lower}"
        or lower.startswith("e2e/")
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def path_anchor_tokens(relative_path: str) -> set[str]:
    path = Path(relative_path)
    candidate_parts = list(path.parts[-4:])
    stem = path.stem.lower()
    if stem in _GENERIC_SOURCE_STEMS and path.parent.name:
        candidate_parts.append(path.parent.name)
    else:
        candidate_parts.append(path.stem)

    tokens: set[str] = set()
    for part in candidate_parts:
        part_text = Path(part).stem if "." in part else str(part)
        lowered = part_text.lower()
        if lowered in _GENERIC_PATH_TOKENS:
            continue
        for token in _split_identifier_tokens(part_text):
            if len(token) >= 3 and token not in _GENERIC_PATH_TOKENS:
                tokens.add(token)
        compact = "".join(_split_identifier_tokens(part_text))
        if len(compact) >= 3 and compact not in _GENERIC_PATH_TOKENS:
            tokens.add(compact)
    return tokens


def test_link_score(source_path: str, test_path: str) -> float:
    if not looks_like_test_path(test_path):
        return 0.0
    source_tokens = path_anchor_tokens(source_path)
    test_tokens = path_anchor_tokens(test_path)
    overlap = source_tokens & test_tokens
    if not overlap:
        return 0.0

    source_label = _source_anchor_label(source_path)
    score = 0.25 + 0.45 * (len(overlap) / max(1, len(source_tokens)))
    if source_label and source_label in test_tokens:
        score += 0.2

    shared_parent_tokens = {
        token.lower()
        for token in Path(source_path).parts[:-1]
        if token and token.lower() not in _GENERIC_PATH_TOKENS
    } & {
        token.lower()
        for token in Path(test_path).parts[:-1]
        if token and token.lower() not in _GENERIC_PATH_TOKENS
    }
    if shared_parent_tokens:
        score += min(0.15, 0.05 * len(shared_parent_tokens))

    if Path(source_path).stem.lower() in _GENERIC_SOURCE_STEMS:
        parent_label = Path(source_path).parent.name.lower()
        if parent_label and parent_label in test_tokens:
            score += 0.15

    return min(1.0, score)


@dataclass(slots=True)
class TestPathIndex:
    """Index test paths by normalized path-anchor tokens for fast candidate lookup."""

    tests_by_token: dict[str, set[str]] = field(default_factory=dict)
    tokens_by_path: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def from_paths(cls, paths: list[str]) -> "TestPathIndex":
        tests_by_token: dict[str, set[str]] = {}
        tokens_by_path: dict[str, set[str]] = {}
        for path in paths:
            if not looks_like_test_path(path):
                continue
            tokens = path_anchor_tokens(path)
            if not tokens:
                continue
            tokens_by_path[path] = tokens
            for token in tokens:
                tests_by_token.setdefault(token, set()).add(path)
        return cls(tests_by_token=tests_by_token, tokens_by_path=tokens_by_path)

    def linked_tests(
        self,
        source_path: str,
        *,
        native_graph: NativeRepoGraph | None = None,
        max_results: int = 5,
        min_score: float = 0.45,
    ) -> list[tuple[str, float]]:
        source_tokens = path_anchor_tokens(source_path)
        if not source_tokens:
            return []

        candidates: set[str] = set()
        for token in source_tokens:
            candidates.update(self.tests_by_token.get(token, set()))

        graph_related = _graph_related_paths(native_graph, source_path)
        candidates.update(path for path in graph_related if path in self.tokens_by_path)

        scored: list[tuple[str, float]] = []
        for candidate in candidates:
            score = test_link_score(source_path, candidate)
            if candidate in graph_related:
                score = max(score, 0.8)
            if score >= min_score:
                scored.append((candidate, score))

        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:max_results]


def _graph_related_paths(native_graph: NativeRepoGraph | None, source_path: str) -> set[str]:
    if native_graph is None:
        return set()
    return {
        *native_graph.incoming_by_target.get(source_path, set()),
        *native_graph.edges_by_source.get(source_path, set()),
    }


def _source_anchor_label(relative_path: str) -> str:
    path = Path(relative_path)
    stem = path.stem.lower()
    if stem in _GENERIC_SOURCE_STEMS and path.parent.name:
        return path.parent.name.lower()
    return stem


def _split_identifier_tokens(value: str) -> list[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return [token.lower() for token in _WORD_RE.findall(expanded)]
