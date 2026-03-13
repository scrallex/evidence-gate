"""MCP server for Evidence Gate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Literal

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
    DecisionName,
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
for planned code edits, `evidence_gate_prepare_repository` when the knowledge base may be
missing or stale, and `evidence_gate_gate_action_with_healing` when you want the full
fail-explain-repair-retry loop. If the decision is `abstain` or `escalate`, do not represent
the change as safe. Summarize the missing evidence, cite the strongest evidence spans, and
inspect returned twin PR or incident cases before continuing.
""".strip()


class MCPHealthResponse(BaseModel):
    """Basic status surface for MCP clients."""

    status: str
    service: str
    version: str


class RecentDecisionsResponse(BaseModel):
    decisions: list[DecisionRecord]


class MCPRepositoryPreparationResponse(BaseModel):
    repo_path: str
    ready: bool
    status: str
    preparation_action: Literal["reused", "ingested"]
    ingest_status: str | None = None
    repo_fingerprint: str | None = None
    knowledge_base_path: str | None = None
    external_source_count: int = 0


class MCPHealingLoopResponse(BaseModel):
    preparation: MCPRepositoryPreparationResponse | None = None
    action_decision: ActionDecisionResponse
    retry_prompt: str | None = None
    next_step: Literal["proceed", "repair_and_retry", "inspect_evidence"]
    strongest_evidence_sources: list[str]
    twin_case_sources: list[str]


class MCPIntentEvaluationResponse(BaseModel):
    preparation: MCPRepositoryPreparationResponse | None = None
    intent_decision: DecisionRecord
    preflight_prompt: str | None = None
    next_step: Literal["proceed", "inspect_evidence_first"]
    strongest_evidence_sources: list[str]
    twin_case_sources: list[str]


READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
NON_DESTRUCTIVE = ToolAnnotations(destructiveHint=False, openWorldHint=False)


def _build_retry_prompt(missing_evidence: Sequence[str]) -> str:
    guidance = "; ".join(str(item).strip() for item in missing_evidence if str(item).strip())
    if not guidance:
        return ""
    guidance = "; ".join(guidance.split("; ")[:3])
    return (
        "Evidence Gate blocked the previous attempt because: "
        f"{guidance}. "
        "Write the missing tests or update the supported files, then retry the gate."
    )


def _prepare_repository(
    *,
    repo_path: str,
    refresh: bool,
    external_sources: list[dict[str, str]] | None,
) -> MCPRepositoryPreparationResponse:
    service = get_decision_service()
    status = service.get_repository_ingest_status(repo_path)
    source_count = len(external_sources or [])
    if status.status == "ready" and not refresh:
        return MCPRepositoryPreparationResponse(
            repo_path=repo_path,
            ready=True,
            status=status.status,
            preparation_action="reused",
            repo_fingerprint=status.cached_repo_fingerprint,
            knowledge_base_path=status.knowledge_base_path,
            external_source_count=source_count,
        )

    ingest = service.ingest_repository(
        KnowledgeBaseIngestRequest(
            repo_path=repo_path,
            refresh=True,
            external_sources=external_sources or [],
        )
    )
    updated_status = service.get_repository_ingest_status(repo_path)
    return MCPRepositoryPreparationResponse(
        repo_path=repo_path,
        ready=updated_status.status == "ready",
        status=updated_status.status,
        preparation_action="ingested",
        ingest_status=ingest.status,
        repo_fingerprint=ingest.repo_fingerprint,
        knowledge_base_path=ingest.knowledge_base_path,
        external_source_count=source_count,
    )


def _build_intent_prompt(intent_summary: str, decision: DecisionRecord) -> str:
    strongest_sources = [span.source for span in decision.evidence_spans[:3]]
    twin_sources = [twin.source for twin in decision.twin_cases[:2]]
    evidence_clause = ", ".join(strongest_sources + twin_sources) or "the strongest retrieved evidence"
    missing_clause = "; ".join(decision.missing_evidence[:3])
    if missing_clause:
        return (
            f"Before implementing '{intent_summary}', inspect {evidence_clause}. "
            f"Address the missing evidence first: {missing_clause}"
        )
    return f"Before implementing '{intent_summary}', inspect {evidence_clause} and preserve the cited behavior."


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
        name="evidence_gate_prepare_repository",
        description=(
            "Ensure a repository knowledge base is ready for later Evidence Gate decisions. Reuse a ready "
            "knowledge base when possible, or ingest automatically when the cache is missing, stale, or "
            "the caller requests a refresh."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def prepare_repository(
        repo_path: str,
        refresh: bool = False,
        external_sources: list[dict[str, str]] | None = None,
    ) -> MCPRepositoryPreparationResponse:
        try:
            return _prepare_repository(
                repo_path=repo_path,
                refresh=refresh,
                external_sources=external_sources,
            )
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
        name="evidence_gate_gate_action_with_healing",
        description=(
            "Run the full fail-explain-repair-retry loop: optionally prepare the repository, gate a "
            "proposed action, and return a retry prompt plus next-step guidance when the action is blocked."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def gate_action_with_healing(
        repo_path: str,
        action_summary: str,
        changed_paths: list[str] | None = None,
        diff_summary: str | None = None,
        safety_policy: dict[str, object] | None = None,
        top_k: int = 5,
        prepare_repository: bool = True,
        refresh_repository: bool = False,
        external_sources: list[dict[str, str]] | None = None,
    ) -> MCPHealingLoopResponse:
        try:
            preparation = None
            if prepare_repository:
                preparation = _prepare_repository(
                    repo_path=repo_path,
                    refresh=refresh_repository,
                    external_sources=external_sources,
                )
            action_decision = get_decision_service().decide_action(
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

        retry_prompt = ""
        next_step: Literal["proceed", "repair_and_retry", "inspect_evidence"] = "proceed"
        if not action_decision.allowed:
            retry_prompt = _build_retry_prompt(action_decision.decision_record.missing_evidence)
            next_step = "repair_and_retry" if retry_prompt else "inspect_evidence"

        return MCPHealingLoopResponse(
            preparation=preparation,
            action_decision=action_decision,
            retry_prompt=retry_prompt or None,
            next_step=next_step,
            strongest_evidence_sources=[
                span.source for span in action_decision.decision_record.evidence_spans[:3]
            ],
            twin_case_sources=[
                twin.source for twin in action_decision.decision_record.twin_cases[:3]
            ],
        )

    @mcp.tool(
        name="evidence_gate_evaluate_intent",
        description=(
            "Evaluate a planned engineering intent before code is written. Reuse or prepare the knowledge base, "
            "search code plus external context, and return preflight guidance grounded in incidents, runbooks, "
            "tickets, and prior code evidence."
        ),
        annotations=NON_DESTRUCTIVE,
        structured_output=True,
    )
    def evaluate_intent(
        repo_path: str,
        intent_summary: str,
        changed_paths: list[str] | None = None,
        diff_summary: str | None = None,
        top_k: int = 5,
        prepare_repository: bool = True,
        refresh_repository: bool = False,
        external_sources: list[dict[str, str]] | None = None,
    ) -> MCPIntentEvaluationResponse:
        try:
            preparation = None
            if prepare_repository:
                preparation = _prepare_repository(
                    repo_path=repo_path,
                    refresh=refresh_repository,
                    external_sources=external_sources,
                )
            intent_query = (
                "Before implementing this plan, what code, tests, docs, runbooks, tickets, wiki pages, "
                f"or incidents should guide the work?\nPlan: {intent_summary}"
            )
            intent_decision = get_decision_service().decide_change_impact(
                ChangeImpactRequest(
                    repo_path=repo_path,
                    change_summary=intent_query,
                    changed_paths=changed_paths or [],
                    diff_summary=diff_summary,
                    top_k=top_k,
                )
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        next_step: Literal["proceed", "inspect_evidence_first"] = "proceed"
        preflight_prompt: str | None = None
        if (
            intent_decision.decision != DecisionName.ADMIT
            or bool(intent_decision.missing_evidence)
            or any(twin.source_type.value == "incident" for twin in intent_decision.twin_cases)
        ):
            next_step = "inspect_evidence_first"
            preflight_prompt = _build_intent_prompt(intent_summary, intent_decision)

        return MCPIntentEvaluationResponse(
            preparation=preparation,
            intent_decision=intent_decision,
            preflight_prompt=preflight_prompt,
            next_step=next_step,
            strongest_evidence_sources=[
                span.source for span in intent_decision.evidence_spans[:3]
            ],
            twin_case_sources=[
                twin.source for twin in intent_decision.twin_cases[:3]
            ],
        )

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

    @mcp.prompt(
        name="evidence_gate_fail_explain_repair_retry",
        title="Run The Evidence Gate Healing Loop",
        description="Prime an agent to prepare the repo, gate an action, and retry with the returned repair guidance.",
    )
    def fail_explain_repair_retry_prompt(
        repo_path: str,
        action_summary: str,
        changed_paths: str = "",
        diff_summary: str = "",
    ) -> list[dict[str, str]]:
        changed_display = changed_paths.strip() or "none provided"
        diff_display = diff_summary.strip() or "none provided"
        return [
            {
                "role": "user",
                "content": (
                    "Run Evidence Gate as a fail-explain-repair-retry loop before changing code.\n"
                    f"Repository: {repo_path}\n"
                    f"Proposed action: {action_summary}\n"
                    f"Changed paths: {changed_display}\n"
                    f"Diff summary: {diff_display}\n\n"
                    "1. Call `evidence_gate_prepare_repository` if the knowledge base may be missing or stale.\n"
                    "2. Call `evidence_gate_gate_action_with_healing`.\n"
                    "3. If `next_step` is `repair_and_retry`, use `retry_prompt` as the next agent instruction.\n"
                    "4. If `next_step` is `inspect_evidence`, inspect `missing_evidence`, strongest evidence, and twin cases before editing.\n"
                    "5. Only continue as if the change is safe when the returned action decision is allowed."
                ),
            }
        ]

    @mcp.prompt(
        name="evidence_gate_plan_with_intent",
        title="Evaluate Intent Before Writing Code",
        description="Prime an agent to ask Evidence Gate for preflight guidance before it edits code.",
    )
    def plan_with_intent_prompt(
        repo_path: str,
        intent_summary: str,
        changed_paths: str = "",
    ) -> list[dict[str, str]]:
        changed_display = changed_paths.strip() or "none provided"
        return [
            {
                "role": "user",
                "content": (
                    "Before writing code, evaluate the plan with Evidence Gate.\n"
                    f"Repository: {repo_path}\n"
                    f"Planned intent: {intent_summary}\n"
                    f"Likely changed paths: {changed_display}\n\n"
                    "1. Call `evidence_gate_prepare_repository` if the knowledge base may be missing or stale.\n"
                    "2. Call `evidence_gate_evaluate_intent`.\n"
                    "3. If `next_step` is `inspect_evidence_first`, read the cited evidence and follow the "
                    "returned `preflight_prompt` before editing code.\n"
                    "4. Only proceed without extra review when the returned intent decision is `admit`."
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
