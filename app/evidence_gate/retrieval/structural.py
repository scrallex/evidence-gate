"""Repository knowledge-base construction, persistence, and structural span search."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from evidence_gate.config import Settings
from evidence_gate.decision.models import SourceType
from evidence_gate.retrieval.repository import (
    DocumentRecord,
    SearchHit,
    iter_repository_files,
    scan_repository,
    tokenize,
)
from evidence_gate.structural.sidecar import ManifoldIndex, build_index, encode_text
from evidence_gate.verification.truth_pack import TruthPackEngine, TruthPackSpan, _span_id

KB_FORMAT_VERSION = 1
MAX_IN_MEMORY_KB = 8
_KB_CACHE: dict[tuple[str, str, str], "RepositoryKnowledgeBase"] = {}


@dataclass(slots=True)
class RepositoryKnowledgeBase:
    documents: list[DocumentRecord]
    spans: list[TruthPackSpan]
    truth_pack: TruthPackEngine


@dataclass(slots=True)
class RepositoryKnowledgeBaseMaterialization:
    knowledge_base: RepositoryKnowledgeBase
    repo_root: Path
    repo_fingerprint: str
    cache_dir: Path
    status: str
    file_count: int
    document_count: int
    span_count: int


@dataclass(slots=True)
class RepositoryKnowledgeBaseManifest:
    repo_root: Path
    repo_fingerprint: str
    settings_signature: str
    built_at: datetime | None
    cache_dir: Path
    file_count: int
    document_count: int
    span_count: int
    format_version: int


@dataclass(slots=True)
class RepositoryKnowledgeBaseStatus:
    repo_root: Path
    cache_dir: Path
    status: str
    built_at: datetime | None
    current_repo_fingerprint: str | None
    cached_repo_fingerprint: str | None
    current_file_count: int
    cached_file_count: int
    document_count: int
    span_count: int
    settings_match: bool


@dataclass(slots=True)
class RepositoryKnowledgeBaseRemoval:
    repo_root: Path
    cache_dir: Path
    action: str
    previous_status: str | None
    reason: str | None
    document_count: int
    span_count: int


@dataclass(slots=True)
class RepositoryKnowledgeBaseMaintenanceRun:
    ran_at: datetime
    dry_run: bool
    total_knowledge_bases: int
    removals: list[RepositoryKnowledgeBaseRemoval]
    stale_count: int
    expired_count: int
    overflow_count: int


@dataclass(slots=True)
class RawSpan:
    source: str
    text: str
    line_number: int | None


@dataclass(slots=True)
class RepositorySnapshotEntry:
    path: str
    size: int
    mtime_ns: int


@dataclass(slots=True)
class RepositorySnapshot:
    fingerprint: str
    entries: list[RepositorySnapshotEntry]


def clear_repository_knowledge_base_cache() -> None:
    """Clear the process-local repository knowledge-base cache."""

    _KB_CACHE.clear()


def build_repository_knowledge_base(
    repo_root: Path,
    settings: Settings,
    *,
    exclude_relative_prefixes: tuple[str, ...] | None = None,
) -> RepositoryKnowledgeBase:
    prefixes = exclude_relative_prefixes or _artifact_relative_prefixes(repo_root, settings)
    documents = scan_repository(repo_root, exclude_relative_prefixes=prefixes)
    return _build_repository_knowledge_base_from_documents(documents, settings)


def materialize_repository_knowledge_base(
    repo_root: Path,
    settings: Settings,
    *,
    force_refresh: bool = False,
) -> RepositoryKnowledgeBaseMaterialization:
    repo_root = repo_root.resolve()
    prefixes = _artifact_relative_prefixes(repo_root, settings)
    snapshot = _snapshot_repository(repo_root, exclude_relative_prefixes=prefixes)
    settings_signature = _knowledge_base_settings_signature(settings)
    cache_key = (str(repo_root), snapshot.fingerprint, settings_signature)
    cache_dir = _cache_dir_for_repo(repo_root, settings)

    if not force_refresh:
        cached = _KB_CACHE.get(cache_key)
        if cached is not None:
            return _materialization_result(
                cached,
                repo_root=repo_root,
                snapshot=snapshot,
                cache_dir=cache_dir,
                status="reused",
            )

        knowledge_base = _load_cached_repository_knowledge_base(
            cache_dir=cache_dir,
            repo_root=repo_root,
            snapshot=snapshot,
            settings=settings,
            settings_signature=settings_signature,
        )
        if knowledge_base is not None:
            _store_in_memory_cache(cache_key, knowledge_base)
            return _materialization_result(
                knowledge_base,
                repo_root=repo_root,
                snapshot=snapshot,
                cache_dir=cache_dir,
                status="reused",
            )

    knowledge_base = build_repository_knowledge_base(
        repo_root,
        settings,
        exclude_relative_prefixes=prefixes,
    )
    _persist_repository_knowledge_base(
        knowledge_base,
        cache_dir=cache_dir,
        repo_root=repo_root,
        snapshot=snapshot,
        settings_signature=settings_signature,
    )
    _store_in_memory_cache(cache_key, knowledge_base)
    return _materialization_result(
        knowledge_base,
        repo_root=repo_root,
        snapshot=snapshot,
        cache_dir=cache_dir,
        status="refreshed" if force_refresh else "built",
    )


def load_repository_knowledge_base(repo_root: Path, settings: Settings) -> RepositoryKnowledgeBase:
    return materialize_repository_knowledge_base(repo_root, settings).knowledge_base


def get_repository_knowledge_base_status(
    repo_root: Path,
    settings: Settings,
) -> RepositoryKnowledgeBaseStatus:
    repo_root = repo_root.resolve()
    snapshot = _snapshot_for_status(repo_root, settings)
    cache_dir = _cache_dir_for_repo(repo_root, settings)
    manifest = _load_repository_knowledge_base_manifest(cache_dir)
    if manifest is None:
        return RepositoryKnowledgeBaseStatus(
            repo_root=repo_root,
            cache_dir=cache_dir,
            status="missing",
            built_at=None,
            current_repo_fingerprint=snapshot.fingerprint,
            cached_repo_fingerprint=None,
            current_file_count=len(snapshot.entries),
            cached_file_count=0,
            document_count=0,
            span_count=0,
            settings_match=False,
        )
    return _status_from_manifest(manifest, settings, snapshot)


def list_repository_knowledge_bases(settings: Settings) -> list[RepositoryKnowledgeBaseStatus]:
    cache_root = _resolve_storage_root(settings.knowledge_root)
    if not cache_root.exists():
        return []

    statuses: list[RepositoryKnowledgeBaseStatus] = []
    for manifest_path in sorted(cache_root.rglob("manifest.json")):
        manifest = _load_repository_knowledge_base_manifest(manifest_path.parent)
        if manifest is None:
            continue
        snapshot = None
        if manifest.repo_root.exists() and manifest.repo_root.is_dir():
            snapshot = _snapshot_for_status(manifest.repo_root, settings)
        statuses.append(_status_from_manifest(manifest, settings, snapshot))

    statuses.sort(
        key=lambda status: (
            status.status != "ready",
            status.repo_root.as_posix(),
        )
    )
    return statuses


def delete_repository_knowledge_base(
    repo_root: Path,
    settings: Settings,
    *,
    dry_run: bool = False,
    reason: str | None = None,
) -> RepositoryKnowledgeBaseRemoval:
    repo_root = repo_root.resolve()
    cache_dir = _cache_dir_for_repo(repo_root, settings)
    manifest = _load_repository_knowledge_base_manifest(cache_dir)

    previous_status: str | None = "missing"
    document_count = 0
    span_count = 0
    if manifest is not None:
        snapshot = None
        if manifest.repo_root.exists() and manifest.repo_root.is_dir():
            snapshot = _snapshot_for_status(manifest.repo_root, settings)
        status = _status_from_manifest(manifest, settings, snapshot)
        previous_status = status.status
        document_count = status.document_count
        span_count = status.span_count

    if not cache_dir.exists():
        return RepositoryKnowledgeBaseRemoval(
            repo_root=repo_root,
            cache_dir=cache_dir,
            action="missing",
            previous_status=previous_status,
            reason=reason,
            document_count=document_count,
            span_count=span_count,
        )

    if dry_run:
        action = "would_delete"
    else:
        shutil.rmtree(cache_dir)
        _evict_in_memory_cache_for_repo(repo_root)
        action = "deleted"

    return RepositoryKnowledgeBaseRemoval(
        repo_root=repo_root,
        cache_dir=cache_dir,
        action=action,
        previous_status=previous_status,
        reason=reason,
        document_count=document_count,
        span_count=span_count,
    )


def prune_repository_knowledge_bases(
    settings: Settings,
    *,
    stale_only: bool = True,
    dry_run: bool = False,
) -> list[RepositoryKnowledgeBaseRemoval]:
    removals: list[RepositoryKnowledgeBaseRemoval] = []
    for status in list_repository_knowledge_bases(settings):
        if stale_only and status.status != "stale":
            continue
        removals.append(
            delete_repository_knowledge_base(
                status.repo_root,
                settings,
                dry_run=dry_run,
                reason="stale" if status.status == "stale" else None,
            )
        )
    return removals


def apply_repository_knowledge_base_retention(
    settings: Settings,
    *,
    dry_run: bool = False,
) -> RepositoryKnowledgeBaseMaintenanceRun:
    statuses = list_repository_knowledge_bases(settings)
    now = datetime.now(timezone.utc)
    reasons_by_repo: dict[str, tuple[str, RepositoryKnowledgeBaseStatus]] = {}
    maintenance = settings.maintenance

    for status in statuses:
        if status.status == "stale":
            reasons_by_repo[str(status.repo_root)] = ("stale", status)
            continue
        if (
            maintenance.max_age_hours is not None
            and status.built_at is not None
            and (now - status.built_at).total_seconds() >= maintenance.max_age_hours * 3600
        ):
            reasons_by_repo.setdefault(str(status.repo_root), ("expired", status))

    if maintenance.max_cache_entries is not None and len(statuses) > maintenance.max_cache_entries:
        ranked_statuses = sorted(
            statuses,
            key=lambda status: status.built_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        for status in ranked_statuses[maintenance.max_cache_entries :]:
            reasons_by_repo.setdefault(str(status.repo_root), ("overflow", status))

    removals: list[RepositoryKnowledgeBaseRemoval] = []
    reason_counts: Counter[str] = Counter()
    for reason, status in sorted(reasons_by_repo.values(), key=lambda item: item[1].repo_root.as_posix()):
        removals.append(
            delete_repository_knowledge_base(
                status.repo_root,
                settings,
                dry_run=dry_run,
                reason=reason,
            )
        )
        reason_counts[reason] += 1

    return RepositoryKnowledgeBaseMaintenanceRun(
        ran_at=now,
        dry_run=dry_run,
        total_knowledge_bases=len(statuses),
        removals=removals,
        stale_count=reason_counts.get("stale", 0),
        expired_count=reason_counts.get("expired", 0),
        overflow_count=reason_counts.get("overflow", 0),
    )


def search_repository(
    repo_root: Path,
    *,
    query: str,
    top_k: int,
    settings: Settings,
) -> list[SearchHit]:
    kb = load_repository_knowledge_base(repo_root, settings)
    match_limit = max(top_k * 4, 12)
    matches = kb.truth_pack.structural_search(query, top_k=match_limit)

    hits: list[SearchHit] = []
    seen_sources: set[str] = set()
    for match in matches:
        evaluation = kb.truth_pack.evaluate(match.span, query=query)
        span = match.span
        snippet = " ".join(span.text.strip().split())
        if not snippet:
            continue
        if span.source in seen_sources:
            continue
        seen_sources.add(span.source)
        score = min(
            1.0,
            0.45 * match.final_score
            + 0.25 * evaluation.coverage
            + 0.15 * span.patternability
            + 0.15 * evaluation.semantic_similarity,
        )
        hits.append(
            SearchHit(
                path=span.source,
                source_type=span.source_type,
                score=score,
                snippet=snippet[:240],
                line_number=span.line_number,
                verified=evaluation.verified,
            )
        )

    hits.sort(key=lambda hit: (hit.verified, hit.score), reverse=True)
    return hits[: max(top_k * 2, settings.thresholds.top_k_evidence + settings.thresholds.top_k_twins)]


def _build_repository_knowledge_base_from_documents(
    documents: list[DocumentRecord],
    settings: Settings,
) -> RepositoryKnowledgeBase:
    spans = _build_truth_pack_spans(documents, settings)
    sidecar_index = build_index(
        {span.span_id: span.text for span in spans},
        window_bytes=settings.thresholds.structural_window_bytes,
        stride_bytes=settings.thresholds.structural_stride_bytes,
        precision=settings.thresholds.structural_precision,
        hazard_percentile=settings.thresholds.structural_hazard_percentile,
    )
    truth_pack = TruthPackEngine(
        spans=spans,
        sidecar_index=sidecar_index,
        coverage_threshold=settings.thresholds.verification_coverage_threshold,
        semantic_threshold=settings.thresholds.verification_semantic_threshold,
        structural_threshold=settings.thresholds.verification_structural_threshold,
    )
    return RepositoryKnowledgeBase(documents=documents, spans=spans, truth_pack=truth_pack)


def _materialization_result(
    knowledge_base: RepositoryKnowledgeBase,
    *,
    repo_root: Path,
    snapshot: RepositorySnapshot,
    cache_dir: Path,
    status: str,
) -> RepositoryKnowledgeBaseMaterialization:
    return RepositoryKnowledgeBaseMaterialization(
        knowledge_base=knowledge_base,
        repo_root=repo_root,
        repo_fingerprint=snapshot.fingerprint,
        cache_dir=cache_dir,
        status=status,
        file_count=len(snapshot.entries),
        document_count=len(knowledge_base.documents),
        span_count=len(knowledge_base.spans),
    )


def _store_in_memory_cache(
    cache_key: tuple[str, str, str],
    knowledge_base: RepositoryKnowledgeBase,
) -> None:
    if len(_KB_CACHE) >= MAX_IN_MEMORY_KB:
        _KB_CACHE.clear()
    _KB_CACHE[cache_key] = knowledge_base


def _evict_in_memory_cache_for_repo(repo_root: Path) -> None:
    repo_key = str(repo_root.resolve())
    stale_keys = [cache_key for cache_key in _KB_CACHE if cache_key[0] == repo_key]
    for cache_key in stale_keys:
        _KB_CACHE.pop(cache_key, None)


def _artifact_relative_prefixes(repo_root: Path, settings: Settings) -> tuple[str, ...]:
    repo_root = repo_root.resolve()
    prefixes: set[str] = set()
    for artifact_root in (settings.audit_root, settings.knowledge_root):
        resolved_root = _resolve_storage_root(artifact_root)
        try:
            relative = resolved_root.relative_to(repo_root)
        except ValueError:
            continue
        relative_path = relative.as_posix()
        if relative_path and relative_path != ".":
            prefixes.add(relative_path)
    return tuple(sorted(prefixes))


def _snapshot_for_status(repo_root: Path, settings: Settings) -> RepositorySnapshot:
    prefixes = _artifact_relative_prefixes(repo_root, settings)
    return _snapshot_repository(repo_root, exclude_relative_prefixes=prefixes)


def _resolve_storage_root(path: Path) -> Path:
    root = path.expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _snapshot_repository(
    repo_root: Path,
    *,
    exclude_relative_prefixes: tuple[str, ...],
) -> RepositorySnapshot:
    entries: list[RepositorySnapshotEntry] = []
    digest = hashlib.blake2b(digest_size=16)
    for path in iter_repository_files(repo_root, exclude_relative_prefixes=exclude_relative_prefixes):
        stat = path.stat()
        rel_path = path.relative_to(repo_root).as_posix()
        entry = RepositorySnapshotEntry(
            path=rel_path,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )
        entries.append(entry)
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry.size).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry.mtime_ns).encode("utf-8"))
        digest.update(b"\n")
    return RepositorySnapshot(fingerprint=digest.hexdigest(), entries=entries)


def _knowledge_base_settings_signature(settings: Settings) -> str:
    thresholds = settings.thresholds
    payload = (
        KB_FORMAT_VERSION,
        thresholds.structural_window_bytes,
        thresholds.structural_stride_bytes,
        thresholds.structural_precision,
        thresholds.structural_hazard_percentile,
    )
    return hashlib.blake2b(repr(payload).encode("utf-8"), digest_size=16).hexdigest()


def _cache_dir_for_repo(repo_root: Path, settings: Settings) -> Path:
    cache_root = _resolve_storage_root(settings.knowledge_root)
    repo_key = hashlib.blake2b(str(repo_root).encode("utf-8"), digest_size=12).hexdigest()
    return cache_root / repo_key


def _artifact_paths(cache_dir: Path) -> dict[str, Path]:
    return {
        "manifest": cache_dir / "manifest.json",
        "documents": cache_dir / "documents.json",
        "spans": cache_dir / "spans.json",
        "sidecar": cache_dir / "sidecar.json",
    }


def _manifest_matches(
    manifest: dict[str, object],
    *,
    repo_root: Path,
    snapshot: RepositorySnapshot,
    settings_signature: str,
) -> bool:
    return (
        manifest.get("format_version") == KB_FORMAT_VERSION
        and manifest.get("repo_root") == str(repo_root)
        and manifest.get("repo_fingerprint") == snapshot.fingerprint
        and manifest.get("settings_signature") == settings_signature
    )


def _load_cached_repository_knowledge_base(
    *,
    cache_dir: Path,
    repo_root: Path,
    snapshot: RepositorySnapshot,
    settings: Settings,
    settings_signature: str,
) -> RepositoryKnowledgeBase | None:
    paths = _artifact_paths(cache_dir)
    if not paths["manifest"].exists():
        return None

    try:
        manifest = _read_json(paths["manifest"])
        if not _manifest_matches(
            manifest,
            repo_root=repo_root,
            snapshot=snapshot,
            settings_signature=settings_signature,
        ):
            return None
        documents_payload = _read_json(paths["documents"])
        spans_payload = _read_json(paths["spans"])
        sidecar_payload = _read_json(paths["sidecar"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None

    documents = [_document_from_payload(item) for item in documents_payload]
    spans = [_span_from_payload(item) for item in spans_payload]
    sidecar_index = ManifoldIndex(
        meta=dict(sidecar_payload["meta"]),
        signatures=dict(sidecar_payload["signatures"]),
        documents=dict(sidecar_payload["documents"]),
    )
    truth_pack = TruthPackEngine(
        spans=spans,
        sidecar_index=sidecar_index,
        coverage_threshold=settings.thresholds.verification_coverage_threshold,
        semantic_threshold=settings.thresholds.verification_semantic_threshold,
        structural_threshold=settings.thresholds.verification_structural_threshold,
    )
    return RepositoryKnowledgeBase(documents=documents, spans=spans, truth_pack=truth_pack)


def _load_repository_knowledge_base_manifest(cache_dir: Path) -> RepositoryKnowledgeBaseManifest | None:
    manifest_path = _artifact_paths(cache_dir)["manifest"]
    if not manifest_path.exists():
        return None
    try:
        manifest = _read_json(manifest_path)
        if not isinstance(manifest, dict):
            return None
        built_at_raw = manifest.get("built_at")
        built_at = datetime.fromisoformat(str(built_at_raw)) if built_at_raw else None
        repo_root = Path(str(manifest["repo_root"])).expanduser().resolve()
        return RepositoryKnowledgeBaseManifest(
            repo_root=repo_root,
            repo_fingerprint=str(manifest["repo_fingerprint"]),
            settings_signature=str(manifest["settings_signature"]),
            built_at=built_at,
            cache_dir=cache_dir,
            file_count=int(manifest.get("file_count", 0)),
            document_count=int(manifest.get("document_count", 0)),
            span_count=int(manifest.get("span_count", 0)),
            format_version=int(manifest.get("format_version", 0)),
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _status_from_manifest(
    manifest: RepositoryKnowledgeBaseManifest,
    settings: Settings,
    snapshot: RepositorySnapshot | None,
) -> RepositoryKnowledgeBaseStatus:
    settings_signature = _knowledge_base_settings_signature(settings)
    settings_match = (
        manifest.format_version == KB_FORMAT_VERSION
        and manifest.settings_signature == settings_signature
    )
    current_repo_fingerprint = snapshot.fingerprint if snapshot is not None else None
    current_file_count = len(snapshot.entries) if snapshot is not None else 0
    status = "ready"
    if snapshot is None or current_repo_fingerprint != manifest.repo_fingerprint or not settings_match:
        status = "stale"
    return RepositoryKnowledgeBaseStatus(
        repo_root=manifest.repo_root,
        cache_dir=manifest.cache_dir,
        status=status,
        built_at=manifest.built_at,
        current_repo_fingerprint=current_repo_fingerprint,
        cached_repo_fingerprint=manifest.repo_fingerprint,
        current_file_count=current_file_count,
        cached_file_count=manifest.file_count,
        document_count=manifest.document_count,
        span_count=manifest.span_count,
        settings_match=settings_match,
    )


def _persist_repository_knowledge_base(
    knowledge_base: RepositoryKnowledgeBase,
    *,
    cache_dir: Path,
    repo_root: Path,
    snapshot: RepositorySnapshot,
    settings_signature: str,
) -> None:
    paths = _artifact_paths(cache_dir)
    documents_payload = [_document_to_payload(document) for document in knowledge_base.documents]
    spans_payload = [_span_to_payload(span) for span in knowledge_base.spans]
    sidecar_payload = {
        "meta": knowledge_base.truth_pack.sidecar_index.meta,
        "signatures": knowledge_base.truth_pack.sidecar_index.signatures,
        "documents": knowledge_base.truth_pack.sidecar_index.documents,
    }
    manifest = {
        "format_version": KB_FORMAT_VERSION,
        "repo_root": str(repo_root),
        "repo_fingerprint": snapshot.fingerprint,
        "settings_signature": settings_signature,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(snapshot.entries),
        "document_count": len(knowledge_base.documents),
        "span_count": len(knowledge_base.spans),
        "snapshot": [_snapshot_entry_to_payload(entry) for entry in snapshot.entries],
        "artifacts": {
            name: path.name
            for name, path in paths.items()
            if name != "manifest"
        },
    }
    _write_json(paths["documents"], documents_payload)
    _write_json(paths["spans"], spans_payload)
    _write_json(paths["sidecar"], sidecar_payload)
    _write_json(paths["manifest"], manifest)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path) -> dict[str, object] | list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot_entry_to_payload(entry: RepositorySnapshotEntry) -> dict[str, object]:
    return {
        "path": entry.path,
        "size": entry.size,
        "mtime_ns": entry.mtime_ns,
    }


def _document_to_payload(document: DocumentRecord) -> dict[str, object]:
    return {
        "path": document.path,
        "source_type": document.source_type.value,
        "content": document.content,
    }


def _document_from_payload(payload: dict[str, object]) -> DocumentRecord:
    path = str(payload["path"])
    content = str(payload["content"])
    return DocumentRecord(
        path=path,
        source_type=SourceType(str(payload["source_type"])),
        content=content,
        lines=tuple(content.splitlines()),
        token_counts=Counter(tokenize(content)),
        path_token_counts=Counter(tokenize(path.replace("/", " "))),
    )


def _span_to_payload(span: TruthPackSpan) -> dict[str, object]:
    return {
        "span_id": span.span_id,
        "source": span.source,
        "source_type": span.source_type.value,
        "line_number": span.line_number,
        "text": span.text,
        "search_text": span.search_text,
        "occurrences": span.occurrences,
        "patternability": span.patternability,
        "coherence": span.coherence,
        "stability": span.stability,
        "entropy": span.entropy,
        "rupture": span.rupture,
        "hazard": span.hazard,
        "signature": span.signature,
    }


def _span_from_payload(payload: dict[str, object]) -> TruthPackSpan:
    search_text = str(payload["search_text"])
    return TruthPackSpan(
        span_id=str(payload["span_id"]),
        source=str(payload["source"]),
        source_type=SourceType(str(payload["source_type"])),
        line_number=int(payload["line_number"]) if payload["line_number"] is not None else None,
        text=str(payload["text"]),
        search_text=search_text,
        occurrences=int(payload["occurrences"]),
        patternability=float(payload["patternability"]),
        coherence=float(payload["coherence"]),
        stability=float(payload["stability"]),
        entropy=float(payload["entropy"]),
        rupture=float(payload["rupture"]),
        hazard=float(payload["hazard"]),
        signature=str(payload["signature"]) if payload["signature"] is not None else None,
        qgrams=_build_qgrams(search_text),
        hash_vector=_hash_search_vector(search_text),
    )


def _build_truth_pack_spans(documents: list[DocumentRecord], settings: Settings) -> list[TruthPackSpan]:
    raw_spans: list[tuple[DocumentRecord, RawSpan]] = []
    for document in documents:
        for raw_span in _extract_document_spans(document):
            raw_spans.append((document, raw_span))

    occurrence_counts: dict[str, int] = {}
    for _document, raw_span in raw_spans:
        key = " ".join(raw_span.text.strip().lower().split())
        if not key:
            continue
        occurrence_counts[key] = occurrence_counts.get(key, 0) + 1

    spans: list[TruthPackSpan] = []
    for document, raw_span in raw_spans:
        norm_key = " ".join(raw_span.text.strip().lower().split())
        if not norm_key:
            continue
        encoded = encode_text(
            raw_span.text,
            window_bytes=settings.thresholds.structural_window_bytes,
            stride_bytes=settings.thresholds.structural_stride_bytes,
            precision=settings.thresholds.structural_precision,
            hazard_percentile=settings.thresholds.structural_hazard_percentile,
        )
        if encoded.windows:
            coherence = sum(window.coherence for window in encoded.windows) / len(encoded.windows)
            stability = sum(window.stability for window in encoded.windows) / len(encoded.windows)
            entropy = sum(window.entropy for window in encoded.windows) / len(encoded.windows)
            hazard = sum(window.hazard for window in encoded.windows) / len(encoded.windows)
            signature = encoded.windows[0].signature
        else:
            coherence = 0.0
            stability = 0.0
            entropy = 1.0
            hazard = 1.0
            signature = None
        patternability = max(0.0, min(1.0, 1.0 - hazard))
        rupture = hazard
        search_text = f"{document.path} {document.source_type.value} {raw_span.text}"
        spans.append(
            TruthPackSpan(
                span_id=_span_id(raw_span.text, document.path, raw_span.line_number),
                source=document.path,
                source_type=document.source_type,
                line_number=raw_span.line_number,
                text=raw_span.text,
                search_text=search_text,
                occurrences=occurrence_counts.get(norm_key, 1),
                patternability=patternability,
                coherence=coherence,
                stability=stability,
                entropy=entropy,
                rupture=rupture,
                hazard=hazard,
                signature=signature,
                qgrams=_build_qgrams(search_text),
                hash_vector=_hash_search_vector(search_text),
            )
        )

    return spans


def _extract_document_spans(document: DocumentRecord) -> list[RawSpan]:
    spans: list[RawSpan] = []
    non_empty_lines = [(index, line.strip()) for index, line in enumerate(document.lines, start=1) if line.strip()]
    if not non_empty_lines:
        return spans

    summary_lines = [line for _, line in non_empty_lines[:8]]
    summary_text = "\n".join([document.path, document.source_type.value, *summary_lines])
    spans.append(RawSpan(source=document.path, text=summary_text, line_number=non_empty_lines[0][0]))

    if document.source_type.value in {"doc", "runbook", "pr", "incident", "other"}:
        spans.extend(_paragraph_spans(document))
    else:
        spans.extend(_code_block_spans(document))

    return spans


def _paragraph_spans(document: DocumentRecord) -> list[RawSpan]:
    spans: list[RawSpan] = []
    buffer: list[str] = []
    start_line: int | None = None
    for index, line in enumerate(document.lines, start=1):
        stripped = line.strip()
        if stripped:
            if start_line is None:
                start_line = index
            buffer.append(stripped)
            continue
        if buffer and start_line is not None:
            spans.append(RawSpan(source=document.path, text="\n".join(buffer), line_number=start_line))
        buffer = []
        start_line = None
    if buffer and start_line is not None:
        spans.append(RawSpan(source=document.path, text="\n".join(buffer), line_number=start_line))
    return spans


def _code_block_spans(document: DocumentRecord) -> list[RawSpan]:
    spans: list[RawSpan] = []
    buffer: list[str] = []
    start_line: int | None = None
    for index, line in enumerate(document.lines, start=1):
        if line.strip():
            if start_line is None:
                start_line = index
            buffer.append(line.rstrip())
            continue
        if buffer and start_line is not None:
            spans.append(RawSpan(source=document.path, text="\n".join(buffer), line_number=start_line))
        buffer = []
        start_line = None
    if buffer and start_line is not None:
        spans.append(RawSpan(source=document.path, text="\n".join(buffer), line_number=start_line))
    return spans


def _build_qgrams(text: str) -> set[str]:
    from evidence_gate.verification.truth_pack import _qgrams

    return _qgrams(text, 3)


def _hash_search_vector(text: str) -> dict[int, float]:
    from evidence_gate.verification.truth_pack import _hash_vector

    return _hash_vector(text)
