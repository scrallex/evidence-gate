from pathlib import Path

from evidence_gate.benchmark.fastapi import TOPICS, build_fastapi_cases


def test_fastapi_benchmark_has_balanced_case_set() -> None:
    cases = build_fastapi_cases()

    assert len(cases) == 50
    assert sum(1 for case in cases if case.should_admit) == 25
    assert sum(1 for case in cases if not case.should_admit) == 25
    assert len({case.case_id for case in cases}) == 50


def test_topic_paths_are_relative() -> None:
    for topic in TOPICS:
        for relative_path in topic.corpus_paths:
            assert not Path(relative_path).is_absolute()
