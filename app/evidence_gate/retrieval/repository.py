"""Lightweight repository scanning and lexical retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from evidence_gate.decision.models import ExternalMetadata, SourceType

WORD_RE = re.compile(r"[A-Za-z0-9_]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}
TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".rb",
    ".rst",
    ".sh",
    ".tcl",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
MAX_FILE_BYTES = 256_000


@dataclass(slots=True)
class DocumentRecord:
    path: str
    source_type: SourceType
    content: str
    lines: tuple[str, ...]
    token_counts: Counter[str]
    path_token_counts: Counter[str]
    metadata: ExternalMetadata | None = None


@dataclass(slots=True)
class SearchHit:
    path: str
    source_type: SourceType
    score: float
    snippet: str
    line_number: int | None
    verified: bool = False
    metadata: ExternalMetadata | None = None


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in WORD_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


def classify_source_type(relative_path: str) -> SourceType:
    lower = relative_path.lower()
    name = Path(lower).name
    if (
        "/tests/" in f"/{lower}"
        or lower.startswith("tests/")
        or "/__tests__/" in f"/{lower}"
        or lower.endswith("/__tests__")
        or "/e2e/" in f"/{lower}"
        or lower.startswith("e2e/")
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    ):
        return SourceType.TEST
    if "runbook" in lower or "playbook" in lower:
        return SourceType.RUNBOOK
    if "incident" in lower or "postmortem" in lower:
        return SourceType.INCIDENT
    if lower.startswith("prs/") or "/prs/" in f"/{lower}" or "pull_request" in lower or re.search(r"\bpr[_-]?\d+", lower):
        return SourceType.PR
    if Path(lower).suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".rb", ".c", ".cc", ".cpp", ".h", ".hpp"}:
        return SourceType.CODE
    if lower.endswith((".md", ".rst", ".txt")):
        return SourceType.DOC
    return SourceType.OTHER


def iter_repository_files(
    repo_root: Path,
    *,
    exclude_relative_prefixes: tuple[str, ...] = (),
) -> list[Path]:
    files: list[Path] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        if any(
            rel_path == prefix or rel_path.startswith(f"{prefix}/")
            for prefix in exclude_relative_prefixes
        ):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)
    return files


def scan_repository(
    repo_root: Path,
    *,
    exclude_relative_prefixes: tuple[str, ...] = (),
) -> list[DocumentRecord]:
    from evidence_gate.ingest.local_repo import LocalRepoIngestor

    return LocalRepoIngestor(
        repo_root,
        exclude_relative_prefixes=exclude_relative_prefixes,
    ).collect_documents()


def _best_snippet(lines: tuple[str, ...], query_tokens: set[str]) -> tuple[str, int | None]:
    best_line = ""
    best_index: int | None = None
    best_score = -1
    for index, line in enumerate(lines, start=1):
        clean_line = " ".join(line.strip().split())
        if not clean_line:
            continue
        score = sum(1 for token in query_tokens if token in clean_line.lower())
        if score > best_score:
            best_score = score
            best_line = clean_line
            best_index = index
    if best_line:
        return best_line[:240], best_index
    return "", None


def search_documents(documents: list[DocumentRecord], query: str, top_k: int) -> list[SearchHit]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    query_counts = Counter(query_tokens)
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(document.token_counts.keys())

    document_count = max(1, len(documents))
    max_query_weight = sum(
        (math.log((document_count + 1) / (1 + document_frequency[token])) + 1.0) * count
        for token, count in query_counts.items()
    )
    if max_query_weight <= 0:
        return []

    hits: list[SearchHit] = []
    for document in documents:
        weighted_overlap = 0.0
        matched_unique = 0
        for token, count in query_counts.items():
            occurrences = max(
                document.token_counts.get(token, 0),
                document.path_token_counts.get(token, 0),
            )
            if not occurrences:
                continue
            matched_unique += 1
            idf = math.log((document_count + 1) / (1 + document_frequency[token])) + 1.0
            weighted_overlap += min(count, occurrences) * idf

        if weighted_overlap <= 0:
            continue

        strength = min(1.0, weighted_overlap / max_query_weight)
        coverage = matched_unique / max(1, len(query_counts))
        score = min(1.0, 0.6 * coverage + 0.4 * strength)
        snippet, line_number = _best_snippet(document.lines, set(query_tokens))
        hits.append(
            SearchHit(
                path=document.path,
                source_type=document.source_type,
                score=score,
                snippet=snippet or document.content.strip().splitlines()[0][:240],
                line_number=line_number,
            )
        )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:top_k]
