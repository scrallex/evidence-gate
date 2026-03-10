"""Application configuration for Evidence Gate."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class ThresholdConfig(BaseModel):
    """Thresholds for the initial deterministic decision engine."""

    top_k_evidence: int = 5
    top_k_twins: int = 3
    admit_score_min: float = 0.25
    admit_evidence_count: int = 2
    escalate_score_min: float = 0.12
    escalate_evidence_count: int = 1
    focus_path_limit: int = 2
    structural_window_bytes: int = 96
    structural_stride_bytes: int = 48
    structural_precision: int = 2
    structural_hazard_percentile: float = 0.8
    verification_coverage_threshold: float = 0.5
    verification_semantic_threshold: float = 0.08
    verification_structural_threshold: float = 0.08


class Settings(BaseModel):
    """Static application settings."""

    app_name: str = "Evidence Gate"
    version: str = "0.1.0"
    audit_root: Path = Field(default_factory=lambda: Path("var/audit"))
    knowledge_root: Path = Field(default_factory=lambda: Path("var/knowledge_bases"))
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from the environment."""

    audit_root = Path(os.environ.get("EVIDENCE_GATE_AUDIT_ROOT", "var/audit"))
    knowledge_root = Path(os.environ.get("EVIDENCE_GATE_KB_ROOT", "var/knowledge_bases"))
    return Settings(audit_root=audit_root, knowledge_root=knowledge_root)
