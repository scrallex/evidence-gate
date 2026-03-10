"""Decision service for query and change-impact workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from uuid import uuid4

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.blast_radius.ast_deps import ASTDependencyAnalyzer
from evidence_gate.config import Settings
from evidence_gate.decision.models import (
    ActionDecisionRequest,
    ActionDecisionResponse,
    ActionSafetyPolicy,
    BlastRadius,
    ChangeImpactRequest,
    DecisionName,
    DecisionRecord,
    EvidenceSpan,
    KnowledgeBaseIngestRequest,
    KnowledgeBaseIngestResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseMaintenanceRunRequest,
    KnowledgeBaseMaintenanceRunResponse,
    KnowledgeBaseMaintenanceStatusResponse,
    KnowledgeBasePruneRequest,
    KnowledgeBasePruneResponse,
    KnowledgeBaseRemovalResponse,
    KnowledgeBaseStatusResponse,
    QueryDecisionRequest,
    SourceType,
    TwinCase,
)
from evidence_gate.retrieval.repository import SearchHit
from evidence_gate.retrieval.structural import (
    CONFLUENCE_SOURCE_KIND,
    INCIDENT_SOURCE_KIND,
    JIRA_SOURCE_KIND,
    PAGERDUTY_SOURCE_KIND,
    REPOSITORY_SOURCE_KIND,
    SLACK_SOURCE_KIND,
    KnowledgeBaseSourceSpec,
    apply_repository_knowledge_base_retention,
    delete_repository_knowledge_base,
    get_repository_knowledge_base_status,
    list_repository_knowledge_bases,
    materialize_repository_knowledge_base,
    prune_repository_knowledge_bases,
    search_repository,
)

_WARNING_EVIDENCE_TERMS = (
    "deprecated",
    "do not use",
    "unsupported",
    "archived",
    "legacy sentinel",
)


class DecisionService:
    """Execute the first Evidence Gate decision workflow."""

    def __init__(self, settings: Settings, audit_store: FileAuditStore):
        self.settings = settings
        self.audit_store = audit_store
        self._last_maintenance_run: KnowledgeBaseMaintenanceRunResponse | None = None

    def decide_query(self, request: QueryDecisionRequest) -> DecisionRecord:
        repo_root = self._resolve_repo_root(request.repo_path)
        ranked_hits = self._search(repo_root, request.query, request.top_k)
        evidence_spans, twin_cases = self._split_hits(ranked_hits)
        focus_paths = [
            evidence.source
            for evidence in evidence_spans
            if evidence.source_type == SourceType.CODE
        ][: self.settings.thresholds.focus_path_limit]
        blast_radius = self._compute_blast_radius(repo_root, focus_paths)
        return self._finalize_record(
            request_type="query",
            prompt=request.query,
            request_payload=request.model_dump(),
            evidence_spans=evidence_spans,
            twin_cases=twin_cases,
            blast_radius=blast_radius,
        )

    def decide_change_impact(self, request: ChangeImpactRequest) -> DecisionRecord:
        repo_root = self._resolve_repo_root(request.repo_path)
        query = self._decision_query(request.change_summary, request.diff_summary)
        ranked_hits = self._search(repo_root, query, request.top_k)
        evidence_spans, twin_cases = self._split_hits(ranked_hits)
        focus_paths = request.changed_paths or [
            evidence.source
            for evidence in evidence_spans
            if evidence.source_type == SourceType.CODE
        ][: self.settings.thresholds.focus_path_limit]
        blast_radius = self._compute_blast_radius(repo_root, focus_paths)
        path_alignment_gap = self._has_changed_path_alignment_gap(request.changed_paths, ranked_hits)
        return self._finalize_record(
            request_type="change-impact",
            prompt=query,
            request_payload=request.model_dump(),
            evidence_spans=evidence_spans,
            twin_cases=twin_cases,
            blast_radius=blast_radius,
            path_alignment_gap=path_alignment_gap,
        )

    def decide_action(self, request: ActionDecisionRequest) -> ActionDecisionResponse:
        repo_root = self._resolve_repo_root(request.repo_path)
        query = self._decision_query(request.action_summary, request.diff_summary)
        ranked_hits = self._search(repo_root, query, request.top_k)
        evidence_spans, twin_cases = self._split_hits(ranked_hits)
        focus_paths = request.changed_paths or [
            evidence.source
            for evidence in evidence_spans
            if evidence.source_type == SourceType.CODE
        ][: self.settings.thresholds.focus_path_limit]
        blast_radius = self._compute_blast_radius(repo_root, focus_paths)
        path_alignment_gap = self._has_changed_path_alignment_gap(request.changed_paths, ranked_hits)
        record = self._finalize_record(
            request_type="action",
            prompt=query,
            request_payload=request.model_dump(),
            evidence_spans=evidence_spans,
            twin_cases=twin_cases,
            blast_radius=blast_radius,
            path_alignment_gap=path_alignment_gap,
            persist=False,
        )
        policy_violations: list[str] = []
        if request.safety_policy is not None:
            record, policy_violations = self._apply_action_safety_policy(record, request.safety_policy)
        self.audit_store.save(record)
        blocking_decisions = list(dict.fromkeys(request.block_on))
        allowed = record.decision not in set(blocking_decisions)
        failure_reason = None
        if not allowed:
            failure_reason = self._action_failure_reason(record.decision, policy_violations)
        return ActionDecisionResponse(
            allowed=allowed,
            status="allow" if allowed else "block",
            blocking_decisions=blocking_decisions,
            failure_reason=failure_reason,
            policy_violations=policy_violations,
            decision_record=record,
        )

    def ingest_repository(self, request: KnowledgeBaseIngestRequest) -> KnowledgeBaseIngestResponse:
        repo_root = self._resolve_repo_root(request.repo_path)
        source_specs = self._build_ingest_source_specs(repo_root, request)
        materialization = materialize_repository_knowledge_base(
            repo_root,
            self.settings,
            force_refresh=request.refresh,
            source_specs=source_specs,
        )
        return KnowledgeBaseIngestResponse(
            repo_path=str(materialization.repo_root),
            repo_fingerprint=materialization.repo_fingerprint,
            knowledge_base_path=str(materialization.cache_dir),
            status=materialization.status,
            file_count=materialization.file_count,
            document_count=materialization.document_count,
            span_count=materialization.span_count,
        )

    def get_repository_ingest_status(self, repo_path: str) -> KnowledgeBaseStatusResponse:
        repo_root = self._resolve_repo_root(repo_path)
        status = get_repository_knowledge_base_status(repo_root, self.settings)
        return KnowledgeBaseStatusResponse(
            repo_path=str(status.repo_root),
            knowledge_base_path=str(status.cache_dir),
            status=status.status,
            built_at=status.built_at,
            current_repo_fingerprint=status.current_repo_fingerprint,
            cached_repo_fingerprint=status.cached_repo_fingerprint,
            current_file_count=status.current_file_count,
            cached_file_count=status.cached_file_count,
            document_count=status.document_count,
            span_count=status.span_count,
            settings_match=status.settings_match,
        )

    def list_ingested_repositories(self) -> KnowledgeBaseListResponse:
        return KnowledgeBaseListResponse(
            knowledge_bases=[
                KnowledgeBaseStatusResponse(
                    repo_path=str(status.repo_root),
                    knowledge_base_path=str(status.cache_dir),
                    status=status.status,
                    built_at=status.built_at,
                    current_repo_fingerprint=status.current_repo_fingerprint,
                    cached_repo_fingerprint=status.cached_repo_fingerprint,
                    current_file_count=status.current_file_count,
                    cached_file_count=status.cached_file_count,
                    document_count=status.document_count,
                    span_count=status.span_count,
                    settings_match=status.settings_match,
                )
                for status in list_repository_knowledge_bases(self.settings)
            ]
        )

    def delete_repository_ingest(self, repo_path: str) -> KnowledgeBaseRemovalResponse:
        repo_root = self._normalize_repo_path(repo_path)
        removal = delete_repository_knowledge_base(repo_root, self.settings)
        return KnowledgeBaseRemovalResponse(
            repo_path=str(removal.repo_root),
            knowledge_base_path=str(removal.cache_dir),
            action=removal.action,
            previous_status=removal.previous_status,
            reason=removal.reason,
            document_count=removal.document_count,
            span_count=removal.span_count,
        )

    def prune_repository_ingests(self, request: KnowledgeBasePruneRequest) -> KnowledgeBasePruneResponse:
        removals = prune_repository_knowledge_bases(
            self.settings,
            stale_only=request.stale_only,
            dry_run=request.dry_run,
        )
        return KnowledgeBasePruneResponse(
            stale_only=request.stale_only,
            dry_run=request.dry_run,
            removed_count=len(removals),
            results=[
                KnowledgeBaseRemovalResponse(
                    repo_path=str(removal.repo_root),
                    knowledge_base_path=str(removal.cache_dir),
                    action=removal.action,
                    previous_status=removal.previous_status,
                    reason=removal.reason,
                    document_count=removal.document_count,
                    span_count=removal.span_count,
                )
                for removal in removals
            ],
        )

    def get_maintenance_status(self) -> KnowledgeBaseMaintenanceStatusResponse:
        policy = self.settings.maintenance
        return KnowledgeBaseMaintenanceStatusResponse(
            enabled=policy.enabled,
            prune_on_startup=policy.prune_on_startup,
            max_age_hours=policy.max_age_hours,
            max_cache_entries=policy.max_cache_entries,
            last_run=self._last_maintenance_run,
        )

    def run_knowledge_base_maintenance(
        self,
        request: KnowledgeBaseMaintenanceRunRequest | None = None,
    ) -> KnowledgeBaseMaintenanceRunResponse:
        run_request = request or KnowledgeBaseMaintenanceRunRequest()
        maintenance_run = apply_repository_knowledge_base_retention(
            self.settings,
            dry_run=run_request.dry_run,
        )
        response = KnowledgeBaseMaintenanceRunResponse(
            ran_at=maintenance_run.ran_at,
            dry_run=maintenance_run.dry_run,
            total_knowledge_bases=maintenance_run.total_knowledge_bases,
            removed_count=len(maintenance_run.removals),
            stale_count=maintenance_run.stale_count,
            expired_count=maintenance_run.expired_count,
            overflow_count=maintenance_run.overflow_count,
            results=[
                KnowledgeBaseRemovalResponse(
                    repo_path=str(removal.repo_root),
                    knowledge_base_path=str(removal.cache_dir),
                    action=removal.action,
                    previous_status=removal.previous_status,
                    reason=removal.reason,
                    document_count=removal.document_count,
                    span_count=removal.span_count,
                )
                for removal in maintenance_run.removals
            ],
        )
        self._last_maintenance_run = response
        return response

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        return self.audit_store.get(decision_id)

    def list_recent_decisions(self, limit: int = 20) -> list[DecisionRecord]:
        return self.audit_store.list_recent(limit)

    def _resolve_repo_root(self, repo_path: str) -> Path:
        repo_root = self._normalize_repo_path(repo_path)
        if not repo_root.exists():
            raise ValueError(f"Repository path does not exist: {repo_root}")
        if not repo_root.is_dir():
            raise ValueError(f"Repository path must be a directory: {repo_root}")
        return repo_root

    def _normalize_repo_path(self, repo_path: str) -> Path:
        return Path(repo_path).expanduser().resolve()

    def _build_ingest_source_specs(
        self,
        repo_root: Path,
        request: KnowledgeBaseIngestRequest,
    ) -> tuple[KnowledgeBaseSourceSpec, ...]:
        external_specs = [
            KnowledgeBaseSourceSpec(
                kind=self._normalize_source_kind(source.type),
                root=self._normalize_repo_path(source.path),
            )
            for source in request.external_sources
        ]
        external_specs.sort(key=lambda source_spec: (source_spec.kind, source_spec.root.as_posix()))
        return (KnowledgeBaseSourceSpec(kind=REPOSITORY_SOURCE_KIND, root=repo_root), *external_specs)

    def _normalize_source_kind(self, source_kind: str) -> str:
        normalized = source_kind.strip().lower()
        if normalized in {INCIDENT_SOURCE_KIND, "incident"}:
            return INCIDENT_SOURCE_KIND
        if normalized in {JIRA_SOURCE_KIND, "ticket", "tickets", "epic", "epics"}:
            return JIRA_SOURCE_KIND
        if normalized in {PAGERDUTY_SOURCE_KIND, "pager-duty", "pager_duty"}:
            return PAGERDUTY_SOURCE_KIND
        if normalized == SLACK_SOURCE_KIND:
            return SLACK_SOURCE_KIND
        if normalized in {CONFLUENCE_SOURCE_KIND, "architecture-docs", "architecture_docs", "wiki"}:
            return CONFLUENCE_SOURCE_KIND
        raise ValueError(f"Unsupported external source type: {source_kind}")

    def _search(self, repo_root: Path, query: str, top_k: int) -> list[SearchHit]:
        hits = search_repository(
            repo_root,
            query=query,
            top_k=top_k,
            settings=self.settings,
        )
        if not hits:
            raise ValueError(f"No structural evidence was found under {repo_root}")
        return hits

    def _split_hits(self, hits: list[SearchHit]) -> tuple[list[EvidenceSpan], list[TwinCase]]:
        evidence_spans: list[EvidenceSpan] = []
        twin_cases: list[TwinCase] = []

        for hit in hits:
            if hit.source_type in {SourceType.PR, SourceType.INCIDENT}:
                if len(twin_cases) >= self.settings.thresholds.top_k_twins:
                    continue
                twin_cases.append(
                    TwinCase(
                        id=Path(hit.path).stem,
                        source=hit.path,
                        source_type=hit.source_type,
                        similarity=hit.score,
                        summary=hit.snippet,
                        metadata=hit.metadata,
                    )
                )
                continue

            if len(evidence_spans) >= self.settings.thresholds.top_k_evidence:
                continue
            evidence_spans.append(
                EvidenceSpan(
                    source=hit.path,
                    source_type=hit.source_type,
                    score=hit.score,
                    snippet=hit.snippet,
                    line_number=hit.line_number,
                    verified=hit.verified,
                    metadata=hit.metadata,
                )
            )

        if not evidence_spans:
            for hit in hits[: self.settings.thresholds.top_k_evidence]:
                evidence_spans.append(
                    EvidenceSpan(
                        source=hit.path,
                        source_type=hit.source_type,
                        score=hit.score,
                        snippet=hit.snippet,
                        line_number=hit.line_number,
                        verified=hit.verified,
                        metadata=hit.metadata,
                    )
                )

        return evidence_spans, twin_cases

    def _compute_blast_radius(self, repo_root: Path, focus_paths: list[str]) -> BlastRadius:
        if not focus_paths:
            return BlastRadius()
        analyzer = ASTDependencyAnalyzer(repo_root)
        analyzer.build_dependency_graph()
        return analyzer.summarize(focus_paths)

    def _finalize_record(
        self,
        *,
        request_type: str,
        prompt: str,
        request_payload: dict[str, object],
        evidence_spans: list[EvidenceSpan],
        twin_cases: list[TwinCase],
        blast_radius: BlastRadius,
        path_alignment_gap: bool = False,
        persist: bool = True,
    ) -> DecisionRecord:
        support_score = (
            mean(sorted((span.score for span in evidence_spans), reverse=True)[:3])
            if evidence_spans
            else 0.0
        )
        recurrence = len(evidence_spans) + len(twin_cases)
        warning_evidence_hit = self._has_warning_evidence(evidence_spans)
        missing_evidence = self._build_missing_evidence(
            evidence_spans,
            twin_cases,
            path_alignment_gap=path_alignment_gap,
            warning_evidence_hit=warning_evidence_hit,
        )
        has_test_support = any(span.source_type == SourceType.TEST for span in evidence_spans)
        has_runbook_support = any(span.source_type == SourceType.RUNBOOK for span in evidence_spans)
        hazard = min(
            1.0,
            max(
                0.0,
                0.65
                - support_score
                + 0.08 * len(missing_evidence)
                + 0.02 * max(0, blast_radius.files - 5),
            ),
        )
        confidence = min(
            1.0,
            max(
                0.0,
                support_score
                + (0.05 if twin_cases else 0.0)
                + (0.05 if has_test_support else 0.0)
                + (0.05 if has_runbook_support else 0.0)
                - 0.03 * max(0, blast_radius.files - 4),
            ),
        )
        decision = self._decide(
            evidence_spans,
            twin_cases,
            support_score,
            missing_evidence,
            path_alignment_gap=path_alignment_gap,
            warning_evidence_hit=warning_evidence_hit,
        )
        explanation = self._build_explanation(decision, support_score, blast_radius, missing_evidence)
        answer_or_action = self._build_summary(prompt, evidence_spans, twin_cases, blast_radius, decision)

        record = DecisionRecord(
            decision_id=uuid4().hex,
            created_at=datetime.now(timezone.utc),
            request_type=request_type,
            decision=decision,
            hazard=hazard,
            recurrence=recurrence,
            confidence=confidence,
            evidence_spans=evidence_spans,
            twin_cases=twin_cases,
            blast_radius=blast_radius,
            missing_evidence=missing_evidence,
            answer_or_action=answer_or_action,
            explanation=explanation,
            request_payload=request_payload,
        )
        if persist:
            self.audit_store.save(record)
        return record

    def _decision_query(self, summary: str, diff_summary: str | None) -> str:
        if not diff_summary:
            return summary
        return f"{summary}\n\nDiff summary:\n{diff_summary}"

    def _apply_action_safety_policy(
        self,
        record: DecisionRecord,
        policy: ActionSafetyPolicy,
    ) -> tuple[DecisionRecord, list[str]]:
        policy_violations: list[str] = []
        has_test_support = any(span.source_type == SourceType.TEST for span in record.evidence_spans)
        has_runbook_support = any(span.source_type == SourceType.RUNBOOK for span in record.evidence_spans)
        has_precedent = bool(record.twin_cases)
        has_incident_precedent = any(twin.source_type == SourceType.INCIDENT for twin in record.twin_cases)

        if (
            policy.max_blast_radius_files is not None
            and record.blast_radius.files > policy.max_blast_radius_files
        ):
            policy_violations.append(
                f"Blast radius files {record.blast_radius.files} exceeded policy limit {policy.max_blast_radius_files}."
            )
        if policy.max_hazard is not None and record.hazard > policy.max_hazard:
            policy_violations.append(
                f"Hazard score {record.hazard:.2f} exceeded policy limit {policy.max_hazard:.2f}."
            )
        if policy.min_confidence is not None and record.confidence < policy.min_confidence:
            policy_violations.append(
                f"Confidence {record.confidence:.2f} fell below policy minimum {policy.min_confidence:.2f}."
            )
        if policy.require_test_evidence and not has_test_support:
            policy_violations.append("Policy requires supporting test evidence.")
        if policy.require_runbook_evidence and not has_runbook_support:
            policy_violations.append("Policy requires runbook or operational evidence.")
        if policy.require_precedent and not has_precedent:
            policy_violations.append("Policy requires prior precedent.")
        if policy.require_incident_precedent and not has_incident_precedent:
            policy_violations.append("Policy requires prior incident precedent.")
        if policy.escalate_on_incident_match and has_incident_precedent:
            policy_violations.append("Policy blocks changes that match prior incident precedent.")

        if not policy_violations:
            return record, []

        missing_evidence = list(record.missing_evidence)
        for violation in policy_violations:
            note = f"Safety policy violation: {violation}"
            if note not in missing_evidence:
                missing_evidence.append(note)
        explanation = (
            f"{record.explanation} Safety policy violations: {' '.join(policy_violations)}"
        )
        answer_or_action = (
            f"{record.answer_or_action} Safety policy violations: {' '.join(policy_violations)}"
        )
        return (
            record.model_copy(
                update={
                    "decision": DecisionName.ESCALATE,
                    "missing_evidence": missing_evidence,
                    "explanation": explanation,
                    "answer_or_action": answer_or_action,
                }
            ),
            policy_violations,
        )

    def _action_failure_reason(
        self,
        decision: DecisionName,
        policy_violations: list[str],
    ) -> str:
        if policy_violations:
            return (
                "Action blocked because Evidence Gate safety thresholds were violated: "
                + "; ".join(policy_violations)
            )
        return f"Action blocked because Evidence Gate returned {decision.value} for the proposed change."

    def _build_missing_evidence(
        self,
        evidence_spans: list[EvidenceSpan],
        twin_cases: list[TwinCase],
        *,
        path_alignment_gap: bool = False,
        warning_evidence_hit: bool = False,
    ) -> list[str]:
        missing: list[str] = []
        if not evidence_spans:
            missing.append("No directly supporting code or documentation was found.")
        if evidence_spans and not any(span.verified for span in evidence_spans):
            missing.append("Retrieved evidence could not be verified against the truth-pack.")
        if path_alignment_gap:
            missing.append("The proposed changed paths were not directly supported by the retrieved evidence.")
        if warning_evidence_hit:
            missing.append("Top retrieved evidence was marked deprecated or explicitly unsafe.")
        if not any(span.source_type == SourceType.TEST for span in evidence_spans):
            missing.append("No supporting test evidence was found for the affected flow.")
        if not any(span.source_type == SourceType.RUNBOOK for span in evidence_spans):
            missing.append("No runbook or operational handling evidence was found.")
        if not twin_cases:
            missing.append("No prior PR or incident precedent was found.")
        return missing

    def _decide(
        self,
        evidence_spans: list[EvidenceSpan],
        twin_cases: list[TwinCase],
        support_score: float,
        missing_evidence: list[str],
        *,
        path_alignment_gap: bool = False,
        warning_evidence_hit: bool = False,
    ) -> DecisionName:
        thresholds = self.settings.thresholds
        evidence_count = len(evidence_spans)
        has_test_support = any(span.source_type == SourceType.TEST for span in evidence_spans)
        has_runbook_support = any(span.source_type == SourceType.RUNBOOK for span in evidence_spans)
        has_precedent = bool(twin_cases)
        verified_code_like = any(
            span.verified and span.source_type in {SourceType.CODE, SourceType.TEST, SourceType.RUNBOOK}
            for span in evidence_spans
        )

        if path_alignment_gap:
            return DecisionName.ESCALATE
        if warning_evidence_hit and not (verified_code_like and has_test_support and has_precedent):
            return DecisionName.ESCALATE

        strong_support = (
            evidence_count >= thresholds.admit_evidence_count
            and support_score >= thresholds.admit_score_min
            and (has_precedent or (has_test_support and has_runbook_support))
        )
        if strong_support and len(missing_evidence) <= 1:
            return DecisionName.ADMIT

        if evidence_count >= thresholds.escalate_evidence_count and support_score >= thresholds.escalate_score_min:
            return DecisionName.ESCALATE

        return DecisionName.ABSTAIN

    def _build_explanation(
        self,
        decision: DecisionName,
        support_score: float,
        blast_radius: BlastRadius,
        missing_evidence: list[str],
    ) -> str:
        return (
            f"Decision {decision.value} based on support score {support_score:.2f}, "
            f"blast radius of {blast_radius.files} files, and {len(missing_evidence)} missing evidence flags."
        )

    def _build_summary(
        self,
        prompt: str,
        evidence_spans: list[EvidenceSpan],
        twin_cases: list[TwinCase],
        blast_radius: BlastRadius,
        decision: DecisionName,
    ) -> str:
        evidence_sources = ", ".join(span.source for span in evidence_spans[:3]) or "no direct evidence"
        twin_sources = ", ".join(twin.source for twin in twin_cases[:2]) or "no precedent cases"
        return (
            f"For '{prompt}', the strongest support came from {evidence_sources}. "
            f"Blast radius touches {blast_radius.files} files, {blast_radius.tests} tests, "
            f"{blast_radius.docs} docs, and {blast_radius.runbooks} runbooks. "
            f"Closest precedent: {twin_sources}. Decision: {decision.value}."
        )

    def _has_changed_path_alignment_gap(
        self,
        changed_paths: list[str],
        ranked_hits: list[SearchHit],
    ) -> bool:
        if not changed_paths:
            return False
        normalized_changed = [self._normalize_relative_path(path) for path in changed_paths if path.strip()]
        if not normalized_changed:
            return False
        hit_paths = [self._normalize_relative_path(hit.path) for hit in ranked_hits]
        return not any(
            self._paths_align(changed_path, hit_path)
            for changed_path in normalized_changed
            for hit_path in hit_paths
        )

    def _normalize_relative_path(self, path: str) -> str:
        normalized = Path(path.strip()).as_posix()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

    def _paths_align(self, changed_path: str, hit_path: str) -> bool:
        changed = Path(changed_path)
        hit = Path(hit_path)
        if changed == hit:
            return True
        if changed.stem and changed.stem == hit.stem:
            return True
        return False

    def _has_warning_evidence(self, evidence_spans: list[EvidenceSpan]) -> bool:
        for span in evidence_spans[:3]:
            lowered = f"{span.source} {span.snippet}".lower()
            if any(term in lowered for term in _WARNING_EVIDENCE_TERMS):
                return True
        return False
