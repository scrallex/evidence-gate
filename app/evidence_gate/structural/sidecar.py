"""Structural sidecar index and hazard-gated verification adapted for Evidence Gate."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Mapping

from evidence_gate.structural.encoding import encode_window, signature_from_metrics


@dataclass(slots=True)
class EncodedWindow:
    signature: str
    hazard: float
    entropy: float
    coherence: float
    stability: float
    byte_start: int
    byte_end: int
    char_start: int
    char_end: int
    window_index: int


@dataclass(slots=True)
class EncodeResult:
    windows: list[EncodedWindow]
    prototypes: dict[str, str]
    hazards: list[float]
    hazard_threshold: float
    window_bytes: int
    stride_bytes: int
    precision: int


@dataclass(slots=True)
class ManifoldIndex:
    meta: dict[str, object]
    signatures: dict[str, dict[str, object]]
    documents: dict[str, dict[str, object]]


@dataclass(slots=True)
class VerificationResult:
    verified: bool
    coverage: float
    match_ratio: float
    hazard_threshold: float
    total_windows: int
    gated_hits: int
    matched_documents: list[str]


def _build_byte_index(text: str) -> list[int]:
    offsets = [0]
    for char in text:
        offsets.append(offsets[-1] + len(char.encode("utf-8")))
    return offsets


def _byte_to_char(byte_offset: int, byte_index: list[int]) -> int:
    return max(0, bisect_right(byte_index, byte_offset) - 1)


def sliding_windows(data: bytes, window_bytes: int, stride_bytes: int) -> list[tuple[int, bytes]]:
    """Generate stable byte windows with tail coverage."""

    if not data:
        return []
    if len(data) <= window_bytes:
        return [(0, data)]
    windows: list[tuple[int, bytes]] = []
    for offset in range(0, len(data) - window_bytes + 1, stride_bytes):
        windows.append((offset, data[offset : offset + window_bytes]))
    tail_start = len(data) - window_bytes
    if tail_start % stride_bytes != 0:
        windows.append((tail_start, data[tail_start:]))
    return windows


def encode_text(
    text: str,
    *,
    window_bytes: int = 96,
    stride_bytes: int = 48,
    precision: int = 2,
    hazard_percentile: float = 0.8,
) -> EncodeResult:
    """Encode a text span into structural windows and hazards."""

    text_bytes = text.encode("utf-8")
    if not text_bytes:
        return EncodeResult(
            windows=[],
            prototypes={},
            hazards=[],
            hazard_threshold=0.0,
            window_bytes=window_bytes,
            stride_bytes=stride_bytes,
            precision=precision,
        )

    byte_index = _build_byte_index(text)
    windows: list[EncodedWindow] = []
    prototypes: dict[str, str] = {}
    hazards: list[float] = []

    for window_index, (offset, chunk) in enumerate(sliding_windows(text_bytes, window_bytes, stride_bytes)):
        metrics = encode_window(chunk)
        signature = signature_from_metrics(
            metrics["coherence"],
            metrics["stability"],
            metrics["entropy"],
            precision=precision,
        )
        byte_start = offset
        byte_end = offset + len(chunk)
        encoded = EncodedWindow(
            signature=signature,
            hazard=float(metrics["lambda_hazard"]),
            entropy=float(metrics["entropy"]),
            coherence=float(metrics["coherence"]),
            stability=float(metrics["stability"]),
            byte_start=byte_start,
            byte_end=byte_end,
            char_start=_byte_to_char(byte_start, byte_index),
            char_end=_byte_to_char(byte_end, byte_index),
            window_index=window_index,
        )
        windows.append(encoded)
        hazards.append(encoded.hazard)
        prototypes.setdefault(signature, text_bytes[byte_start:byte_end].decode("utf-8", errors="replace"))

    hazards_sorted = sorted(hazards)
    if hazards_sorted:
        threshold_index = int(hazard_percentile * (len(hazards_sorted) - 1))
        hazard_threshold = hazards_sorted[threshold_index]
    else:
        hazard_threshold = 0.0

    return EncodeResult(
        windows=windows,
        prototypes=prototypes,
        hazards=hazards,
        hazard_threshold=hazard_threshold,
        window_bytes=window_bytes,
        stride_bytes=stride_bytes,
        precision=precision,
    )


def build_index(
    docs: Mapping[str, str],
    *,
    window_bytes: int = 96,
    stride_bytes: int = 48,
    precision: int = 2,
    hazard_percentile: float = 0.8,
) -> ManifoldIndex:
    """Build an in-memory sidecar index over the provided spans."""

    signatures: dict[str, dict[str, object]] = {}
    documents: dict[str, dict[str, object]] = {}
    all_hazards: list[float] = []
    total_windows = 0

    for doc_id, text in docs.items():
        encoded = encode_text(
            text,
            window_bytes=window_bytes,
            stride_bytes=stride_bytes,
            precision=precision,
            hazard_percentile=hazard_percentile,
        )
        documents[doc_id] = {
            "window_count": len(encoded.windows),
            "characters": len(text),
        }
        total_windows += len(encoded.windows)
        all_hazards.extend(encoded.hazards)

        for window in encoded.windows:
            entry = signatures.get(window.signature)
            if entry is None:
                entry = {
                    "prototype": {
                        "text": encoded.prototypes[window.signature],
                        "doc_id": doc_id,
                        "char_start": window.char_start,
                        "char_end": window.char_end,
                    },
                    "occurrences": [],
                    "hazard": {"count": 0, "sum": 0.0, "min": 1.0, "max": 0.0},
                }
                signatures[window.signature] = entry

            occurrences = entry["occurrences"]
            occurrences.append(
                {
                    "doc_id": doc_id,
                    "char_start": window.char_start,
                    "char_end": window.char_end,
                    "hazard": window.hazard,
                    "window_index": window.window_index,
                }
            )
            hazard_stats = entry["hazard"]
            hazard_stats["count"] += 1
            hazard_stats["sum"] += window.hazard
            hazard_stats["min"] = min(hazard_stats["min"], window.hazard)
            hazard_stats["max"] = max(hazard_stats["max"], window.hazard)

    hazards_sorted = sorted(all_hazards)
    if hazards_sorted:
        threshold_index = int(hazard_percentile * (len(hazards_sorted) - 1))
        hazard_threshold = hazards_sorted[threshold_index]
    else:
        hazard_threshold = 0.0

    for entry in signatures.values():
        hazard_stats = entry["hazard"]
        count = int(hazard_stats["count"])
        entry["hazard"] = {
            "count": count,
            "min": float(hazard_stats["min"]),
            "max": float(hazard_stats["max"]),
            "mean": (float(hazard_stats["sum"]) / count) if count else 0.0,
        }

    return ManifoldIndex(
        meta={
            "window_bytes": window_bytes,
            "stride_bytes": stride_bytes,
            "precision": precision,
            "hazard_threshold": hazard_threshold,
            "hazard_percentile": hazard_percentile,
            "total_windows": total_windows,
            "documents": len(documents),
        },
        signatures=signatures,
        documents=documents,
    )


def verify_snippet(
    text: str,
    index: ManifoldIndex,
    *,
    coverage_threshold: float = 0.5,
) -> VerificationResult:
    """Verify a span by matching low-hazard signatures against the sidecar index."""

    encoded = encode_text(
        text,
        window_bytes=int(index.meta.get("window_bytes", 96)),
        stride_bytes=int(index.meta.get("stride_bytes", 48)),
        precision=int(index.meta.get("precision", 2)),
    )
    hazard_threshold = float(index.meta.get("hazard_threshold", 0.0))

    total_windows = len(encoded.windows)
    matched_windows = 0
    gated_hits = 0
    matched_documents: set[str] = set()

    for window in encoded.windows:
        entry = index.signatures.get(window.signature)
        if not entry:
            continue
        matched_windows += 1
        occurrences = entry.get("occurrences", [])
        safe_occurrences = [
            occurrence
            for occurrence in occurrences
            if float(occurrence.get("hazard", 1.0)) <= hazard_threshold
        ]
        if window.hazard <= hazard_threshold and (safe_occurrences or occurrences):
            gated_hits += 1
        for occurrence in safe_occurrences or occurrences:
            doc_id = str(occurrence.get("doc_id", ""))
            if doc_id:
                matched_documents.add(doc_id)

    coverage = gated_hits / total_windows if total_windows else 0.0
    match_ratio = matched_windows / total_windows if total_windows else 0.0

    return VerificationResult(
        verified=coverage >= coverage_threshold,
        coverage=coverage,
        match_ratio=match_ratio,
        hazard_threshold=hazard_threshold,
        total_windows=total_windows,
        gated_hits=gated_hits,
        matched_documents=sorted(matched_documents),
    )

