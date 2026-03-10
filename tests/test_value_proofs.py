from pathlib import Path

from evidence_gate.benchmark.value_proofs import (
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
