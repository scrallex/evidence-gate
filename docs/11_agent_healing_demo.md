# Agent Healing Demo

This guide covers the public sales demo for Evidence Gate's healing loop.

## Goal

Show one concrete sequence:

1. an automated pull request fixes code but skips a required test
2. Evidence Gate blocks the pull request and posts a retry prompt
3. the agent follows that prompt, adds the missing test, and the same pull request turns green

This is the shortest product story in the repo because it makes the market
distinction obvious:

- a typical AI PR reviewer tells a human reviewer what looks wrong
- Evidence Gate blocks the agent attempt itself
- the block returns machine-readable `missing_evidence` and a retry prompt
- the agent can use that prompt to heal the patch before human review

## Assets

- `scripts/scaffold_agent_healing_demo.py`
- `scripts/publish_agent_healing_demo.py`
- `scripts/render_agent_healing_video.py`

## Demo repo

The scaffold creates a minimal billing-style repository with:

- a bugged `billing/api.py`
- docs and a rollback runbook
- a vendored copy of the current Evidence Gate GitHub Action
- a pull-request workflow that runs the gate, comments on the PR, and fails the check when blocked

## Live example

The current public demo run lives here:

- repo: `https://github.com/scrallex/evidence-gate-healing-loop-demo-20260311b`
- pull request: `https://github.com/scrallex/evidence-gate-healing-loop-demo-20260311b/pull/1`
- blocked run: `https://github.com/scrallex/evidence-gate-healing-loop-demo-20260311b/actions/runs/22930416751`
- healed run: `https://github.com/scrallex/evidence-gate-healing-loop-demo-20260311b/actions/runs/22930437421`

The rendered video artifact in this repository is:

- `artifacts/agent_healing_demo/evidence-gate-healing-loop-demo.mp4`

## Publish the public repo

```bash
python scripts/publish_agent_healing_demo.py \
  --repo-name evidence-gate-healing-loop-demo-$(date +%Y%m%d)
```

That command will:

1. scaffold the repo locally
2. create a public GitHub repo
3. push `main`
4. push a failing agent branch with a code-only fix
5. open a pull request
6. wait for the blocked run and PR comment
7. push a healing commit with the missing test
8. wait for the passing run
9. write `artifacts/agent_healing_demo/demo_summary.json`

Use `--delete-existing` only when the GitHub token has repository deletion scope and you explicitly want to replace an existing public demo repo.

## Render the video

```bash
python scripts/render_agent_healing_video.py \
  --summary-json artifacts/agent_healing_demo/demo_summary.json
```

The renderer builds a terminal-first MP4 from the real PR checks and the real
Evidence Gate comment. The default output path is:

```text
artifacts/agent_healing_demo/evidence-gate-healing-loop-demo.mp4
```

The current cut renders to 114 seconds.

## Findings

- the public run exposed a real composite-action manifest bug in `action.yml`; the demo failed until the diff-summary step was rewritten as valid shell
- the final public PR shows the exact red-to-green healing loop: blocked for missing test evidence, then admitted after the regression test was added
- the broader benchmark story now matches the demo shape at dataset scale: on the full 300-instance `SWE-bench_Lite` replay, admit rate moved from 32.67% to 50.67% after the healing retry while wrong-file false allows stayed at 1.00%

## Talk track

Use this exact message on the final slide or voiceover:

`AI agents write tech debt. Evidence Gate forces them to write tests and read your docs before you ever have to review their code.`

Short variant for investor or partner conversations:

`This is not another AI PR reviewer. It is a compiler for agents: block, diagnose, retry, then admit.`

Use the benchmark numbers carefully in the spoken pitch:

- say `the healing loop improved admit rate by 18 points on a 300-task SWE-bench Lite replay`
- do not say `it solved 50.67% of SWE-bench`; this benchmark measures gate admission behavior, not end-to-end task completion
