#!/usr/bin/env python3
"""Run the curated FastAPI structural-vs-baseline benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from evidence_gate.benchmark.fastapi import (
    DEFAULT_BENCHMARK_ROOT,
    run_fastapi_benchmark,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-repo",
        type=Path,
        default=Path.home() / ".evidence-gate" / "benchmark_repos" / "fastapi",
        help="Local FastAPI clone to use as the upstream source corpus.",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=DEFAULT_BENCHMARK_ROOT / "workdir",
        help="External state root for the derived corpus and knowledge base.",
    )
    parser.add_argument(
        "--cases-json",
        type=Path,
        default=Path("benchmarks/cases/fastapi_cases.json"),
        help="Tracked JSON file describing the 50 benchmark queries.",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=Path("benchmarks/results/fastapi_structural_vs_baseline.json"),
        help="Tracked JSON file for raw benchmark results.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("benchmarks/results/fastapi_structural_vs_baseline.md"),
        help="Tracked Markdown report summarizing the benchmark outcome.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=12,
        help="Retrieval depth to evaluate for both structural and baseline search.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_fastapi_benchmark(
        source_repo=args.source_repo,
        work_root=args.work_root,
        cases_json_path=args.cases_json,
        results_json_path=args.results_json,
        report_path=args.report,
        top_k=args.top_k,
    )
    summary = payload["summary"]
    print(
        "FastAPI benchmark complete: "
        f"structural accuracy={summary['structural_binary_accuracy']:.2%}, "
        f"baseline accuracy={summary['baseline_binary_accuracy']:.2%}, "
        f"structural false-admit={summary['structural_false_admit_rate']:.2%}, "
        f"baseline false-admit={summary['baseline_false_admit_rate']:.2%}"
    )
    print(f"Cases: {args.cases_json}")
    print(f"Results: {args.results_json}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
