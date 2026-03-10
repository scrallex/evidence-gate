#!/usr/bin/env python3
"""Format Evidence Gate action decisions as GitHub-friendly markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_comment(payload: dict[str, Any]) -> str:
    action_payload = payload
    if "decision_record" not in action_payload:
        action_payload = {
            "allowed": payload.get("decision") == "admit",
            "status": "allow" if payload.get("decision") == "admit" else "block",
            "failure_reason": None,
            "decision_record": payload,
        }

    record = action_payload["decision_record"]
    blast_radius = record.get("blast_radius", {})
    evidence_spans = record.get("evidence_spans", [])
    twin_cases = record.get("twin_cases", [])
    missing_evidence = record.get("missing_evidence", [])
    decision = str(record.get("decision", "unknown")).capitalize()
    title_status = "Allow" if action_payload.get("allowed") else "Block"

    lines = [f"## Evidence Gate: {title_status} ({decision})", ""]
    lines.append(f"- Decision ID: `{record.get('decision_id', 'unknown')}`")
    lines.append(
        "- Blast radius: "
        f"{blast_radius.get('files', 0)} files, "
        f"{blast_radius.get('tests', 0)} tests, "
        f"{blast_radius.get('docs', 0)} docs, "
        f"{blast_radius.get('runbooks', 0)} runbooks"
    )
    if action_payload.get("failure_reason"):
        lines.append(f"- Failure reason: {action_payload['failure_reason']}")

    if missing_evidence:
        lines.append("- Missing evidence: " + "; ".join(str(item) for item in missing_evidence[:3]))

    if twin_cases:
        twin_summary = ", ".join(str(twin.get("source", twin.get("id", "unknown"))) for twin in twin_cases[:2])
        lines.append(f"- Closest twins: {twin_summary}")

    if evidence_spans:
        evidence_summary = ", ".join(str(span.get("source", "unknown")) for span in evidence_spans[:3])
        lines.append(f"- Strongest evidence: {evidence_summary}")

    explanation = record.get("explanation")
    if explanation:
        lines.append(f"- Explanation: {explanation}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Format an Evidence Gate decision as markdown.")
    parser.add_argument("--input", required=True, help="Path to an action-decision JSON payload.")
    parser.add_argument("--output", help="Optional output markdown path.")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    comment = build_comment(payload)
    if args.output:
        Path(args.output).write_text(comment, encoding="utf-8")
    else:
        print(comment, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
