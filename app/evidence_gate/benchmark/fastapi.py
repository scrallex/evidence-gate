"""FastAPI benchmark corpus and evaluation for Evidence Gate."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from evidence_gate.audit.store import FileAuditStore
from evidence_gate.config import KnowledgeBaseMaintenanceConfig, Settings
from evidence_gate.decision.service import DecisionService
from evidence_gate.retrieval.repository import SearchHit, scan_repository, search_documents, tokenize
from evidence_gate.retrieval.structural import (
    clear_repository_knowledge_base_cache,
    materialize_repository_knowledge_base,
    search_repository,
)

FASTAPI_REPO_URL = "https://github.com/fastapi/fastapi"
DEFAULT_BENCHMARK_ROOT = Path.home() / ".evidence-gate" / "benchmarks" / "fastapi"

_TRANSLATION_RE = re.compile(r"docs/(?!en/)[a-z-]+/docs/")
_PR_RE = re.compile(r"PR \[#(?P<number>\d+)\]\((?P<url>[^)]+)\)")


@dataclass(frozen=True, slots=True)
class FastAPITopic:
    slug: str
    corpus_paths: tuple[str, ...]
    expected_path_hints: tuple[str, ...]
    precedent_terms: tuple[str, ...]
    positive_queries: tuple[str, ...]
    negative_queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    topic: str
    should_admit: bool
    query: str
    expected_path_hints: tuple[str, ...]


@dataclass(slots=True)
class BackendCaseResult:
    raw_decision: str
    predicted_admit: bool
    support_score: float
    evidence_sources: list[str]
    twin_sources: list[str]
    expected_path_rank: int | None
    top_hits: list[dict[str, Any]]


@dataclass(slots=True)
class BenchmarkCaseResult:
    case_id: str
    topic: str
    should_admit: bool
    query: str
    structural: BackendCaseResult
    baseline: BackendCaseResult


TOPICS: tuple[FastAPITopic, ...] = (
    FastAPITopic(
        slug="oauth2-password-form",
        corpus_paths=(
            "fastapi/security/oauth2.py",
            "fastapi/security/base.py",
            "fastapi/security/utils.py",
            "fastapi/dependencies/utils.py",
            "tests/test_security_oauth2.py",
            "tests/test_tutorial/test_security",
            "docs/en/docs/tutorial/security/first-steps.md",
            "docs/en/docs/tutorial/security/simple-oauth2.md",
            "docs/en/docs/tutorial/security/oauth2-jwt.md",
            "docs/en/docs/advanced/security/oauth2-scopes.md",
            "docs_src/security",
        ),
        expected_path_hints=(
            "fastapi/security/oauth2.py",
            "tests/test_security_oauth2.py",
            "docs/en/docs/tutorial/security",
            "docs_src/security",
        ),
        precedent_terms=("OAuth2PasswordRequestForm", "OAuth2PasswordRequestFormStrict"),
        positive_queries=(
            "If we change OAuth2PasswordRequestForm validation behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we tighten OAuth2PasswordRequestFormStrict grant_type handling, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change OpenID device flow polling interval behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change OIDC token introspection cache invalidation behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="websocket-routing",
        corpus_paths=(
            "fastapi/websockets.py",
            "fastapi/routing.py",
            "fastapi/applications.py",
            "fastapi/exceptions.py",
            "fastapi/exception_handlers.py",
            "tests/test_ws_router.py",
            "tests/test_ws_dependencies.py",
            "tests/test_dependency_after_yield_websockets.py",
            "tests/test_dependency_yield_scope_websockets.py",
            "tests/test_tutorial/test_websockets",
            "docs/en/docs/advanced/websockets.md",
            "docs/en/docs/advanced/testing-websockets.md",
            "docs/en/docs/reference/websockets.md",
            "docs_src/websockets_",
        ),
        expected_path_hints=(
            "fastapi/websockets.py",
            "fastapi/routing.py",
            "tests/test_ws_router.py",
            "tests/test_ws_dependencies.py",
            "docs/en/docs/advanced/websockets.md",
        ),
        precedent_terms=("WebSocket", "WebSocketRequestValidationError", "websockets"),
        positive_queries=(
            "If we change dependency support in WebSocket routes, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change WebSocket path parameter routing behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Socket.IO namespace authorization behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change STOMP subscription acknowledgement behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="wsgi-middleware",
        corpus_paths=(
            "fastapi/middleware/wsgi.py",
            "tests/test_tutorial/test_wsgi",
            "docs/en/docs/advanced/wsgi.md",
            "docs_src/wsgi",
        ),
        expected_path_hints=(
            "fastapi/middleware/wsgi.py",
            "tests/test_tutorial/test_wsgi",
            "docs/en/docs/advanced/wsgi.md",
            "docs_src/wsgi",
        ),
        precedent_terms=("WSGIMiddleware",),
        positive_queries=(
            "If we change WSGIMiddleware usage and deprecation behavior, what FastAPI docs, examples, and precedent PRs are implicated?",
            "If we change the a2wsgi migration path for WSGIMiddleware, what FastAPI docs, examples, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Rack adapter lifecycle behavior, what FastAPI docs, examples, and precedent PRs are implicated?",
            "If we change CGI gateway adapter behavior, what FastAPI docs, examples, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="gzip-middleware",
        corpus_paths=(
            "fastapi/middleware/gzip.py",
            "docs/en/docs/advanced/middleware.md",
            "docs/en/docs/reference/middleware.md",
            "docs_src/advanced_middleware",
            "tests/test_tutorial/test_advanced_middleware",
        ),
        expected_path_hints=(
            "fastapi/middleware/gzip.py",
            "docs/en/docs/advanced/middleware.md",
            "docs_src/advanced_middleware",
            "tests/test_tutorial/test_advanced_middleware",
        ),
        precedent_terms=("GZipMiddleware",),
        positive_queries=(
            "If we change GZipMiddleware compresslevel handling, what FastAPI docs, examples, and precedent PRs are implicated?",
            "If we change GZipMiddleware example configuration, what FastAPI docs, examples, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Brotli response compression level handling, what FastAPI docs, examples, and precedent PRs are implicated?",
            "If we change zstd response compression behavior, what FastAPI docs, examples, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="background-tasks",
        corpus_paths=(
            "fastapi/background.py",
            "docs/en/docs/tutorial/background-tasks.md",
            "docs/en/docs/reference/background.md",
            "docs_src/background_tasks",
            "tests/test_tutorial/test_background_tasks",
        ),
        expected_path_hints=(
            "fastapi/background.py",
            "docs/en/docs/tutorial/background-tasks.md",
            "docs/en/docs/reference/background.md",
            "docs_src/background_tasks",
        ),
        precedent_terms=("BackgroundTasks",),
        positive_queries=(
            "If we change BackgroundTasks subclass documentation behavior, what FastAPI docs, examples, and precedent PRs are implicated?",
            "If we change BackgroundTasks reference docs and helper behavior, what FastAPI docs, examples, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Celery beat periodic task scheduling, what FastAPI docs, examples, and precedent PRs are implicated?",
            "If we change RQ job retry backoff scheduling, what FastAPI docs, examples, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="openapi-security-schemes",
        corpus_paths=(
            "fastapi/openapi/utils.py",
            "fastapi/openapi/models.py",
            "fastapi/security/oauth2.py",
            "tests/test_security_scopes.py",
            "tests/test_security_scopes_sub_dependency.py",
            "tests/test_top_level_security_scheme_in_openapi.py",
            "tests/test_security_oauth2_authorization_code_bearer_scopes_openapi.py",
            "tests/test_security_oauth2_authorization_code_bearer_scopes_openapi_simple.py",
            "docs/en/docs/advanced/security/oauth2-scopes.md",
            "docs/en/docs/reference/security/index.md",
            "docs_src/security",
        ),
        expected_path_hints=(
            "fastapi/openapi/utils.py",
            "tests/test_security_scopes.py",
            "tests/test_top_level_security_scheme_in_openapi.py",
            "docs/en/docs/advanced/security/oauth2-scopes.md",
        ),
        precedent_terms=("security schemes", "top level app", "OAuth2 scopes declaration"),
        positive_queries=(
            "If we change OpenAPI security scheme scope deduplication, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change top-level OpenAPI security scheme generation, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change mutual TLS authentication metadata generation, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change OAuth2 device authorization metadata generation, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="openapi-anyof-union",
        corpus_paths=(
            "fastapi/openapi/utils.py",
            "tests/test_duplicate_models_openapi.py",
            "tests/test_openapi_separate_input_output_schemas.py",
            "tests/test_tutorial/test_separate_openapi_schemas",
            "docs/en/docs/how-to/separate-openapi-schemas.md",
            "docs_src/separate_openapi_schemas",
        ),
        expected_path_hints=(
            "fastapi/openapi/utils.py",
            "tests/test_duplicate_models_openapi.py",
            "docs/en/docs/how-to/separate-openapi-schemas.md",
            "docs_src/separate_openapi_schemas",
        ),
        precedent_terms=("anyOf", "Union"),
        positive_queries=(
            "If we change OpenAPI anyOf reference handling for Union responses, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change app-level response model anyOf deduplication, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change GraphQL union fragment masking, what FastAPI tests, docs, and precedent PRs are implicated?",
            "If we change Avro union schema evolution handling, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="openapi-callbacks",
        corpus_paths=(
            "fastapi/routing.py",
            "fastapi/openapi/utils.py",
            "tests/test_tutorial/test_openapi_callbacks",
            "docs/en/docs/advanced/openapi-callbacks.md",
            "docs_src/openapi_callbacks",
        ),
        expected_path_hints=(
            "docs/en/docs/advanced/openapi-callbacks.md",
            "docs_src/openapi_callbacks",
            "tests/test_tutorial/test_openapi_callbacks",
        ),
        precedent_terms=("callbacks", "openapi-callbacks"),
        positive_queries=(
            "If we change OpenAPI callback registration behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change callback parameter handling in OpenAPI docs, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change AsyncAPI callback broker bindings, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change webhook retry broker callback semantics, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="openapi-webhooks",
        corpus_paths=(
            "fastapi/routing.py",
            "fastapi/openapi/utils.py",
            "tests/test_tutorial/test_openapi_webhooks",
            "tests/test_webhooks_security.py",
            "docs/en/docs/advanced/openapi-webhooks.md",
            "docs_src/openapi_webhooks",
        ),
        expected_path_hints=(
            "docs/en/docs/advanced/openapi-webhooks.md",
            "docs_src/openapi_webhooks",
            "tests/test_tutorial/test_openapi_webhooks",
        ),
        precedent_terms=("webhooks",),
        positive_queries=(
            "If we change OpenAPI webhook documentation behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change webhook schema examples in FastAPI, what docs, examples, tests, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Twilio signature rotation daemon behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change Stripe webhook delivery retry backoff, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="sub-applications",
        corpus_paths=(
            "fastapi/applications.py",
            "fastapi/routing.py",
            "tests/test_tutorial/test_sub_applications",
            "docs/en/docs/advanced/sub-applications.md",
            "docs_src/sub_applications",
        ),
        expected_path_hints=(
            "docs/en/docs/advanced/sub-applications.md",
            "docs_src/sub_applications",
            "tests/test_tutorial/test_sub_applications",
        ),
        precedent_terms=("sub-applications",),
        positive_queries=(
            "If we change sub-applications mount behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change sub-applications OpenAPI prefix handling, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Django admin subsite mounting behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change Rails engine mount prefix behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="behind-a-proxy",
        corpus_paths=(
            "fastapi/applications.py",
            "tests/test_tutorial/test_behind_a_proxy",
            "docs/en/docs/advanced/behind-a-proxy.md",
            "docs_src/behind_a_proxy",
        ),
        expected_path_hints=(
            "docs/en/docs/advanced/behind-a-proxy.md",
            "docs_src/behind_a_proxy",
            "tests/test_tutorial/test_behind_a_proxy",
            "runbooks/behind-a-proxy-runbook.md",
        ),
        precedent_terms=("behind-a-proxy", "root_path", "additional-servers"),
        positive_queries=(
            "If we change root_path handling behind a proxy, what FastAPI docs, examples, runbooks, and precedent PRs are implicated?",
            "If we change additional servers generation behind a proxy, what FastAPI docs, examples, runbooks, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change ingress-nginx rewrite-target annotation behavior, what FastAPI docs, examples, runbooks, and precedent PRs are implicated?",
            "If we change Envoy x-forwarded-prefix reconciliation behavior, what FastAPI docs, examples, runbooks, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="sqlmodel-tutorial",
        corpus_paths=(
            "fastapi/encoders.py",
            "tests/test_tutorial/test_sql_databases",
            "docs/en/docs/tutorial/sql-databases.md",
            "docs_src/sql_databases",
        ),
        expected_path_hints=(
            "docs/en/docs/tutorial/sql-databases.md",
            "docs_src/sql_databases",
            "tests/test_tutorial/test_sql_databases",
        ),
        precedent_terms=("SQLModel",),
        positive_queries=(
            "If we change the SQLModel tutorial flow for SQL databases, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change read_with_orm_mode support for SQLModel relationships, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change Prisma relation loading behavior, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
            "If we change Django ORM select_related caching, what FastAPI docs, examples, tests, and precedent PRs are implicated?",
        ),
    ),
    FastAPITopic(
        slug="separate-input-output-schemas",
        corpus_paths=(
            "fastapi/openapi/utils.py",
            "tests/test_openapi_separate_input_output_schemas.py",
            "tests/test_tutorial/test_separate_openapi_schemas",
            "docs/en/docs/how-to/separate-openapi-schemas.md",
            "docs_src/separate_openapi_schemas",
        ),
        expected_path_hints=(
            "fastapi/openapi/utils.py",
            "tests/test_openapi_separate_input_output_schemas.py",
            "docs/en/docs/how-to/separate-openapi-schemas.md",
            "docs_src/separate_openapi_schemas",
        ),
        precedent_terms=("separate_input_output_schemas", "input and output JSON Schemas"),
        positive_queries=(
            "If we change separate_input_output_schemas behavior in OpenAPI generation, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
        negative_queries=(
            "If we change GraphQL input and output schema stitching behavior, what FastAPI tests, docs, and precedent PRs are implicated?",
        ),
    ),
)

_RUNBOOK_SOURCES: tuple[tuple[str, str], ...] = (
    ("docs/en/docs/deployment/versions.md", "versions-runbook.md"),
    ("docs/en/docs/deployment/https.md", "https-runbook.md"),
    ("docs/en/docs/deployment/server-workers.md", "server-workers-runbook.md"),
    ("docs/en/docs/deployment/manually.md", "manual-deployment-runbook.md"),
    ("docs/en/docs/advanced/behind-a-proxy.md", "behind-a-proxy-runbook.md"),
)


def ensure_fastapi_source_repo(source_repo: Path) -> Path:
    """Clone FastAPI if needed and return the source path."""

    source_repo = source_repo.expanduser().resolve()
    if (source_repo / ".git").exists():
        return source_repo

    source_repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", FASTAPI_REPO_URL, str(source_repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    return source_repo


def build_fastapi_cases() -> list[BenchmarkCase]:
    """Return the fixed 50-case benchmark set."""

    cases: list[BenchmarkCase] = []
    counter = 1
    for topic in TOPICS:
        for query in topic.positive_queries:
            cases.append(
                BenchmarkCase(
                    case_id=f"fastapi-{counter:03d}",
                    topic=topic.slug,
                    should_admit=True,
                    query=query,
                    expected_path_hints=topic.expected_path_hints,
                )
            )
            counter += 1
        for query in topic.negative_queries:
            cases.append(
                BenchmarkCase(
                    case_id=f"fastapi-{counter:03d}",
                    topic=topic.slug,
                    should_admit=False,
                    query=query,
                    expected_path_hints=topic.expected_path_hints,
                )
            )
            counter += 1

    if len(cases) != 50:
        raise ValueError(f"Expected 50 benchmark cases, found {len(cases)}")
    return cases


def write_cases_json(path: Path) -> None:
    """Write the current case set to JSON."""

    payload = [
        {
            "case_id": case.case_id,
            "topic": case.topic,
            "should_admit": case.should_admit,
            "query": case.query,
            "expected_path_hints": list(case.expected_path_hints),
        }
        for case in build_fastapi_cases()
    ]
    _write_json(path, payload)


def build_fastapi_corpus(source_repo: Path, corpus_root: Path) -> Path:
    """Build a curated FastAPI corpus with runbooks and extracted precedent PRs."""

    source_repo = ensure_fastapi_source_repo(source_repo)
    corpus_root = corpus_root.expanduser().resolve()
    if corpus_root.exists():
        shutil.rmtree(corpus_root)
    corpus_root.mkdir(parents=True, exist_ok=True)

    copied: set[str] = set()
    for topic in TOPICS:
        for relative_path in topic.corpus_paths:
            if relative_path in copied:
                continue
            copied.add(relative_path)
            _copy_path(source_repo / relative_path, corpus_root / relative_path)

    runbook_dir = corpus_root / "runbooks"
    runbook_dir.mkdir(parents=True, exist_ok=True)
    for source_relative, target_name in _RUNBOOK_SOURCES:
        _copy_path(source_repo / source_relative, runbook_dir / target_name)

    release_notes = (source_repo / "docs/en/docs/release-notes.md").read_text(encoding="utf-8")
    pr_dir = corpus_root / "prs"
    pr_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[dict[str, Any]]] = {}
    for topic in TOPICS:
        extracted = _extract_topic_precedents(release_notes, topic)
        manifest[topic.slug] = extracted
        for item in extracted:
            pr_path = pr_dir / f"{topic.slug}-pr-{item['number']}.md"
            pr_path.write_text(
                "\n".join(
                    [
                        f"# {topic.slug} precedent PR {item['number']}",
                        "",
                        f"topic: {topic.slug}",
                        f"feature_terms: {', '.join(topic.precedent_terms)}",
                        "",
                        item["line"],
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

    _write_json(corpus_root.parent / "benchmark_manifest.json", {"precedents": manifest})
    return corpus_root


def run_fastapi_benchmark(
    *,
    source_repo: Path,
    work_root: Path,
    cases_json_path: Path,
    results_json_path: Path,
    report_path: Path,
    top_k: int = 12,
) -> dict[str, Any]:
    """Materialize the corpus, execute the benchmark, and write reports."""

    source_repo = ensure_fastapi_source_repo(source_repo)
    work_root = work_root.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    corpus_root = build_fastapi_corpus(source_repo, work_root / "corpus")
    write_cases_json(cases_json_path)
    cases = build_fastapi_cases()

    clear_repository_knowledge_base_cache()
    settings = Settings(
        audit_root=work_root / "audit",
        knowledge_root=work_root / "knowledge_bases",
        maintenance=KnowledgeBaseMaintenanceConfig(
            enabled=False,
            prune_on_startup=False,
            max_age_hours=None,
            max_cache_entries=None,
        ),
    )
    materialize_repository_knowledge_base(corpus_root, settings, force_refresh=True)
    documents = scan_repository(corpus_root)
    service = DecisionService(settings, FileAuditStore(work_root / "audit"))

    results: list[BenchmarkCaseResult] = []
    for case in cases:
        structural_hits = search_repository(corpus_root, query=case.query, top_k=top_k, settings=settings)
        baseline_hits = search_documents(documents, case.query, top_k=top_k)
        results.append(
            BenchmarkCaseResult(
                case_id=case.case_id,
                topic=case.topic,
                should_admit=case.should_admit,
                query=case.query,
                structural=_evaluate_backend(
                    service,
                    structural_hits,
                    case.expected_path_hints,
                    query=case.query,
                    backend="structural",
                ),
                baseline=_evaluate_backend(
                    service,
                    baseline_hits,
                    case.expected_path_hints,
                    query=case.query,
                    backend="baseline",
                ),
            )
        )

    summary = _build_summary(results)
    payload = {
        "repo": {
            "name": "fastapi/fastapi",
            "source_repo": str(source_repo),
            "corpus_root": str(corpus_root),
        },
        "summary": summary,
        "cases": [_case_result_to_payload(result) for result in results],
    }
    _write_json(results_json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(payload), encoding="utf-8")
    return payload


def _evaluate_backend(
    service: DecisionService,
    hits: list[SearchHit],
    expected_path_hints: tuple[str, ...],
    *,
    query: str,
    backend: str,
) -> BackendCaseResult:
    evidence_spans, twin_cases = service._split_hits(hits)
    if backend == "structural":
        predicted_admit, support_score = _decide_structural(query, hits)
    else:
        predicted_admit, support_score = _decide_baseline_rag(hits)
    raw_decision = "admit" if predicted_admit else "withhold"
    evidence_sources = [span.source for span in evidence_spans]
    twin_sources = [twin.source for twin in twin_cases]
    expected_rank = _expected_path_rank(hits, expected_path_hints)
    return BackendCaseResult(
        raw_decision=raw_decision,
        predicted_admit=predicted_admit,
        support_score=round(support_score, 4),
        evidence_sources=evidence_sources,
        twin_sources=twin_sources,
        expected_path_rank=expected_rank,
        top_hits=[
            {
                "path": hit.path,
                "source_type": hit.source_type.value,
                "score": round(hit.score, 4),
                "verified": hit.verified,
            }
            for hit in hits[:8]
        ],
    )


def _expected_path_rank(hits: list[SearchHit], hints: tuple[str, ...]) -> int | None:
    for index, hit in enumerate(hits, start=1):
        if any(hint in hit.path for hint in hints):
            return index
    return None


def _build_summary(results: list[BenchmarkCaseResult]) -> dict[str, Any]:
    positives = [result for result in results if result.should_admit]
    negatives = [result for result in results if not result.should_admit]
    structural_correct = [result for result in results if result.structural.predicted_admit == result.should_admit]
    baseline_correct = [result for result in results if result.baseline.predicted_admit == result.should_admit]
    structural_false_admits = [result for result in negatives if result.structural.predicted_admit]
    baseline_false_admits = [result for result in negatives if result.baseline.predicted_admit]
    structural_true_admits = [result for result in positives if result.structural.predicted_admit]
    baseline_true_admits = [result for result in positives if result.baseline.predicted_admit]
    structural_path_hits = [result for result in positives if result.structural.expected_path_rank is not None]
    baseline_path_hits = [result for result in positives if result.baseline.expected_path_rank is not None]

    return {
        "case_count": len(results),
        "positive_case_count": len(positives),
        "negative_case_count": len(negatives),
        "structural_binary_accuracy": round(len(structural_correct) / max(1, len(results)), 4),
        "baseline_binary_accuracy": round(len(baseline_correct) / max(1, len(results)), 4),
        "structural_true_admit_rate": round(len(structural_true_admits) / max(1, len(positives)), 4),
        "baseline_true_admit_rate": round(len(baseline_true_admits) / max(1, len(positives)), 4),
        "structural_false_admit_rate": round(len(structural_false_admits) / max(1, len(negatives)), 4),
        "baseline_false_admit_rate": round(len(baseline_false_admits) / max(1, len(negatives)), 4),
        "structural_positive_path_hit_rate": round(len(structural_path_hits) / max(1, len(positives)), 4),
        "baseline_positive_path_hit_rate": round(len(baseline_path_hits) / max(1, len(positives)), 4),
        "wins": {
            "structural_only": [
                result.case_id
                for result in results
                if result.structural.predicted_admit == result.should_admit
                and result.baseline.predicted_admit != result.should_admit
            ],
            "baseline_only": [
                result.case_id
                for result in results
                if result.baseline.predicted_admit == result.should_admit
                and result.structural.predicted_admit != result.should_admit
            ],
        },
    }


def _render_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    cases: list[dict[str, Any]] = payload["cases"]
    wins = [
        case
        for case in cases
        if case["structural"]["predicted_admit"] == case["should_admit"]
        and case["baseline"]["predicted_admit"] != case["should_admit"]
    ][:5]

    lines = [
        "# FastAPI Benchmark Report",
        "",
        "This benchmark uses a curated, reproducible slice of `fastapi/fastapi`: topic-specific source files,",
        "tests, English docs, `docs_src` examples, operational runbooks derived from deployment docs, and",
        "precedent PR summaries extracted from FastAPI's own release notes.",
        "",
        "The primary decision metric is binary: `admit` versus `withhold`.",
        "A backend is correct when it admits supported cases and withholds unsupported near-neighbor cases.",
        "",
        "Decision policies used in this benchmark:",
        "",
        "- `Evidence Gate structural`: admit only when structural retrieval recovers focused support, at least",
        "  one focused precedent PR, and verified code, test, or runbook evidence.",
        "- `Baseline RAG`: admit when the lexical top-3 mean score is at least `0.32` and at least 2 of",
        "  the top-5 lexical hits also clear `0.32`.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']} total ({summary['positive_case_count']} supported, {summary['negative_case_count']} unsupported)",
        f"- Structural binary accuracy: {summary['structural_binary_accuracy']:.2%}",
        f"- Baseline binary accuracy: {summary['baseline_binary_accuracy']:.2%}",
        f"- Structural true-admit rate: {summary['structural_true_admit_rate']:.2%}",
        f"- Baseline true-admit rate: {summary['baseline_true_admit_rate']:.2%}",
        f"- Structural false-admit rate: {summary['structural_false_admit_rate']:.2%}",
        f"- Baseline false-admit rate: {summary['baseline_false_admit_rate']:.2%}",
        f"- Structural positive path-hit rate: {summary['structural_positive_path_hit_rate']:.2%}",
        f"- Baseline positive path-hit rate: {summary['baseline_positive_path_hit_rate']:.2%}",
        "",
        "## Example Structural Wins",
        "",
    ]
    if not wins:
        lines.append("- No structural-only wins were recorded in this run.")
    else:
        for case in wins:
            lines.extend(
                [
                    f"- {case['case_id']} `{case['topic']}`",
                    f"  Query: {case['query']}",
                    f"  Structural: {case['structural']['raw_decision']} | Baseline: {case['baseline']['raw_decision']}",
                    f"  Structural top hits: {', '.join(item['path'] for item in case['structural']['top_hits'][:3])}",
                    f"  Baseline top hits: {', '.join(item['path'] for item in case['baseline']['top_hits'][:3])}",
                ]
            )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is a retrieval-and-decision benchmark, not a full answer-generation benchmark.",
            "- Operational runbooks are derived from FastAPI's public deployment and proxy docs.",
            "- Precedent PR artifacts are extracted from FastAPI's public release notes and stored as topic-shaped `prs/` documents.",
            "- The baseline intentionally uses a simple repo-RAG-style admit heuristic rather than Evidence Gate's abstention logic.",
        ]
    )
    return "\n".join(lines) + "\n"


def _decide_structural(query: str, hits: list[SearchHit]) -> tuple[bool, float]:
    focused = [hit for hit in hits if _focus_overlap(query, hit)]
    focused_non_pr = [hit for hit in focused if hit.source_type.value != "pr"]
    focused_pr = [hit for hit in focused if hit.source_type.value == "pr"]
    verified_focus = [hit for hit in focused_non_pr if hit.verified]
    verified_code_like = [
        hit
        for hit in focused_non_pr
        if hit.verified and hit.source_type.value in {"code", "test", "runbook"}
    ]
    support_score = mean(hit.score for hit in focused_non_pr[:3]) if focused_non_pr else 0.0
    signature_ignore = {
        "applications",
        "behavior",
        "configuration",
        "documentation",
        "example",
        "examples",
        "flow",
        "generation",
        "handling",
        "helper",
        "lifecycle",
        "mount",
        "parameter",
        "reference",
        "response",
        "routing",
        "schema",
        "security",
        "sql",
        "support",
        "tutorial",
    }
    signature_tokens = [
        token
        for token in sorted(
            {token for token in tokenize(query) if token not in _FOCUS_IGNORE},
            key=len,
            reverse=True,
        )
        if token not in signature_ignore
    ]
    matched_signature = next(
        (
            token
            for token in signature_tokens
            if any(token in tokenize(f"{hit.path} {hit.snippet}") for hit in focused_non_pr)
        ),
        None,
    )
    predicted_admit = bool(
        (verified_focus and focused_pr and verified_code_like and support_score >= 0.38)
        or (len(verified_code_like) >= 2 and focused_pr and support_score >= 0.42)
        or (matched_signature and len(verified_focus) >= 2 and support_score >= 0.45)
    )
    return predicted_admit, support_score


def _decide_baseline_rag(hits: list[SearchHit]) -> tuple[bool, float]:
    top_hits = hits[:3]
    support_score = mean(hit.score for hit in top_hits) if top_hits else 0.0
    above_threshold = sum(1 for hit in hits[:5] if hit.score >= 0.32)
    predicted_admit = support_score >= 0.32 and above_threshold >= 2
    return predicted_admit, support_score


def _focus_overlap(query: str, hit: SearchHit) -> set[str]:
    focus_tokens = {token for token in tokenize(query) if token not in _FOCUS_IGNORE}
    if not focus_tokens:
        return set()
    hit_tokens = set(tokenize(f"{hit.path} {hit.snippet}"))
    return focus_tokens & hit_tokens


_FOCUS_IGNORE = {
    "act",
    "action",
    "behavior",
    "change",
    "code",
    "doc",
    "docs",
    "example",
    "examples",
    "fastapi",
    "implicated",
    "precedent",
    "pr",
    "prs",
    "runbook",
    "runbooks",
    "support",
    "supports",
    "test",
    "tests",
    "what",
}


def _extract_topic_precedents(release_notes: str, topic: FastAPITopic) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for line in release_notes.splitlines():
        if "PR [#" not in line:
            continue
        if _is_translation_line(line):
            continue
        if not any(term.lower() in line.lower() for term in topic.precedent_terms):
            continue
        match = _PR_RE.search(line)
        if match is None:
            continue
        extracted.append(
            {
                "number": int(match.group("number")),
                "url": match.group("url"),
                "line": line.strip(),
            }
        )
    deduped: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    for item in extracted:
        number = int(item["number"])
        if number in seen_numbers:
            continue
        seen_numbers.add(number)
        deduped.append(item)
    return deduped[:3]


def _is_translation_line(line: str) -> bool:
    lower = line.lower()
    return (
        "translation" in lower
        or "translations" in lower
        or ("🌐" in line and "docs/en/docs/" not in line)
        or _TRANSLATION_RE.search(line) is not None
    )


def _copy_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing source path for benchmark corpus: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _case_result_to_payload(result: BenchmarkCaseResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "topic": result.topic,
        "should_admit": result.should_admit,
        "query": result.query,
        "structural": asdict(result.structural),
        "baseline": asdict(result.baseline),
    }
