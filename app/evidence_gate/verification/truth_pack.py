"""Truth-pack span search and verification adapted from SEP score tooling."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from evidence_gate.decision.models import SourceType
from evidence_gate.retrieval.repository import tokenize
from evidence_gate.structural.sidecar import ManifoldIndex, VerificationResult, verify_snippet

NORMALISE_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return NORMALISE_RE.sub(" ", text.strip().lower())


def _span_id(text: str, source: str, line_number: int | None) -> str:
    digest = hashlib.blake2b(
        f"{source}:{line_number}:{_normalise(text)}".encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return digest


def _qgrams(text: str, q: int) -> set[str]:
    padded = f" {_normalise(text)} "
    if not padded.strip():
        return set()
    if len(padded) < q:
        return {padded}
    return {padded[index : index + q] for index in range(len(padded) - q + 1)}


def _hash_vector(text: str, dimensions: int = 256) -> dict[int, float]:
    counts: dict[int, float] = {}
    for token in tokenize(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest, "little") % dimensions
        counts[bucket] = counts.get(bucket, 0.0) + 1.0
    norm = sum(value * value for value in counts.values()) ** 0.5
    if norm > 0:
        for bucket in list(counts):
            counts[bucket] /= norm
    return counts


def _cosine_similarity(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return max(0.0, min(1.0, sum(value * right.get(bucket, 0.0) for bucket, value in left.items())))


@dataclass(slots=True)
class TruthPackSpan:
    span_id: str
    source: str
    source_type: SourceType
    line_number: int | None
    text: str
    search_text: str
    occurrences: int
    patternability: float
    coherence: float
    stability: float
    entropy: float
    rupture: float
    hazard: float
    signature: str | None
    qgrams: set[str]
    hash_vector: dict[int, float]


@dataclass(slots=True)
class StructuralMatch:
    span: TruthPackSpan
    structural_score: float
    semantic_score: float
    final_score: float


@dataclass(slots=True)
class SpanEvaluation:
    span: TruthPackSpan
    coverage: float
    match_ratio: float
    verified: bool
    repeat_ok: bool
    hazard_ok: bool
    semantic_ok: bool
    structural_ok: bool
    semantic_similarity: float


class TruthPackEngine:
    """Search and verify repository spans against a local truth-pack."""

    def __init__(
        self,
        spans: Iterable[TruthPackSpan],
        *,
        sidecar_index: ManifoldIndex,
        coverage_threshold: float = 0.5,
        semantic_threshold: float = 0.08,
        structural_threshold: float = 0.08,
    ) -> None:
        self.spans: list[TruthPackSpan] = list(spans)
        self.sidecar_index = sidecar_index
        self.coverage_threshold = coverage_threshold
        self.semantic_threshold = semantic_threshold
        self.structural_threshold = structural_threshold
        self.hazard_threshold = float(sidecar_index.meta.get("hazard_threshold", 0.0))
        self._by_id = {span.span_id: span for span in self.spans}
        self._by_norm: dict[str, list[TruthPackSpan]] = {}
        self._token_index: dict[str, set[str]] = {}
        for span in self.spans:
            self._by_norm.setdefault(_normalise(span.text), []).append(span)
            for token in tokenize(span.search_text):
                self._token_index.setdefault(token, set()).add(span.span_id)

    def structural_search(self, query: str, *, top_k: int) -> list[StructuralMatch]:
        query_norm = _normalise(query)
        if not query_norm:
            return []
        query_qgrams = _qgrams(query, 3)
        query_vector = _hash_vector(query)
        query_tokens = tokenize(query)

        candidate_ids: set[str] = set()
        for token in query_tokens:
            candidate_ids |= self._token_index.get(token, set())
        if not candidate_ids:
            candidate_ids = set(self._by_id)

        matches: list[StructuralMatch] = []
        for span_id in candidate_ids:
            span = self._by_id[span_id]
            structural_score = len(query_qgrams & span.qgrams) / max(1, len(query_qgrams))
            semantic_score = max(
                _cosine_similarity(query_vector, span.hash_vector),
                SequenceMatcher(None, query_norm, _normalise(span.search_text)).ratio(),
            )
            path_bonus = 0.0
            if any(token in span.source.lower() for token in query_tokens):
                path_bonus = 0.08
            final_score = min(1.0, 0.45 * structural_score + 0.47 * semantic_score + path_bonus)
            if final_score <= 0.0:
                continue
            matches.append(
                StructuralMatch(
                    span=span,
                    structural_score=structural_score,
                    semantic_score=semantic_score,
                    final_score=final_score,
                )
            )

        matches.sort(
            key=lambda match: (
                match.final_score,
                match.semantic_score,
                match.structural_score,
                match.span.occurrences,
            ),
            reverse=True,
        )
        return matches[:top_k]

    def evaluate(self, span: TruthPackSpan, *, query: str | None = None) -> SpanEvaluation:
        verification = verify_snippet(
            span.text,
            self.sidecar_index,
            coverage_threshold=self.coverage_threshold,
        )
        semantic_similarity = (
            _cosine_similarity(_hash_vector(query or ""), span.hash_vector)
            if query
            else 1.0
        )
        repeat_ok = span.occurrences >= 1
        hazard_ok = span.hazard <= max(self.hazard_threshold, 0.75)
        semantic_ok = semantic_similarity >= self.semantic_threshold
        structural_ok = span.patternability >= self.structural_threshold
        verified = verification.verified and repeat_ok and hazard_ok and (semantic_ok or structural_ok)

        return SpanEvaluation(
            span=span,
            coverage=verification.coverage,
            match_ratio=verification.match_ratio,
            verified=verified,
            repeat_ok=repeat_ok,
            hazard_ok=hazard_ok,
            semantic_ok=semantic_ok,
            structural_ok=structural_ok,
            semantic_similarity=semantic_similarity,
        )

    def occurrences_for_text(self, text: str) -> int:
        return len(self._by_norm.get(_normalise(text), []))


__all__ = [
    "SpanEvaluation",
    "StructuralMatch",
    "TruthPackEngine",
    "TruthPackSpan",
    "_span_id",
]
