"""HTTP routes for the Evidence Gate alpha service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from evidence_gate.api.main import get_decision_service
from evidence_gate.decision.models import (
    ChangeImpactRequest,
    DecisionRecord,
    KnowledgeBaseIngestRequest,
    KnowledgeBaseIngestResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseStatusResponse,
    QueryDecisionRequest,
)
from evidence_gate.decision.service import DecisionService

router = APIRouter()


@router.post("/v1/decide/query", response_model=DecisionRecord)
def decide_query(
    request: QueryDecisionRequest,
    service: DecisionService = Depends(get_decision_service),
) -> DecisionRecord:
    try:
        return service.decide_query(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v1/decide/change-impact", response_model=DecisionRecord)
def decide_change_impact(
    request: ChangeImpactRequest,
    service: DecisionService = Depends(get_decision_service),
) -> DecisionRecord:
    try:
        return service.decide_change_impact(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/decisions/{decision_id}", response_model=DecisionRecord)
def get_decision(
    decision_id: str,
    service: DecisionService = Depends(get_decision_service),
) -> DecisionRecord:
    record = service.get_decision(decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")
    return record


@router.post("/v1/knowledge-bases/ingest", response_model=KnowledgeBaseIngestResponse)
def ingest_knowledge_base(
    request: KnowledgeBaseIngestRequest,
    service: DecisionService = Depends(get_decision_service),
) -> KnowledgeBaseIngestResponse:
    try:
        return service.ingest_repository(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/knowledge-bases", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    service: DecisionService = Depends(get_decision_service),
) -> KnowledgeBaseListResponse:
    return service.list_ingested_repositories()


@router.get("/v1/knowledge-bases/status", response_model=KnowledgeBaseStatusResponse)
def get_knowledge_base_status(
    repo_path: str,
    service: DecisionService = Depends(get_decision_service),
) -> KnowledgeBaseStatusResponse:
    try:
        return service.get_repository_ingest_status(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
