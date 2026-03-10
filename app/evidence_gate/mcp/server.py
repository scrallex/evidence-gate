"""MCP server for Evidence Gate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pydantic import BaseModel

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from evidence_gate.__init__ import __version__
from evidence_gate.api.main import get_audit_store, get_decision_service, get_settings
from evidence_gate.decision.models import (
    ActionDecisionRequest,
    ActionDecisionResponse,
    ChangeImpactRequest,
    DecisionRecord,
    KnowledgeBaseIngestRequest,
    KnowledgeBaseIngestResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseStatusResponse,
    QueryDecisionRequest,
)

SERVER_INSTRUCTIONS = """
Evidence Gate is a reliability layer for AI agents operating over engineering repositories.
Use it before proposing or applying risky changes. Prefer `evidence_gate_decide_change_impact`
for planned code edits and `evidence_gate_decide_query` for repository evidence questions.
If the decision is `abstain` or `escalate`, do not represent the change as safe. Summarize
the missing evidence, cite the strongest evidence spans, and inspect returned twin PR or
incident cases before continuing.
""".strip()


class MCPHealthResponse(BaseModel):
    """Basic status surface for MCP clients."""

    status: str
    service: str
    version: str


class RecentDecisionsResponse(BaseModel):
    decisions: list[DecisionRecord]


READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
NON_DESTRUCTIVE = ToolAnnotations(destructiveHint=False, openWorldHint=False)


def create_mcp_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8001,
    streamable_http_path: str = "/mcp",
) -> FastMCP:
    """Create the Evidence Gate MCP server."""

    settings = get_settings()
    mcp = FastMCP(
        name=settings.app_name,
        instructions=SERVER_INSTRUCTIONS,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        log_level="INFO",
    )

    @mcp.tool(
        name="evidence_gate_health",
        description="Return basic Evidence Gate service status and version.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def health() -> MCPHealthResponse:
        return MCPHealthResponse(
            status="ok",
            service=settings.app_name,
            version=__version__,
        )

    @mcp.tool(
        name="evidence_gate_ingest_repository",
        description=(
            "Build or refresh a persisted structural knowledge base for a repository so later "
            "decisions can reuse cached evidence, including optional external incident exports."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def ingest_repository(
        repo_path: str,
        refresh: bool = False,
        external_sources: list[dict[str, str]] | None = None,
    ) -> KnowledgeBaseIngestResponse:
        try:
            return get_decision_service().ingest_repository(
                KnowledgeBaseIngestRequest(
                    repo_path=repo_path,
                    refresh=refresh,
                    external_sources=external_sources or [],
                )
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="evidence_gate_list_knowledge_bases",
        description="List all cached repository knowledge bases visible to this Evidence Gate server.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def list_knowledge_bases() -> KnowledgeBaseListResponse:
        return get_decision_service().list_ingested_repositories()

    @mcp.tool(
        name="evidence_gate_get_knowledge_base_status",
        description="Get ready, stale, or missing status for a repository knowledge base.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_knowledge_base_status(repo_path: str) -> KnowledgeBaseStatusResponse:
        try:
            return get_decision_service().get_repository_ingest_status(repo_path)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="evidence_gate_decide_query",
        description=(
            "Decide whether a repository evidence question is supported strongly enough to admit, "
            "abstain, or escalate."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def decide_query(repo_path: str, query: str, top_k: int = 5) -> DecisionRecord:
        try:
            return get_decision_service().decide_query(
                QueryDecisionRequest(repo_path=repo_path, query=query, top_k=top_k)
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="evidence_gate_decide_change_impact",
        description=(
            "Gate a planned engineering change by returning evidence spans, twin cases, blast radius, "
            "and an admit, abstain, or escalate decision."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def decide_change_impact(
        repo_path: str,
        change_summary: str,
        changed_paths: list[str] | None = None,
        diff_summary: str | None = None,
        top_k: int = 5,
    ) -> DecisionRecord:
        try:
            return get_decision_service().decide_change_impact(
                ChangeImpactRequest(
                    repo_path=repo_path,
                    change_summary=change_summary,
                    changed_paths=changed_paths or [],
                    diff_summary=diff_summary,
                    top_k=top_k,
                )
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="evidence_gate_decide_action",
        description=(
            "Block or allow a proposed action using the stricter action-gating contract built on top "
            "of change-impact evidence retrieval."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def decide_action(
        repo_path: str,
        action_summary: str,
        changed_paths: list[str] | None = None,
        diff_summary: str | None = None,
        safety_policy: dict[str, object] | None = None,
        top_k: int = 5,
    ) -> ActionDecisionResponse:
        try:
            return get_decision_service().decide_action(
                ActionDecisionRequest(
                    repo_path=repo_path,
                    action_summary=action_summary,
                    changed_paths=changed_paths or [],
                    diff_summary=diff_summary,
                    safety_policy=safety_policy,
                    top_k=top_k,
                )
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="evidence_gate_get_decision",
        description="Fetch a prior decision record by ID from the audit store.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_decision(decision_id: str) -> DecisionRecord:
        record = get_decision_service().get_decision(decision_id)
        if record is None:
            raise ToolError(f"Decision not found: {decision_id}")
        return record

    @mcp.tool(
        name="evidence_gate_list_recent_decisions",
        description="List recent decision records from the Evidence Gate audit ledger.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def list_recent_decisions(limit: int = 20) -> RecentDecisionsResponse:
        return RecentDecisionsResponse(decisions=get_decision_service().list_recent_decisions(limit))

    @mcp.resource(
        "evidence-gate://schemas/decision-record",
        name="decision_record_schema",
        title="Decision Record Schema",
        description="JSON schema for the canonical Evidence Gate decision contract.",
        mime_type="application/json",
    )
    def decision_record_schema() -> dict[str, object]:
        return DecisionRecord.model_json_schema()

    @mcp.resource(
        "evidence-gate://decisions/{decision_id}",
        name="decision_record",
        title="Decision Record",
        description="Read a persisted decision record by ID.",
        mime_type="application/json",
    )
    def decision_record_resource(decision_id: str) -> dict[str, object]:
        record = get_decision_service().get_decision(decision_id)
        if record is None:
            raise ValueError(f"Decision not found: {decision_id}")
        return record.model_dump(mode="json")

    @mcp.resource(
        "evidence-gate://audit/decisions.jsonl",
        name="audit_ledger",
        title="Audit Ledger",
        description="Raw JSONL audit ledger of persisted Evidence Gate decisions.",
        mime_type="application/x-ndjson",
    )
    def audit_ledger_resource() -> str:
        return get_audit_store().read_ledger_text()

    @mcp.prompt(
        name="evidence_gate_review_change",
        title="Review Change With Evidence Gate",
        description="Prime an agent to call Evidence Gate before proposing or applying risky code edits.",
    )
    def review_change_prompt(
        repo_path: str,
        change_summary: str,
        changed_paths: str = "",
    ) -> list[dict[str, str]]:
        changed_display = changed_paths.strip() or "none provided"
        return [
            {
                "role": "user",
                "content": (
                    "Before suggesting or applying code changes, call "
                    "`evidence_gate_decide_change_impact`.\n"
                    f"Repository: {repo_path}\n"
                    f"Planned change: {change_summary}\n"
                    f"Changed paths: {changed_display}\n\n"
                    "If the decision is `abstain` or `escalate`, do not present the change as safe. "
                    "Summarize missing evidence, cite the strongest evidence spans, and inspect any "
                    "returned PR or incident twins before continuing."
                ),
            }
        ]

    return mcp


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Evidence Gate MCP server."""

    parser = argparse.ArgumentParser(description="Run the Evidence Gate MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport to expose.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for streamable HTTP transport.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for streamable HTTP transport.",
    )
    parser.add_argument(
        "--streamable-http-path",
        default="/mcp",
        help="Path for the streamable HTTP MCP endpoint.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    server = create_mcp_server(
        host=args.host,
        port=args.port,
        streamable_http_path=args.streamable_http_path,
    )
    server.run(args.transport)
    return 0
