"""Application entrypoint for Evidence Gate."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.config import Settings, get_settings
from evidence_gate.decision.service import DecisionService


@lru_cache(maxsize=1)
def get_audit_store() -> FileAuditStore:
    settings = get_settings()
    return FileAuditStore(settings.audit_root)


@lru_cache(maxsize=1)
def get_decision_service() -> DecisionService:
    settings: Settings = get_settings()
    return DecisionService(settings=settings, audit_store=get_audit_store())


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name, "version": settings.version}

    from evidence_gate.api.routes import router

    app.include_router(router)
    return app


app = create_app()

