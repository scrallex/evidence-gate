"""Canonical request and response models for Evidence Gate."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DecisionName(str, Enum):
    ADMIT = "admit"
    ABSTAIN = "abstain"
    ESCALATE = "escalate"


class SourceType(str, Enum):
    CODE = "code"
    TEST = "test"
    DOC = "doc"
    RUNBOOK = "runbook"
    PR = "pr"
    INCIDENT = "incident"
    OTHER = "other"


class EvidenceSpan(BaseModel):
    source: str
    source_type: SourceType
    score: float = Field(ge=0.0, le=1.0)
    snippet: str
    line_number: int | None = Field(default=None, ge=1)
    verified: bool = True


class TwinCase(BaseModel):
    id: str
    source: str
    source_type: SourceType
    similarity: float = Field(ge=0.0, le=1.0)
    summary: str


class BlastRadius(BaseModel):
    files: int = Field(default=0, ge=0)
    tests: int = Field(default=0, ge=0)
    docs: int = Field(default=0, ge=0)
    runbooks: int = Field(default=0, ge=0)
    max_dependency_depth: int = Field(default=0, ge=0)
    impacted_paths: list[str] = Field(default_factory=list)


class QueryDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    repo_path: str
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class ChangeImpactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    repo_path: str
    change_summary: str = Field(min_length=1)
    changed_paths: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeBaseIngestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    repo_path: str
    refresh: bool = False


class KnowledgeBaseIngestResponse(BaseModel):
    repo_path: str
    repo_fingerprint: str
    knowledge_base_path: str
    status: Literal["built", "reused", "refreshed"]
    file_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    span_count: int = Field(ge=0)


class KnowledgeBaseStatusResponse(BaseModel):
    repo_path: str
    knowledge_base_path: str
    status: Literal["ready", "stale", "missing"]
    built_at: datetime | None = None
    current_repo_fingerprint: str | None = None
    cached_repo_fingerprint: str | None = None
    current_file_count: int = Field(ge=0)
    cached_file_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    span_count: int = Field(ge=0)
    settings_match: bool = False


class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: list[KnowledgeBaseStatusResponse] = Field(default_factory=list)


class KnowledgeBaseRemovalResponse(BaseModel):
    repo_path: str
    knowledge_base_path: str
    action: Literal["deleted", "missing", "would_delete"]
    previous_status: Literal["ready", "stale", "missing"] | None = None
    reason: Literal["stale", "expired", "overflow"] | None = None
    document_count: int = Field(ge=0)
    span_count: int = Field(ge=0)


class KnowledgeBasePruneRequest(BaseModel):
    stale_only: bool = True
    dry_run: bool = False


class KnowledgeBasePruneResponse(BaseModel):
    stale_only: bool
    dry_run: bool
    removed_count: int = Field(ge=0)
    results: list[KnowledgeBaseRemovalResponse] = Field(default_factory=list)


class KnowledgeBaseMaintenanceRunRequest(BaseModel):
    dry_run: bool = False


class KnowledgeBaseMaintenanceRunResponse(BaseModel):
    ran_at: datetime
    dry_run: bool
    total_knowledge_bases: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    expired_count: int = Field(ge=0)
    overflow_count: int = Field(ge=0)
    results: list[KnowledgeBaseRemovalResponse] = Field(default_factory=list)


class KnowledgeBaseMaintenanceStatusResponse(BaseModel):
    enabled: bool
    prune_on_startup: bool
    max_age_hours: int | None = Field(default=None, ge=1)
    max_cache_entries: int | None = Field(default=None, ge=1)
    last_run: KnowledgeBaseMaintenanceRunResponse | None = None


class DecisionRecord(BaseModel):
    decision_id: str
    created_at: datetime
    request_type: Literal["query", "change-impact"]
    decision: DecisionName
    hazard: float = Field(ge=0.0, le=1.0)
    recurrence: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    twin_cases: list[TwinCase] = Field(default_factory=list)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)
    missing_evidence: list[str] = Field(default_factory=list)
    answer_or_action: str
    explanation: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
