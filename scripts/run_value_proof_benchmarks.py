#!/usr/bin/env python3
"""Run the extended Evidence Gate value-proof benchmarks."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from evidence_gate.benchmark.value_proofs import (
    DEFAULT_SWEBENCH_DATASET,
    DEFAULT_VALUE_PROOF_ROOT,
    run_value_proof_benchmarks,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=DEFAULT_VALUE_PROOF_ROOT / "workdir",
        help="External state root for cloned repos, corpora, and knowledge bases.",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=Path("benchmarks/results/value_proof_benchmarks.json"),
        help="Tracked JSON file for raw results.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("benchmarks/results/value_proof_benchmarks.md"),
        help="Tracked Markdown report for the combined findings.",
    )
    parser.add_argument(
        "--swebench-dataset",
        default=DEFAULT_SWEBENCH_DATASET,
        help="Official SWE-bench dataset identifier to replay.",
    )
    parser.add_argument(
        "--swebench-instances",
        type=int,
        default=4,
        help="Maximum number of SWE-bench instances to replay.",
    )
    parser.add_argument(
        "--swebench-repos",
        type=int,
        default=4,
        help="Maximum number of unique SWE-bench repositories to include.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=12,
        help="Retrieval depth to evaluate for the synthetic benchmarks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_value_proof_benchmarks(
        work_root=args.work_root,
        results_json_path=args.results_json,
        report_path=args.report,
        swebench_instances=args.swebench_instances,
        swebench_repos=args.swebench_repos,
        top_k=args.top_k,
        swebench_dataset=args.swebench_dataset,
    )
    poisoned = payload["poisoned_corpus"]["summary"]
    multi_source = payload["multi_source_incident"]["summary"]
    swebench = payload["swebench_replay"]["summary"]
    print(
        "Value-proof benchmarks complete: "
        f"poisoned structural false-admit={poisoned['structural_false_admit_rate']:.2%}, "
        f"poisoned baseline false-admit={poisoned['baseline_false_admit_rate']:.2%}, "
        f"multi-source block delta={multi_source['incremental_block_rate']:.2%}, "
        f"swebench decoy false-allow={swebench['decoy_false_allow_rate']:.2%}"
    )
    print(f"Results: {args.results_json}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
