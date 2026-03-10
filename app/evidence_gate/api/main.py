"""Application entrypoint for Evidence Gate."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.config import Settings, get_settings
from evidence_gate.decision.models import KnowledgeBaseMaintenanceRunRequest
from evidence_gate.decision.service import DecisionService


@lru_cache(maxsize=1)
def get_audit_store() -> FileAuditStore:
    settings = get_settings()
    return FileAuditStore(settings.audit_root)


@lru_cache(maxsize=1)
def get_decision_service() -> DecisionService:
    settings: Settings = get_settings()
    return DecisionService(settings=settings, audit_store=get_audit_store())


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.maintenance.enabled and settings.maintenance.prune_on_startup:
        get_decision_service().run_knowledge_base_maintenance(KnowledgeBaseMaintenanceRunRequest())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=app_lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name, "version": settings.version}

    from evidence_gate.api.routes import router

    app.include_router(router)
    return app


app = create_app()
