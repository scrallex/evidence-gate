"""Decision service for query and change-impact workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
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
    DashboardHealingCase,
    DashboardHealingSummary,
    DashboardHeadlineMetrics,
    DashboardOverviewResponse,
    DashboardRiskAvoidedItem,
    DashboardSignal,
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
    GITHUB_SOURCE_KIND,
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
from evidence_gate.structural.tree_sitter_support import is_frontend_code_path

_WARNING_EVIDENCE_TERMS = (
    "deprecated",
    "do not use",
    "unsupported",
    "archived",
    "legacy sentinel",
)
_PATH_ALIGNMENT_GAP_NOTE = "The proposed changed paths were not directly supported by the retrieved evidence."
_WARNING_EVIDENCE_NOTE = "Top retrieved evidence was marked deprecated or explicitly unsafe."
_NO_TEST_EVIDENCE_NOTE = "No supporting test evidence was found for the affected flow."
_NO_FRONTEND_TEST_EVIDENCE_NOTE = (
    "Downstream frontend tests appear impacted, but no supporting frontend test evidence was found."
)
_NO_RUNBOOK_EVIDENCE_NOTE = "No runbook or operational handling evidence was found."
_NO_PRECEDENT_NOTE = "No prior PR or incident precedent was found."
_OPEN_SOURCE_IGNORED_NOTES = frozenset({_NO_RUNBOOK_EVIDENCE_NOTE, _NO_PRECEDENT_NOTE})

_DASHBOARD_METHODOLOGY = (
    "Healing rate is inferred from audit history by grouping action decisions on the same repo, "
    "action summary, and changed paths. A sequence counts as healed when a blocked action is followed "
    "by a later allowed action for the same fingerprint."
)
_POLICY_LABELS = {
    "require_test_evidence": "Test evidence required",
    "require_runbook_evidence": "Runbook evidence required",
    "require_precedent": "Precedent required",
    "require_incident_precedent": "Incident precedent required",
    "escalate_on_incident_match": "Incident match blocks rollout",
    "max_blast_radius_files": "Blast radius limit",
    "max_hazard": "Hazard threshold",
    "min_confidence": "Minimum confidence",
}


@dataclass(slots=True)
class _DashboardActionSnapshot:
    record: DecisionRecord
    repo_path: str
    action_summary: str
    changed_paths: tuple[str, ...]
    fingerprint: str
    blocked: bool
    strongest_evidence_sources: tuple[str, ...]
    triggering_signals: tuple[DashboardSignal, ...]
    policy_labels: tuple[str, ...]


@dataclass(slots=True)
class _DashboardOpenSequence:
    first_blocked: _DashboardActionSnapshot
    latest_blocked: _DashboardActionSnapshot
    blocked_attempts: int


@dataclass(slots=True)
class _DashboardHealingComputation:
    blocked_sequences: int
    unresolved_sequences: list[_DashboardOpenSequence]
    healed_cases: list[DashboardHealingCase]
    healed_by_blocked_id: dict[str, DashboardHealingCase]
    blocked_snapshots_by_id: dict[str, _DashboardActionSnapshot]


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

    def get_dashboard_overview(
        self,
        *,
        limit: int = 250,
        feed_limit: int = 12,
        repo_path: str | None = None,
    ) -> DashboardOverviewResponse:
        recent_records = self.audit_store.list_recent(limit)
        filtered_records = [
            record
            for record in recent_records
            if self._matches_dashboard_repo_filter(record, repo_path)
        ]
        action_snapshots = sorted(
            (
                self._build_dashboard_snapshot(record)
                for record in filtered_records
                if record.request_type == "action"
            ),
            key=lambda snapshot: snapshot.record.created_at,
        )
        healing = self._infer_dashboard_healing(action_snapshots)
        blocked_action_count = sum(1 for snapshot in action_snapshots if snapshot.blocked)
        incident_linked_blocks = sum(
            1
            for snapshot in action_snapshots
            if snapshot.blocked and snapshot.triggering_signals
        )
        protected_files = sum(
            snapshot.record.blast_radius.files
            for snapshot in action_snapshots
            if snapshot.blocked
        )
        protected_tests = sum(
            snapshot.record.blast_radius.tests
            for snapshot in action_snapshots
            if snapshot.blocked
        )
        protected_docs = sum(
            snapshot.record.blast_radius.docs
            for snapshot in action_snapshots
            if snapshot.blocked
        )
        protected_runbooks = sum(
            snapshot.record.blast_radius.runbooks
            for snapshot in action_snapshots
            if snapshot.blocked
        )

        recent_heals = sorted(
            healing.healed_cases,
            key=lambda case: case.healed_at,
            reverse=True,
        )[:5]
        healing_times = [
            case.time_to_heal_minutes
            for case in healing.healed_cases
            if case.time_to_heal_minutes is not None
        ]
        average_retries = mean(case.retries_before_heal for case in healing.healed_cases) if healing.healed_cases else 0.0
        healing_rate = (
            len(healing.healed_cases) / healing.blocked_sequences
            if healing.blocked_sequences
            else 0.0
        )

        risk_feed = self._build_dashboard_risk_feed(
            healing=healing,
            feed_limit=feed_limit,
        )
        return DashboardOverviewResponse(
            generated_at=datetime.now(timezone.utc),
            scanned_decisions=len(filtered_records),
            scanned_action_decisions=len(action_snapshots),
            headline_metrics=DashboardHeadlineMetrics(
                blocked_actions=blocked_action_count,
                blocked_sequences=healing.blocked_sequences,
                incident_linked_blocks=incident_linked_blocks,
                protected_files=protected_files,
                protected_tests=protected_tests,
                protected_docs=protected_docs,
                protected_runbooks=protected_runbooks,
            ),
            agent_healing=DashboardHealingSummary(
                blocked_sequences=healing.blocked_sequences,
                healed_sequences=len(healing.healed_cases),
                unresolved_sequences=len(healing.unresolved_sequences),
                healing_rate=healing_rate,
                average_retries_to_heal=round(average_retries, 2),
                median_time_to_heal_minutes=round(median(healing_times), 2) if healing_times else None,
                methodology=_DASHBOARD_METHODOLOGY,
                recent_heals=recent_heals,
            ),
            risk_avoided_feed=risk_feed,
        )

    def _resolve_repo_root(self, repo_path: str) -> Path:
        repo_root = self._normalize_repo_path(repo_path)
        if not repo_root.exists():
            raise ValueError(f"Repository path does not exist: {repo_root}")
        if not repo_root.is_dir():
            raise ValueError(f"Repository path must be a directory: {repo_root}")
        return repo_root

    def _normalize_repo_path(self, repo_path: str) -> Path:
        return Path(repo_path).expanduser().resolve()

    def _matches_dashboard_repo_filter(
        self,
        record: DecisionRecord,
        repo_path: str | None,
    ) -> bool:
        if repo_path is None or not repo_path.strip():
            return True
        record_repo = record.request_payload.get("repo_path")
        if not isinstance(record_repo, str) or not record_repo.strip():
            return False
        return self._normalize_dashboard_repo_path(record_repo) == self._normalize_dashboard_repo_path(repo_path)

    def _normalize_dashboard_repo_path(self, repo_path: str) -> str:
        return Path(repo_path).expanduser().resolve(strict=False).as_posix()

    def _build_dashboard_snapshot(self, record: DecisionRecord) -> _DashboardActionSnapshot:
        payload = record.request_payload
        raw_changed_paths = payload.get("changed_paths", [])
        changed_paths = tuple(
            self._normalize_relative_path(str(path))
            for path in raw_changed_paths
            if str(path).strip()
        )
        action_summary = str(payload.get("action_summary") or "Action decision")
        blocking_decisions = {
            self._normalize_dashboard_decision_name(item)
            for item in payload.get(
                "block_on",
                [DecisionName.ABSTAIN.value, DecisionName.ESCALATE.value],
            )
        }
        strongest_evidence_sources = tuple(span.source for span in record.evidence_spans[:3])
        triggering_signals = tuple(self._collect_dashboard_signals(record))
        policy_labels = tuple(self._extract_dashboard_policy_labels(payload))
        repo_path = str(payload.get("repo_path") or "")
        return _DashboardActionSnapshot(
            record=record,
            repo_path=repo_path,
            action_summary=action_summary,
            changed_paths=changed_paths,
            fingerprint=self._dashboard_action_fingerprint(repo_path, action_summary, changed_paths),
            blocked=record.decision.value in blocking_decisions,
            strongest_evidence_sources=strongest_evidence_sources,
            triggering_signals=triggering_signals,
            policy_labels=policy_labels,
        )

    def _normalize_dashboard_decision_name(self, value: object) -> str:
        if isinstance(value, DecisionName):
            return value.value
        text = str(value).strip().lower()
        if "." in text:
            text = text.rsplit(".", maxsplit=1)[-1]
        return text

    def _dashboard_action_fingerprint(
        self,
        repo_path: str,
        action_summary: str,
        changed_paths: tuple[str, ...],
    ) -> str:
        normalized_repo = self._normalize_dashboard_repo_path(repo_path) if repo_path else ""
        normalized_summary = " ".join(action_summary.lower().split())
        normalized_paths = "|".join(sorted(changed_paths))
        return f"{normalized_repo}::{normalized_summary}::{normalized_paths}"

    def _collect_dashboard_signals(self, record: DecisionRecord) -> list[DashboardSignal]:
        signals: dict[tuple[str, str], DashboardSignal] = {}
        for twin in record.twin_cases:
            signal = self._dashboard_signal_from_source(
                source=twin.source,
                relation="twin_case",
                summary=twin.summary,
                metadata=twin.metadata,
            )
            if signal is not None:
                signals[(signal.source, signal.relation)] = signal
        for span in record.evidence_spans:
            signal = self._dashboard_signal_from_source(
                source=span.source,
                relation="evidence_span",
                summary=span.snippet,
                metadata=span.metadata,
            )
            if signal is not None:
                signals[(signal.source, signal.relation)] = signal
        return sorted(
            signals.values(),
            key=lambda signal: (signal.label, signal.source),
        )

    def _dashboard_signal_from_source(
        self,
        *,
        source: str,
        relation: str,
        summary: str | None,
        metadata: object,
    ) -> DashboardSignal | None:
        classified = self._classify_dashboard_signal(source)
        if classified is None:
            return None
        source_kind, label = classified
        external_url = getattr(metadata, "external_url", None)
        timestamp = getattr(metadata, "timestamp", None)
        normalized_summary = self._trim_dashboard_text(summary)
        return DashboardSignal(
            source=source,
            source_kind=source_kind,
            label=label,
            relation=relation,
            title=self._dashboard_signal_title(source, normalized_summary),
            summary=normalized_summary,
            external_url=external_url,
            timestamp=timestamp,
        )

    def _classify_dashboard_signal(self, source: str) -> tuple[str, str] | None:
        lowered = source.lower()
        if lowered.startswith("external_jira/"):
            return "jira", "Jira"
        if lowered.startswith("external_slack/"):
            return "slack", "Slack"
        if lowered.startswith("external_pagerduty/"):
            return "pagerduty", "PagerDuty"
        if lowered.startswith("external_incidents/") or lowered.startswith("incidents/"):
            return "incident", "Incident"
        if lowered.startswith("external_github_prs/") or lowered.startswith("prs/"):
            return "github", "GitHub PR"
        return None

    def _dashboard_signal_title(self, source: str, summary: str | None) -> str:
        if summary:
            return summary.split(". ", maxsplit=1)[0][:96]
        stem = Path(source).stem.replace("_", " ").replace("-", " ").strip()
        return stem or source

    def _trim_dashboard_text(self, text: str | None, *, limit: int = 180) -> str | None:
        if text is None:
            return None
        normalized = " ".join(str(text).split())
        if not normalized:
            return None
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"

    def _extract_dashboard_policy_labels(self, payload: dict[str, object]) -> list[str]:
        raw_policy = payload.get("safety_policy")
        if not isinstance(raw_policy, dict):
            return []
        labels: list[str] = []
        for key, value in raw_policy.items():
            if value is None or value is False:
                continue
            label = _POLICY_LABELS.get(key)
            if label is None:
                continue
            if isinstance(value, bool):
                labels.append(label)
                continue
            labels.append(f"{label}: {value}")
        return labels

    def _infer_dashboard_healing(
        self,
        action_snapshots: list[_DashboardActionSnapshot],
    ) -> _DashboardHealingComputation:
        open_sequences: dict[str, _DashboardOpenSequence] = {}
        blocked_sequences = 0
        healed_cases: list[DashboardHealingCase] = []
        healed_by_blocked_id: dict[str, DashboardHealingCase] = {}
        blocked_snapshots_by_id: dict[str, _DashboardActionSnapshot] = {}

        for snapshot in action_snapshots:
            sequence = open_sequences.get(snapshot.fingerprint)
            if snapshot.blocked:
                if sequence is None:
                    open_sequences[snapshot.fingerprint] = _DashboardOpenSequence(
                        first_blocked=snapshot,
                        latest_blocked=snapshot,
                        blocked_attempts=1,
                    )
                    blocked_sequences += 1
                    blocked_snapshots_by_id[snapshot.record.decision_id] = snapshot
                    continue
                sequence.latest_blocked = snapshot
                sequence.blocked_attempts += 1
                blocked_snapshots_by_id[sequence.first_blocked.record.decision_id] = sequence.first_blocked
                continue

            if sequence is None:
                continue

            blocked_snapshot = sequence.first_blocked
            time_to_heal_minutes: float | None = None
            elapsed_seconds = (snapshot.record.created_at - blocked_snapshot.record.created_at).total_seconds()
            if elapsed_seconds >= 0:
                time_to_heal_minutes = round(elapsed_seconds / 60.0, 2)
            healed_case = DashboardHealingCase(
                blocked_decision_id=blocked_snapshot.record.decision_id,
                healed_decision_id=snapshot.record.decision_id,
                blocked_at=blocked_snapshot.record.created_at,
                healed_at=snapshot.record.created_at,
                repo_path=blocked_snapshot.repo_path,
                action_summary=blocked_snapshot.action_summary,
                changed_paths=list(blocked_snapshot.changed_paths),
                missing_before=list(blocked_snapshot.record.missing_evidence),
                missing_after=list(snapshot.record.missing_evidence),
                retries_before_heal=sequence.blocked_attempts,
                time_to_heal_minutes=time_to_heal_minutes,
            )
            healed_cases.append(healed_case)
            healed_by_blocked_id[blocked_snapshot.record.decision_id] = healed_case
            blocked_snapshots_by_id[blocked_snapshot.record.decision_id] = blocked_snapshot
            del open_sequences[snapshot.fingerprint]

        return _DashboardHealingComputation(
            blocked_sequences=blocked_sequences,
            unresolved_sequences=list(open_sequences.values()),
            healed_cases=healed_cases,
            healed_by_blocked_id=healed_by_blocked_id,
            blocked_snapshots_by_id=blocked_snapshots_by_id,
        )

    def _build_dashboard_risk_feed(
        self,
        *,
        healing: _DashboardHealingComputation,
        feed_limit: int,
    ) -> list[DashboardRiskAvoidedItem]:
        feed_items: list[DashboardRiskAvoidedItem] = []
        for healed_case in healing.healed_cases:
            blocked_snapshot = healing.blocked_snapshots_by_id.get(healed_case.blocked_decision_id)
            if blocked_snapshot is None:
                continue
            feed_items.append(
                self._dashboard_risk_item_from_snapshot(
                    blocked_snapshot,
                    healed_case=healed_case,
                )
            )
        for unresolved in healing.unresolved_sequences:
            feed_items.append(
                self._dashboard_risk_item_from_snapshot(
                    unresolved.latest_blocked,
                    healed_case=None,
                )
            )
        feed_items.sort(
            key=lambda item: (len(item.triggering_signals) > 0, item.created_at),
            reverse=True,
        )
        return feed_items[:feed_limit]

    def _dashboard_risk_item_from_snapshot(
        self,
        snapshot: _DashboardActionSnapshot,
        *,
        healed_case: DashboardHealingCase | None,
    ) -> DashboardRiskAvoidedItem:
        return DashboardRiskAvoidedItem(
            decision_id=snapshot.record.decision_id,
            created_at=snapshot.record.created_at,
            repo_path=snapshot.repo_path,
            action_summary=snapshot.action_summary,
            changed_paths=list(snapshot.changed_paths),
            status="healed_on_retry" if healed_case is not None else "still_blocked",
            healed_decision_id=healed_case.healed_decision_id if healed_case is not None else None,
            healed_at=healed_case.healed_at if healed_case is not None else None,
            blast_radius=snapshot.record.blast_radius,
            missing_evidence=list(snapshot.record.missing_evidence),
            strongest_evidence_sources=list(snapshot.strongest_evidence_sources),
            triggering_signals=list(snapshot.triggering_signals),
            policy_labels=list(snapshot.policy_labels),
        )

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
        if normalized in {GITHUB_SOURCE_KIND, "github-prs", "github_prs", "pull-requests", "pull_requests", "pulls"}:
            return GITHUB_SOURCE_KIND
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
        support_score = self._support_score(evidence_spans)
        recurrence = len(evidence_spans) + len(twin_cases)
        warning_evidence_hit = self._has_warning_evidence(evidence_spans)
        missing_evidence = self._build_missing_evidence(
            evidence_spans,
            twin_cases,
            blast_radius=blast_radius,
            changed_paths=[
                str(item)
                for item in request_payload.get("changed_paths", [])
                if isinstance(item, str) and str(item).strip()
            ],
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
        record = self._recalibrate_record_for_corpus(record, policy)
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

    def _recalibrate_record_for_corpus(
        self,
        record: DecisionRecord,
        policy: ActionSafetyPolicy,
    ) -> DecisionRecord:
        if policy.corpus_profile != "open_source":
            return record

        missing_evidence = [
            note for note in record.missing_evidence if note not in _OPEN_SOURCE_IGNORED_NOTES
        ]
        update: dict[str, object] = {}
        if missing_evidence != list(record.missing_evidence):
            note = " Open-source corpus profile ignored enterprise-only runbook and precedent gaps."
            update["missing_evidence"] = missing_evidence
            update["explanation"] = record.explanation + note
            update["answer_or_action"] = record.answer_or_action + note

        if self._supports_open_source_admit(record, policy):
            update["decision"] = DecisionName.ADMIT

        if not update:
            return record
        return record.model_copy(update=update)

    def _supports_open_source_admit(
        self,
        record: DecisionRecord,
        policy: ActionSafetyPolicy,
    ) -> bool:
        support_score = self._support_score(record.evidence_spans)
        has_code_support = any(
            span.verified and span.source_type == SourceType.CODE for span in record.evidence_spans
        )
        has_secondary_support = any(
            span.verified and span.source_type in {SourceType.DOC, SourceType.TEST}
            for span in record.evidence_spans
        )
        has_test_support = any(span.source_type == SourceType.TEST for span in record.evidence_spans)
        if _PATH_ALIGNMENT_GAP_NOTE in record.missing_evidence:
            return False
        if _WARNING_EVIDENCE_NOTE in record.missing_evidence:
            return False
        if _NO_FRONTEND_TEST_EVIDENCE_NOTE in record.missing_evidence:
            return False
        if policy.require_test_evidence and not has_test_support:
            return False
        return (
            len(record.evidence_spans) >= self.settings.thresholds.admit_evidence_count
            and support_score >= self.settings.thresholds.admit_score_min
            and has_code_support
            and has_secondary_support
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
        blast_radius: BlastRadius,
        changed_paths: list[str],
        path_alignment_gap: bool = False,
        warning_evidence_hit: bool = False,
    ) -> list[str]:
        missing: list[str] = []
        has_test_support = any(span.source_type == SourceType.TEST for span in evidence_spans)
        if not evidence_spans:
            missing.append("No directly supporting code or documentation was found.")
        if evidence_spans and not any(span.verified for span in evidence_spans):
            missing.append("Retrieved evidence could not be verified against the truth-pack.")
        if path_alignment_gap:
            missing.append(_PATH_ALIGNMENT_GAP_NOTE)
        if warning_evidence_hit:
            missing.append(_WARNING_EVIDENCE_NOTE)
        if not has_test_support:
            frontend_changed = any(is_frontend_code_path(path) for path in changed_paths)
            if frontend_changed and blast_radius.tests > 0:
                missing.append(_NO_FRONTEND_TEST_EVIDENCE_NOTE)
            else:
                missing.append(_NO_TEST_EVIDENCE_NOTE)
        if not any(span.source_type == SourceType.RUNBOOK for span in evidence_spans):
            missing.append(_NO_RUNBOOK_EVIDENCE_NOTE)
        if not twin_cases:
            missing.append(_NO_PRECEDENT_NOTE)
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

    def _support_score(self, evidence_spans: list[EvidenceSpan]) -> float:
        if not evidence_spans:
            return 0.0
        return mean(sorted((span.score for span in evidence_spans), reverse=True)[:3])
