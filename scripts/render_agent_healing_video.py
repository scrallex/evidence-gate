#!/usr/bin/env python3
"""Render a terminal-first sales video for the Evidence Gate healing-loop demo."""

from __future__ import annotations

import argparse
import json
import subprocess
from html import escape
from pathlib import Path
from textwrap import wrap


WIDTH = 1600
HEIGHT = 900
TITLE_Y = 182
BODY_Y = 286
LINE_HEIGHT = 36
SNIPPET_Y = 430
SNIPPET_LINE_HEIGHT = 28
FOOTER_Y = 840


def run(args: list[str]) -> None:
    subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def wrap_lines(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append("")
            continue
        lines.extend(wrap(stripped, width=width) or [""])
    return lines


def snippet_lines(text: str, limit: int = 12, width: int = 88) -> list[str]:
    raw_lines: list[str] = []
    for line in text.splitlines():
        raw_lines.extend(wrap(line.rstrip(), width=width, replace_whitespace=False) or [""])
    return raw_lines[:limit]


def svg_text_block(lines: list[str], *, x: int, y: int, font_size: int, fill: str, font_family: str) -> str:
    rendered: list[str] = []
    for index, line in enumerate(lines):
        escaped = escape(line) if line else " "
        rendered.append(
            f'<text x="{x}" y="{y + index * (font_size + 8)}" '
            f'font-family="{font_family}" font-size="{font_size}" fill="{fill}">{escaped}</text>'
        )
    return "\n".join(rendered)


def extract_comment_focus(comment_text: str) -> str:
    focus_lines: list[str] = []
    for raw_line in comment_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            focus_lines.append(line)
            continue
        if line.startswith("- Failure reason:"):
            focus_lines.append(line)
            continue
        if line.startswith("- Missing evidence:"):
            focus_lines.append(line)
            continue
        if line.startswith("### Suggested Retry Prompt"):
            focus_lines.append(line)
            continue
        if focus_lines and not line.startswith("- ") and not line.startswith("<!-- "):
            focus_lines.append(line)
    return "\n".join(focus_lines)


def load_full_replay_metrics(benchmark_json: Path) -> dict[str, object]:
    payload = json.loads(benchmark_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    cases = payload.get("cases", [])
    initial_allowed = sum(1 for case in cases if case.get("initial_gold_allowed"))
    healed_allowed = sum(1 for case in cases if case.get("healed_gold_allowed"))
    healed_delta = healed_allowed - initial_allowed
    false_allow_count = sum(1 for case in cases if case.get("decoy_allowed"))
    return {
        "dataset_name": payload["dataset"],
        "case_count": summary["case_count"],
        "initial_allow_rate": summary["initial_gold_allow_rate"],
        "healed_allow_rate": summary["healed_gold_allow_rate"],
        "uplift_points": (summary["healed_gold_allow_rate"] - summary["initial_gold_allow_rate"]) * 100.0,
        "healed_delta": healed_delta,
        "false_allow_rate": summary["decoy_false_allow_rate"],
        "false_allow_count": false_allow_count,
    }


def format_changed_paths(paths: list[str], *, label: str = "Changed paths:") -> str:
    if not paths:
        return f"{label}\n  (not provided)"
    return label + "\n" + "\n".join(f"  {path}" for path in paths)


def write_slide(
    *,
    output_path: Path,
    title: str,
    body: str,
    snippet: str,
    accent: str,
    footer: str,
    eyebrow: str,
) -> None:
    body_lines = wrap_lines(body, 72)
    code_lines = snippet_lines(snippet)
    title_font_size = 60
    if len(title) > 34:
        title_font_size = 54
    if len(title) > 46:
        title_font_size = 48
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#08111f" />
      <stop offset="100%" stop-color="#14243f" />
    </linearGradient>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)" />
  <circle cx="1340" cy="120" r="180" fill="{accent}" opacity="0.10" />
  <circle cx="1480" cy="760" r="220" fill="{accent}" opacity="0.08" />
  <rect x="0" y="0" width="{WIDTH}" height="16" fill="{accent}" />
  <rect x="80" y="90" width="340" height="48" rx="24" fill="{accent}" opacity="0.18" />
  <text x="110" y="123" font-family="DejaVu Sans" font-size="22" font-weight="700" fill="{accent}">{escape(eyebrow)}</text>
  <rect x="80" y="360" width="1440" height="390" rx="22" fill="#0d1728" stroke="{accent}" stroke-width="3" />
  <text x="80" y="{TITLE_Y}" font-family="DejaVu Sans" font-size="{title_font_size}" font-weight="700" fill="#f8fafc">{escape(title)}</text>
  {svg_text_block(body_lines, x=80, y=BODY_Y, font_size=30, fill="#cbd5e1", font_family="DejaVu Sans")}
  {svg_text_block(code_lines, x=110, y=SNIPPET_Y, font_size=24, fill="#e2e8f0", font_family="DejaVu Sans Mono")}
  <text x="80" y="{FOOTER_Y}" font-family="DejaVu Sans" font-size="24" fill="{accent}">{escape(footer)}</text>
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def slide_specs(summary: dict[str, object], benchmark_metrics: dict[str, object]) -> list[dict[str, object]]:
    if summary.get("demo_type") == "dogfood_runbook":
        return dogfood_runbook_slide_specs(summary, benchmark_metrics)

    blocked = summary["blocked"]
    healed = summary["healed"]
    repo_url = str(summary["repo_url"])
    pr_url = str(summary["pr_url"])
    blocked_comment = Path(str(blocked["comment_path"])).read_text(encoding="utf-8")
    blocked_checks = Path(str(blocked["checks_path"])).read_text(encoding="utf-8")
    healed_checks = Path(str(healed["checks_path"])).read_text(encoding="utf-8")
    retry_prompt = str(blocked.get("retry_prompt", ""))
    blocked_focus = extract_comment_focus(blocked_comment)
    proof_snippet = (
        f"Tested on {benchmark_metrics['case_count']} SWE-bench Lite tasks\n"
        f"Healed {benchmark_metrics['healed_delta']} broken PR-like patches\n"
        f"+{benchmark_metrics['uplift_points']:.2f} points admit uplift\n"
        f"{benchmark_metrics['false_allow_rate']:.2%} wrong-file false-allow"
    )

    return [
        {
            "eyebrow": "THE PROBLEM",
            "title": "AI Agents Write Tech Debt",
            "body": (
                "They fix code fast, but they skip tests and ignore the operating context that makes the "
                "change safe to merge. Evidence Gate exists to block that incomplete work before review."
            ),
            "snippet": (
                "Failure pattern:\n"
                "  1. code-only fix lands\n"
                "  2. tests stay stale\n"
                "  3. runbook context is skipped\n"
                "  4. reviewer inherits the cleanup"
            ),
            "accent": "#38bdf8",
            "footer": "Hook: Evidence Gate forces agents to finish the engineering job, not just the diff.",
            "duration": 8,
        },
        {
            "eyebrow": "1. THE ACTION",
            "title": "The Agent Opens A Code-Only PR",
            "body": (
                "This is a real public demo PR. The agent fixes the billing tax bug in `billing/api.py`, "
                "but it does not touch the regression test that should prove the fix."
            ),
            "snippet": (
                f"Repo: {repo_url}\n"
                f"PR: {pr_url}\n\n"
                "Changed path:\n"
                "  billing/api.py\n\n"
                "No test file touched on the first attempt."
            ),
            "accent": "#f59e0b",
            "footer": "This is the failure mode: a plausible fix that still creates review debt.",
            "duration": 11,
        },
        {
            "eyebrow": "2. THE GATE",
            "title": "Evidence Gate Blocks The PR",
            "body": (
                "The workflow fails closed. Evidence Gate sees a code path change without supporting test "
                "evidence and refuses to let the pull request slide through on vibes."
            ),
            "snippet": blocked_checks,
            "accent": "#ef4444",
            "footer": "Outcome: red check, blocked merge, no human reviewer has to explain the miss.",
            "duration": 12,
        },
        {
            "eyebrow": "3. THE DIAGNOSTIC",
            "title": "The Gate Returns `missing_evidence`",
            "body": (
                "This is the differentiator. Evidence Gate does not only say no. It emits a machine-readable "
                "diagnostic and a retry prompt the agent can use on the very next attempt."
            ),
            "snippet": blocked_focus,
            "accent": "#ef4444",
            "footer": "Key UX: the block becomes the agent's next instruction.",
            "duration": 14,
        },
        {
            "eyebrow": "4. THE HEAL",
            "title": "The Agent Consumes The Prompt",
            "body": (
                "The retry prompt tells the agent what is missing. It goes back, adds the regression test, "
                "and pushes the same pull request through the gate again."
            ),
            "snippet": (
                (retry_prompt or "Evidence Gate blocked the previous attempt because the change lacked supporting test evidence.")
                + "\n\n"
                "New file:\n"
                "  tests/test_total.py\n\n"
                "Test case:\n"
                "  assert calculate_total_cents(1000, 8) == 1080"
            ),
            "accent": "#f59e0b",
            "footer": "Compiler loop: fail, explain, repair, retry.",
            "duration": 13,
        },
        {
            "eyebrow": "5. THE RESULT",
            "title": "The Same PR Turns Green",
            "body": (
                "Nothing about the reviewer changed. The patch got better. With the missing test in place, "
                "Evidence Gate now admits the change and the pull request turns green."
            ),
            "snippet": healed_checks,
            "accent": "#22c55e",
            "footer": "Evidence Gate is not review summarization. It is admission control for agents.",
            "duration": 12,
        },
        {
            "eyebrow": "5. THE PROOF",
            "title": "This Pattern Holds Beyond One Demo",
            "body": (
                "The public PR is the visual hook. The benchmark is the proof layer: on the full official "
                "SWE-bench Lite replay, the healing loop rescued 54 initially blocked gold-path attempts."
            ),
            "snippet": proof_snippet,
            "accent": "#38bdf8",
            "footer": "Use this line: Tested on 300 SWE-bench Lite tasks. Healed 54 broken PRs. +18% uplift.",
            "duration": 12,
        },
        {
            "eyebrow": "CLOSE",
            "title": "Compiler For Agents, Not Another PR Bot",
            "body": (
                "CodeRabbit tells a human what looks risky. Evidence Gate blocks the agent, explains why, "
                "and forces the next retry to include the missing test or supported file path."
            ),
            "snippet": (
                "Narrative:\n"
                "  problem -> code-only PR\n"
                "  gate -> missing_evidence\n"
                "  heal -> added test\n"
                "  result -> green PR\n"
                "  proof -> +18.00 points on 300 tasks"
            ),
            "accent": "#38bdf8",
            "footer": "Tagline: AI agents write tech debt. Evidence Gate forces them to write tests and read your docs first.",
            "duration": 9,
        },
    ]


def dogfood_runbook_slide_specs(
    summary: dict[str, object],
    benchmark_metrics: dict[str, object],
) -> list[dict[str, object]]:
    blocked = summary["blocked"]
    healed = summary["healed"]
    story = summary.get("story", {})
    repo_url = str(summary["repo_url"])
    blocked_comment = Path(str(blocked["comment_path"])).read_text(encoding="utf-8")
    blocked_checks = Path(str(blocked["checks_path"])).read_text(encoding="utf-8")
    healed_checks = Path(str(healed["checks_path"])).read_text(encoding="utf-8")
    retry_prompt = str(blocked.get("retry_prompt", ""))
    blocked_focus = extract_comment_focus(blocked_comment)
    changed_paths = [
        str(path)
        for path in story.get("changed_paths", [])
        if isinstance(path, str) and path.strip()
    ]
    repair_file = str(story.get("repair_file", "runbooks/mcp_agent_troubleshooting.md"))
    repair_prompt = str(story.get("repair_prompt", blocked.get("retry_prompt", "")))
    repair_summary = str(
        story.get(
            "repair_summary",
            "Add the missing operational runbook, then rerun the gate.",
        )
    )
    policy_name = str(story.get("policy_name", "require_runbook_evidence"))
    policy_summary = str(
        story.get(
            "policy_summary",
            "Organizational standard: operational runbook coverage is required before merge.",
        )
    )
    proof_snippet = (
        f"Dogfood:\n"
        f"  policy: {policy_name}\n"
        f"  blocked: 7 files, 2 tests, 1 docs, 0 runbooks\n"
        f"  healed: 8 files, 2 tests, 1 docs, 1 runbooks\n\n"
        f"Benchmark:\n"
        f"  Tested on {benchmark_metrics['case_count']} SWE-bench Lite tasks\n"
        f"  Healed {benchmark_metrics['healed_delta']} broken PR-like patches\n"
        f"  +{benchmark_metrics['uplift_points']:.2f} points admit uplift"
    )

    return [
        {
            "eyebrow": "THE PROBLEM",
            "title": "AI Agents Can Ship Unmaintainable Integrations",
            "body": (
                "A workflow can be technically correct and still fail the team standard. "
                "Agents often wire up code and tests but skip the operational runbook that "
                "tells the next engineer how to debug or roll it back."
            ),
            "snippet": (
                "Failure pattern:\n"
                "  1. MCP workflow lands\n"
                "  2. regression tests exist\n"
                "  3. no runbook is written\n"
                "  4. oncall inherits the ambiguity"
            ),
            "accent": "#38bdf8",
            "footer": "Hook: Evidence Gate can enforce standards, not just summarize risk.",
            "duration": 8,
        },
        {
            "eyebrow": "1. THE ACTION",
            "title": "The Agent Changes The MCP Workflow",
            "body": (
                "This is Evidence Gate dogfooding itself. The integration adds repo preparation, "
                "action gating, and a shell bridge for Cursor, Cline, and SWE-agent workflows."
            ),
            "snippet": (
                f"Repo: {repo_url}\n\n"
                + format_changed_paths(changed_paths)
            ),
            "accent": "#f59e0b",
            "footer": "The diff is useful, but it is still incomplete without operational context.",
            "duration": 10,
        },
        {
            "eyebrow": "2. THE GATE",
            "title": "Evidence Gate Blocks The Diff",
            "body": (
                "The gate is running with an explicit organizational standard: MCP workflow "
                "changes need runbook evidence before merge. The code can be real and still fail."
            ),
            "snippet": blocked_checks,
            "accent": "#ef4444",
            "footer": "Outcome: blocked because the standard was not met, not because a reviewer felt uneasy.",
            "duration": 11,
        },
        {
            "eyebrow": "3. THE DIAGNOSTIC",
            "title": "The Block Explains What Is Missing",
            "body": (
                "This is the enterprise hook. The gate does not only reject the change. It says "
                "which standard was violated and returns a retry prompt the agent can act on."
            ),
            "snippet": blocked_focus,
            "accent": "#ef4444",
            "footer": "The failed check becomes the next machine-readable instruction.",
            "duration": 12,
        },
        {
            "eyebrow": "4. THE HEAL",
            "title": "The Agent Writes The Runbook",
            "body": (
                "The repair is not another code tweak. The missing evidence is operational. "
                "The agent adds the MCP troubleshooting runbook with failure modes, debug steps, "
                "blast radius, and rollback guidance."
            ),
            "snippet": (
                (repair_prompt or "Evidence Gate blocked the previous attempt because the runbook was missing.")
                + "\n\n"
                f"New file:\n  {repair_file}\n\n"
                f"Added:\n  {repair_summary}"
            ),
            "accent": "#f59e0b",
            "footer": "The loop is fail, explain, repair, retry even when the missing artifact is documentation.",
            "duration": 12,
        },
        {
            "eyebrow": "5. THE RESULT",
            "title": "The Same Change Turns Green",
            "body": (
                "Nothing about the policy changed. The patch got better. Once the runbook exists, "
                "Evidence Gate can cite it directly and allow the exact same MCP integration diff."
            ),
            "snippet": healed_checks,
            "accent": "#22c55e",
            "footer": "The gate is enforcing maintainability, not only code correctness.",
            "duration": 11,
        },
        {
            "eyebrow": "6. THE PROOF",
            "title": "This Is Standards Enforcement",
            "body": (
                f"{policy_summary} Evidence Gate blocked the repo's own change until the runbook "
                "was written. The same compiler-style retry loop also raises admit rate at benchmark scale."
            ),
            "snippet": proof_snippet,
            "accent": "#38bdf8",
            "footer": "Use this line: We dogfooded the policy on our own MCP workflow and moved from block to allow by adding the runbook.",
            "duration": 12,
        },
        {
            "eyebrow": "CLOSE",
            "title": "Compiler For Agents, With Standards",
            "body": (
                "The point is not another PR bot. Evidence Gate can encode what your organization "
                "requires, stop the agent when that bar is missed, and tell it how to repair the gap."
            ),
            "snippet": (
                "Narrative:\n"
                "  action -> MCP workflow diff\n"
                "  gate -> runbook policy violation\n"
                "  heal -> added troubleshooting runbook\n"
                "  result -> allow\n"
                "  proof -> standard enforced by the tool"
            ),
            "accent": "#38bdf8",
            "footer": "Tagline: AI should not create legacy code. Evidence Gate forces the missing operational evidence before merge.",
            "duration": 9,
        },
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary-json",
        type=Path,
        required=True,
        help="Path to the demo summary JSON generated by publish_agent_healing_demo.py.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/agent_healing_demo/evidence-gate-healing-loop-demo.mp4"),
        help="Output MP4 path.",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("artifacts/agent_healing_demo/video_frames"),
        help="Working directory for generated slides.",
    )
    parser.add_argument(
        "--benchmark-json",
        type=Path,
        default=Path("benchmarks/results/swebench_lite_full_replay.json"),
        help="Path to the full SWE-bench Lite replay JSON for proof-slide stats.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = json.loads(args.summary_json.read_text(encoding="utf-8"))
    benchmark_metrics = load_full_replay_metrics(args.benchmark_json)
    workdir = args.workdir.expanduser().resolve()
    if workdir.exists():
        for path in workdir.iterdir():
            if path.is_file():
                path.unlink()
    else:
        workdir.mkdir(parents=True, exist_ok=True)

    specs = slide_specs(summary, benchmark_metrics)
    concat_lines: list[str] = []
    for index, spec in enumerate(specs, start=1):
        svg_path = workdir / f"slide_{index:02d}.svg"
        png_path = workdir / f"slide_{index:02d}.png"
        segment_path = workdir / f"segment_{index:02d}.mp4"
        write_slide(
            output_path=svg_path,
            title=str(spec["title"]),
            body=str(spec["body"]),
            snippet=str(spec["snippet"]),
            accent=str(spec["accent"]),
            footer=str(spec["footer"]),
            eyebrow=str(spec["eyebrow"]),
        )
        run(["convert", str(svg_path), str(png_path)])
        run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(png_path),
                "-t",
                str(int(spec["duration"])),
                "-r",
                "30",
                "-vf",
                "fps=30,format=yuv420p",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(segment_path),
            ]
        )
        concat_lines.append(f"file '{segment_path.as_posix()}'")

    concat_path = workdir / "segments.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(args.output),
        ]
    )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
