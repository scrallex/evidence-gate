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


class KnowledgeBaseMaintenanceConfig(BaseModel):
    """Retention policy for persisted repository knowledge bases."""

    enabled: bool = True
    prune_on_startup: bool = True
    max_age_hours: int | None = 24 * 7
    max_cache_entries: int | None = 20


class Settings(BaseModel):
    """Static application settings."""

    app_name: str = "Evidence Gate"
    version: str = "0.1.0"
    audit_root: Path = Field(default_factory=lambda: _default_state_root() / "audit")
    knowledge_root: Path = Field(default_factory=lambda: _default_state_root() / "knowledge_bases")
    maintenance: KnowledgeBaseMaintenanceConfig = Field(default_factory=KnowledgeBaseMaintenanceConfig)
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from the environment."""

    audit_root = Path(os.environ.get("EVIDENCE_GATE_AUDIT_ROOT", str(_default_state_root() / "audit")))
    knowledge_root = Path(
        os.environ.get("EVIDENCE_GATE_KB_ROOT", str(_default_state_root() / "knowledge_bases"))
    )
    maintenance = KnowledgeBaseMaintenanceConfig(
        enabled=_env_bool("EVIDENCE_GATE_KB_MAINT_ENABLED", True),
        prune_on_startup=_env_bool("EVIDENCE_GATE_KB_PRUNE_ON_STARTUP", True),
        max_age_hours=_env_optional_int("EVIDENCE_GATE_KB_MAX_AGE_HOURS", 24 * 7),
        max_cache_entries=_env_optional_int("EVIDENCE_GATE_KB_MAX_CACHE_ENTRIES", 20),
    )
    return Settings(
        audit_root=audit_root,
        knowledge_root=knowledge_root,
        maintenance=maintenance,
    )


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_int(name: str, default: int | None) -> int | None:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    return int(raw_value)


def _default_state_root() -> Path:
    return Path.home() / ".evidence-gate"
