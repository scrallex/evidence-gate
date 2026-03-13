"""Application configuration for Evidence Gate."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

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


class ASTCacheConfig(BaseModel):
    """Persistent parse-cache settings for blast-radius analysis."""

    enabled: bool = True
    root: Path = Field(default_factory=lambda: _default_state_root() / "ast_graphs")


class ModelBackendConfig(BaseModel):
    """Configured backend for embeddings or decision assistance."""

    provider: Literal["local_structural", "deterministic", "azure_openai", "openai", "ollama", "vllm"]
    endpoint: str | None = None
    deployment: str | None = None
    model: str | None = None
    api_version: str | None = None


class PrivacyConfig(BaseModel):
    """Security and privacy posture for model-backed deployments."""

    remote_inference_allowed: bool = False
    public_model_training_allowed: bool = False
    organizational_memory_sandboxed: bool = True
    redact_secrets_before_remote_inference: bool = True


class Settings(BaseModel):
    """Static application settings."""

    app_name: str = "Evidence Gate"
    version: str = "0.1.0"
    audit_root: Path = Field(default_factory=lambda: _default_state_root() / "audit")
    knowledge_root: Path = Field(default_factory=lambda: _default_state_root() / "knowledge_bases")
    maintenance: KnowledgeBaseMaintenanceConfig = Field(default_factory=KnowledgeBaseMaintenanceConfig)
    ast_cache: ASTCacheConfig = Field(default_factory=ASTCacheConfig)
    embeddings: ModelBackendConfig = Field(
        default_factory=lambda: ModelBackendConfig(provider="local_structural")
    )
    decision_engine: ModelBackendConfig = Field(
        default_factory=lambda: ModelBackendConfig(provider="deterministic")
    )
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
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
    ast_cache = ASTCacheConfig(
        enabled=_env_bool("EVIDENCE_GATE_AST_CACHE_ENABLED", True),
        root=Path(os.environ.get("EVIDENCE_GATE_AST_CACHE_ROOT", str(_default_state_root() / "ast_graphs"))),
    )
    return Settings(
        audit_root=audit_root,
        knowledge_root=knowledge_root,
        maintenance=maintenance,
        ast_cache=ast_cache,
        embeddings=_load_embedding_backend_config(),
        decision_engine=_load_decision_backend_config(),
        privacy=PrivacyConfig(
            remote_inference_allowed=_env_bool("EVIDENCE_GATE_REMOTE_INFERENCE_ALLOWED", False),
            public_model_training_allowed=_env_bool("EVIDENCE_GATE_PUBLIC_MODEL_TRAINING_ALLOWED", False),
            organizational_memory_sandboxed=_env_bool("EVIDENCE_GATE_ORG_MEMORY_SANDBOXED", True),
            redact_secrets_before_remote_inference=_env_bool(
                "EVIDENCE_GATE_REDACT_SECRETS_BEFORE_REMOTE_INFERENCE",
                True,
            ),
        ),
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


def _load_embedding_backend_config() -> ModelBackendConfig:
    provider = os.environ.get("EVIDENCE_GATE_EMBEDDING_BACKEND", "local_structural").strip() or "local_structural"
    return _load_backend_config(prefix="EVIDENCE_GATE_EMBEDDING", provider=provider)


def _load_decision_backend_config() -> ModelBackendConfig:
    provider = os.environ.get("EVIDENCE_GATE_DECISION_BACKEND", "deterministic").strip() or "deterministic"
    return _load_backend_config(prefix="EVIDENCE_GATE_DECISION", provider=provider)


def _load_backend_config(*, prefix: str, provider: str) -> ModelBackendConfig:
    normalized = provider.strip().lower()
    return ModelBackendConfig(
        provider=normalized,  # type: ignore[arg-type]
        endpoint=_env_optional_str(f"{prefix}_ENDPOINT"),
        deployment=_env_optional_str(f"{prefix}_DEPLOYMENT"),
        model=_env_optional_str(f"{prefix}_MODEL"),
        api_version=_env_optional_str(f"{prefix}_API_VERSION"),
    )


def _env_optional_str(name: str) -> str | None:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def _default_state_root() -> Path:
    return Path.home() / ".evidence-gate"
