from pathlib import Path

from evidence_gate.benchmark.value_proofs import (
    GENERALIZATION_CASES,
    _build_healing_prompt,
    _select_decoy_paths,
    _select_retry_test_paths,
    _select_swebench_instances,
    _split_gold_patch_paths,
    render_swebench_replay_report,
    run_multi_source_incident_benchmark,
    run_poisoned_corpus_benchmark,
)
from evidence_gate.retrieval.repository import scan_repository


def test_poisoned_corpus_benchmark_builds_balanced_case_set(tmp_path: Path) -> None:
    payload = run_poisoned_corpus_benchmark(work_root=tmp_path / "poisoned", top_k=10)

    assert payload["summary"]["case_count"] == 48
    assert payload["summary"]["positive_case_count"] == 24
    assert payload["summary"]["negative_case_count"] == 24
    assert payload["summary"]["structural_false_admit_rate"] <= payload["summary"]["baseline_false_admit_rate"]


def test_multi_source_incident_benchmark_blocks_more_with_external_evidence(tmp_path: Path) -> None:
    payload = run_multi_source_incident_benchmark(work_root=tmp_path / "multi_source", top_k=10)

    assert payload["summary"]["case_count"] == 100
    assert payload["summary"]["multi_source_block_rate"] >= payload["summary"]["repo_only_block_rate"]
    assert payload["summary"]["incident_twin_hit_rate"] > 0


def test_swebench_healing_helpers_split_code_paths_and_build_retry_prompt() -> None:
    initial_paths, test_paths = _split_gold_patch_paths(
        ["src/cache.py", "tests/test_cache.py", "docs/cache.md"]
    )

    assert initial_paths == ["src/cache.py", "docs/cache.md"]
    assert test_paths == ["tests/test_cache.py"]

    prompt = _build_healing_prompt(
        "Review the cache change before merge.",
        ["No supporting test evidence was found for the affected flow."],
    )
    assert "blocked the previous attempt" in prompt
    assert "missing test coverage" in prompt


def test_generalization_catalog_covers_cross_language_targets() -> None:
    repos = {case.repo for case in GENERALIZATION_CASES}

    assert "redis/redis" in repos
    assert "facebook/react" in repos
    assert "vitejs/vite" in repos


def test_select_swebench_instances_supports_pilot_and_full_modes() -> None:
    dataset = [
        {
            "repo": "pallets/flask",
            "instance_id": "flask-1",
            "patch": "+++ b/src/app.py\n+++ b/tests/test_app.py\n",
        },
        {
            "repo": "pallets/flask",
            "instance_id": "flask-2",
            "patch": "+++ b/src/cli.py\n",
        },
        {
            "repo": "psf/requests",
            "instance_id": "requests-1",
            "patch": "+++ b/requests/sessions.py\n+++ b/tests/test_sessions.py\n",
        },
    ]

    pilot = _select_swebench_instances(
        dataset,
        max_instances=10,
        max_unique_repos=10,
        selection_mode="pilot",
    )
    full = _select_swebench_instances(
        dataset,
        max_instances=10,
        max_unique_repos=10,
        selection_mode="full",
    )

    assert [item["instance_id"] for item in pilot] == ["flask-1", "requests-1"]
    assert [item["instance_id"] for item in full] == ["flask-1", "flask-2", "requests-1"]


def test_render_swebench_replay_report_mentions_compiler_loop_and_limit() -> None:
    report = render_swebench_replay_report(
        {
            "dataset": "princeton-nlp/SWE-bench_Lite",
            "summary": {
                "selection_mode": "full",
                "dataset_case_count": 300,
                "dataset_repo_count": 12,
                "case_count": 300,
                "repo_count": 12,
                "dataset_coverage_rate": 1.0,
                "initial_gold_allow_rate": 0.25,
                "healed_gold_allow_rate": 0.75,
                "healing_retry_rate": 0.75,
                "healing_success_rate": 0.6667,
                "test_gap_block_rate": 0.75,
                "decoy_false_allow_rate": 0.0,
                "baseline_allow_rate": 1.0,
                "alignment_gap_trigger_rate": 1.0,
            },
            "cases": [],
        }
    )

    assert "compiler-like healing loop" in report
    assert "OpenHands or SWE-agent" in report


def test_swebench_helpers_reuse_pre_scanned_documents(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / "tests").mkdir(parents=True)
    (repo_root / "src" / "cache.py").write_text("def refresh_cache():\n    return True\n", encoding="utf-8")
    (repo_root / "src" / "worker.py").write_text("def run_worker():\n    return True\n", encoding="utf-8")
    (repo_root / "tests" / "test_cache.py").write_text(
        "from src.cache import refresh_cache\n\n"
        "def test_refresh_cache():\n"
        "    assert refresh_cache() is True\n",
        encoding="utf-8",
    )

    documents = scan_repository(repo_root)

    def _unexpected_scan(*args, **kwargs):
        raise AssertionError("scan_repository should not run when documents are provided")

    monkeypatch.setattr("evidence_gate.benchmark.value_proofs.scan_repository", _unexpected_scan)

    decoy_paths = _select_decoy_paths(
        repo_root,
        ["src/cache.py"],
        "Review the cache refresh change before merge.",
        documents=documents,
    )
    retry_paths = _select_retry_test_paths(
        repo_root,
        [],
        "Review the cache refresh change before merge.",
        ["src/cache.py"],
        documents=documents,
    )

    assert decoy_paths == ["src/worker.py"]
    assert retry_paths == ["tests/test_cache.py"]
