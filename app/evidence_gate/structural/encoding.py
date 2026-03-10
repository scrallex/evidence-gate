"""Lightweight structural encoding adapted from SEP manifold code."""

from __future__ import annotations

import math


def bytes_to_bits(data: bytes) -> list[int]:
    """Convert a byte string into a bit list."""

    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def compute_metrics(bits: list[int]) -> dict[str, float]:
    """Compute simplified coherence, stability, entropy, and hazard metrics."""

    count = len(bits)
    if count == 0:
        return {
            "coherence": 0.0,
            "stability": 0.0,
            "entropy": 0.0,
            "rupture": 0.0,
            "lambda_hazard": 0.0,
        }

    ones = sum(bits)
    zeros = count - ones
    entropy = 0.0
    for probability in (zeros / count, ones / count):
        if probability > 0:
            entropy -= probability * math.log2(probability)
    entropy = min(entropy, 1.0)

    transitions = sum(1 for idx in range(1, count) if bits[idx] != bits[idx - 1])
    rupture = transitions / (count - 1) if count > 1 else 0.0
    stability = 1.0 - rupture
    coherence = 1.0 - entropy

    return {
        "coherence": coherence,
        "stability": stability,
        "entropy": entropy,
        "rupture": rupture,
        "lambda_hazard": rupture,
    }


def encode_window(window: bytes) -> dict[str, float]:
    """Encode one text window into structural metrics."""

    return compute_metrics(bytes_to_bits(window))


def signature_from_metrics(
    coherence: float,
    stability: float,
    entropy: float,
    *,
    precision: int = 2,
) -> str:
    """Bucket metrics into a structural signature."""

    scale = 10**precision

    def bucket(value: float) -> float:
        clamped = min(max(value, 0.0), 1.0)
        return round(clamped * scale) / scale

    return f"c{bucket(coherence)}_s{bucket(stability)}_e{bucket(entropy)}"

