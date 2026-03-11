#!/usr/bin/env python3
"""Run a full SWE-bench Lite replay benchmark for Evidence Gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from datasets import load_dataset

from evidence_gate.benchmark.value_proofs import (
    DEFAULT_SWEBENCH_DATASET,
    DEFAULT_VALUE_PROOF_ROOT,
    render_swebench_replay_report,
    run_swebench_replay_benchmark,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=DEFAULT_VALUE_PROOF_ROOT / "swebench_full_workdir",
        help="External state root for cloned repos, corpora, and knowledge bases.",
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_SWEBENCH_DATASET,
        help="Official SWE-bench dataset identifier to replay.",
    )
    parser.add_argument(
        "--split",
        default="test",
        help="Dataset split to evaluate.",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=Path("benchmarks/results/swebench_lite_full_replay.json"),
        help="Tracked JSON file for raw full-replay results.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("benchmarks/results/swebench_lite_full_replay.md"),
        help="Tracked Markdown report for the full-replay findings.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=16,
        help="Retrieval depth to evaluate for the SWE-bench replay.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_dataset(args.dataset, split=args.split)
    repo_count = len({str(item["repo"]) for item in dataset})
    payload = run_swebench_replay_benchmark(
        work_root=args.work_root,
        dataset_name=args.dataset,
        split=args.split,
        max_instances=len(dataset),
        max_unique_repos=repo_count,
        selection_mode="full",
        top_k=args.top_k,
        verbose=True,
    )
    args.results_json.parent.mkdir(parents=True, exist_ok=True)
    args.results_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_swebench_replay_report(payload), encoding="utf-8")
    summary = payload["summary"]
    print(
        "Full SWE-bench replay complete: "
        f"coverage={summary['dataset_coverage_rate']:.2%}, "
        f"initial allow={summary['initial_gold_allow_rate']:.2%}, "
        f"healed allow={summary['healed_gold_allow_rate']:.2%}, "
        f"wrong-file false-allow={summary['decoy_false_allow_rate']:.2%}"
    )
    print(f"Results: {args.results_json}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
