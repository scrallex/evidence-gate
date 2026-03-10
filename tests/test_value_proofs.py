from pathlib import Path

from evidence_gate.benchmark.value_proofs import (
    GENERALIZATION_CASES,
    _build_healing_prompt,
    _split_gold_patch_paths,
    run_multi_source_incident_benchmark,
    run_poisoned_corpus_benchmark,
)


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
