#!/usr/bin/env python3
"""Run the Evidence Gate fail-explain-repair-retry loop as a shell-friendly JSON tool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from evidence_gate.api.main import get_decision_service
from evidence_gate.decision.models import ActionDecisionRequest
from evidence_gate.mcp.server import _build_retry_prompt, _prepare_repository


def _parse_external_source(raw_value: str) -> dict[str, str]:
    kind, separator, path = raw_value.partition("=")
    if not separator or not kind.strip() or not path.strip():
        raise argparse.ArgumentTypeError(
            "External sources must use KIND=/absolute/or/relative/path syntax."
        )
    return {"type": kind.strip(), "path": path.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", required=True, help="Absolute path to the target repository.")
    parser.add_argument("--action-summary", required=True, help="Planned action summary to gate.")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Relative path touched by the planned change. Repeat for multiple paths.",
    )
    parser.add_argument(
        "--diff-summary",
        default=None,
        help="Optional diff or PR summary to strengthen path alignment.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Retrieval depth for the action decision.",
    )
    parser.add_argument(
        "--refresh-repository",
        action="store_true",
        help="Force a repository re-ingest before gating.",
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Skip the repository preparation step and reuse the current knowledge base state.",
    )
    parser.add_argument(
        "--external-source",
        action="append",
        default=[],
        type=_parse_external_source,
        help="External source in KIND=PATH form. Repeat for multiple sources.",
    )
    parser.add_argument(
        "--safety-policy-json",
        default=None,
        help="Optional inline JSON object for the action safety policy.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    safety_policy = json.loads(args.safety_policy_json) if args.safety_policy_json else None

    preparation = None
    if not args.skip_prepare:
        preparation = _prepare_repository(
            repo_path=args.repo_path,
            refresh=args.refresh_repository,
            external_sources=args.external_source,
        )

    action_decision = get_decision_service().decide_action(
        ActionDecisionRequest(
            repo_path=args.repo_path,
            action_summary=args.action_summary,
            changed_paths=args.changed_path,
            diff_summary=args.diff_summary,
            safety_policy=safety_policy,
            top_k=args.top_k,
        )
    )

    retry_prompt = ""
    next_step = "proceed"
    if not action_decision.allowed:
        retry_prompt = _build_retry_prompt(action_decision.decision_record.missing_evidence)
        next_step = "repair_and_retry" if retry_prompt else "inspect_evidence"

    payload = {
        "preparation": preparation.model_dump(mode="json") if preparation is not None else None,
        "action_decision": action_decision.model_dump(mode="json"),
        "retry_prompt": retry_prompt or None,
        "next_step": next_step,
        "strongest_evidence_sources": [
            span.source for span in action_decision.decision_record.evidence_spans[:3]
        ],
        "twin_case_sources": [
            twin.source for twin in action_decision.decision_record.twin_cases[:3]
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
