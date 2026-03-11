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
TITLE_Y = 110
BODY_Y = 220
LINE_HEIGHT = 36
SNIPPET_Y = 360
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


def write_slide(
    *,
    output_path: Path,
    title: str,
    body: str,
    snippet: str,
    accent: str,
    footer: str,
) -> None:
    body_lines = wrap_lines(body, 72)
    code_lines = snippet_lines(snippet)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="{WIDTH}" height="{HEIGHT}" fill="#0b1220" />
  <rect x="0" y="0" width="{WIDTH}" height="18" fill="{accent}" />
  <rect x="80" y="310" width="1440" height="450" rx="18" fill="#101827" stroke="{accent}" stroke-width="3" />
  <text x="80" y="{TITLE_Y}" font-family="DejaVu Sans" font-size="58" font-weight="700" fill="#f8fafc">{escape(title)}</text>
  {svg_text_block(body_lines, x=80, y=BODY_Y, font_size=30, fill="#cbd5e1", font_family="DejaVu Sans")}
  {svg_text_block(code_lines, x=110, y=SNIPPET_Y, font_size=24, fill="#e2e8f0", font_family="DejaVu Sans Mono")}
  <text x="80" y="{FOOTER_Y}" font-family="DejaVu Sans" font-size="24" fill="{accent}">{escape(footer)}</text>
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def slide_specs(summary: dict[str, object]) -> list[dict[str, object]]:
    blocked = summary["blocked"]
    healed = summary["healed"]
    repo_url = str(summary["repo_url"])
    pr_url = str(summary["pr_url"])
    blocked_comment = Path(str(blocked["comment_path"])).read_text(encoding="utf-8")
    blocked_checks = Path(str(blocked["checks_path"])).read_text(encoding="utf-8")
    healed_checks = Path(str(healed["checks_path"])).read_text(encoding="utf-8")
    retry_prompt = str(blocked.get("retry_prompt", ""))

    return [
        {
            "title": "Evidence Gate: Compiler For AI Agents",
            "body": (
                "This demo shows a real public pull request getting blocked for missing test evidence, "
                "then turning green after the agent consumes Evidence Gate's retry prompt."
            ),
            "snippet": f"Repo: {repo_url}\nPR: {pr_url}",
            "accent": "#38bdf8",
            "footer": "Message: AI agents write tech debt. Evidence Gate forces them to finish the job.",
            "duration": 10,
        },
        {
            "title": "Scene 1: The Agent Makes The Code-Only Fix",
            "body": (
                "The first pull request fixes the billing tax bug but skips the missing regression test. "
                "The GitHub Action runs Evidence Gate as an active merge gate."
            ),
            "snippet": "Changed path:\n  billing/api.py\n\nNo test file touched on the first attempt.",
            "accent": "#f59e0b",
            "footer": "Evidence Gate is wired directly into the pull request workflow.",
            "duration": 14,
        },
        {
            "title": "Scene 2: The PR Gets Blocked",
            "body": (
                "The workflow fails closed. Evidence Gate does not allow the billing fix through because "
                "the pull request lacks supporting test evidence."
            ),
            "snippet": blocked_checks,
            "accent": "#ef4444",
            "footer": "Outcome: red check, blocked merge, no human review required yet.",
            "duration": 16,
        },
        {
            "title": "Scene 3: Evidence Gate Explains Exactly Why",
            "body": (
                "The pull request comment is the sales moment. It cites the missing evidence and emits "
                "a concrete retry instruction instead of just saying no."
            ),
            "snippet": blocked_comment,
            "accent": "#ef4444",
            "footer": "Key UX: missing_evidence plus a Suggested Retry Prompt.",
            "duration": 18,
        },
        {
            "title": "Scene 4: The Agent Uses The Retry Prompt",
            "body": (
                "Now the agent can repair the change instead of opening another bad pull request. "
                "The retry prompt becomes the next instruction."
            ),
            "snippet": retry_prompt or "Evidence Gate blocked the previous attempt because the change lacked supporting test evidence.",
            "accent": "#f59e0b",
            "footer": "Compiler loop: fail, explain, repair, retry.",
            "duration": 14,
        },
        {
            "title": "Scene 5: The Agent Adds The Missing Test",
            "body": (
                "A second commit adds the regression test for the billing total calculation and pushes "
                "the same pull request back through the gate."
            ),
            "snippet": "New file:\n  tests/test_total.py\n\nTest case:\n  assert calculate_total_cents(1000, 8) == 1080",
            "accent": "#22c55e",
            "footer": "The agent is now doing the complete engineering job.",
            "duration": 14,
        },
        {
            "title": "Scene 6: The PR Turns Green",
            "body": (
                "The same pull request now passes because the required evidence is present. "
                "Evidence Gate has coached the agent into a mergeable change."
            ),
            "snippet": healed_checks,
            "accent": "#22c55e",
            "footer": "Outcome: green check, guarded merge path, less human cleanup.",
            "duration": 16,
        },
        {
            "title": "Evidence Gate Stops Tech Debt Before Review",
            "body": (
                "This is the product wedge: a 0.00% false-allow guardrail that pushes agents toward "
                "tested, document-backed pull requests before they ever reach a reviewer."
            ),
            "snippet": (
                "Healing loop proof:\n"
                "  75.00% healed SWE-bench gold-path allow\n"
                "  66.67% healing success rate\n"
                "  0.00% false-allow in the replay\n"
                "  75.00% cross-language curated pilot allow"
            ),
            "accent": "#38bdf8",
            "footer": "Tagline: AI agents write tech debt. Evidence Gate forces them to write tests and read your docs first.",
            "duration": 12,
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = json.loads(args.summary_json.read_text(encoding="utf-8"))
    workdir = args.workdir.expanduser().resolve()
    if workdir.exists():
        for path in workdir.iterdir():
            if path.is_file():
                path.unlink()
    else:
        workdir.mkdir(parents=True, exist_ok=True)

    specs = slide_specs(summary)
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
