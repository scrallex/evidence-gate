# Live Connector Operations

This runbook covers the operational guardrails for Evidence Gate's live,
read-only Jira, Confluence, Slack, GitHub, and PagerDuty connectors.

## Scope

Use this runbook when:

- rotating API tokens used by `scripts/live_connector_exports.py`
- running `scripts/sync_live_exports.py` in a polling loop
- debugging stale or partial live-ingest context in CI, MCP, or local pilots
- deciding whether a connector outage should block merges or stay in shadow mode

Expected blast radius for the current connector surface is roughly:

- `5` integration families: GitHub, Jira, Confluence, Slack, PagerDuty
- `3` execution paths: local CLI, GitHub Action, MCP/partner pilot
- `1` persistent sync-state file: `sync-state.json`
- `1` operational runbook

## Token Rotation

All live connectors are read-only. Keep secrets in environment variables or CI
secrets, never in tracked config.

Rotate on this sequence:

1. Create the replacement token in the source system with the same read-only
   scopes as the old one.
2. Update the secret store first:
   - `GITHUB_TOKEN`
   - `JIRA_API_TOKEN`
   - `CONFLUENCE_API_TOKEN`
   - `SLACK_BOT_TOKEN`
   - `PAGERDUTY_TOKEN`
3. Trigger a one-shot sync with `scripts/sync_live_exports.py --max-runs 1`.
4. Confirm the export root contains fresh JSON and the new sync completed
   without `401` or `403`.
5. Revoke the old token only after the validation sync succeeds.

If one provider token fails rotation, disable only that connector and keep the
others running. Do not delete `sync-state.json`; preserve the cursors so the
next successful token resumes incrementally.

## Polling Policy

Evidence Gate already respects `Retry-After` on `429` and retries transient
`5xx` responses. The product policy is still conservative:

- bootstrap sync: one-shot, `30` day lookback
- steady-state polling: every `300` seconds or slower
- emergency shadow-mode pilot: every `900` seconds or slower
- timeout budget: `90` seconds per sync run

Do not run a continuous loop faster than `300` seconds in production pilots.
If an enterprise wants tighter freshness, start by increasing data quality
checks before increasing poll frequency.

## Failure Modes

Common failures:

1. `401` or `403`: token expired, wrong workspace, or missing read scope
2. repeated `429`: poll interval is too aggressive or another integration is
   consuming the quota
3. missing Slack threads or Confluence pages: channel IDs / space keys are
   wrong, or the token cannot see the content
4. sync appears successful but the gate still ignores context: the live export
   path is correct locally but not visible inside Docker or the running API
5. incremental sync stalls: `sync-state.json` advanced after a partial run or
   the upstream clock skew caused a cursor gap

## Troubleshooting Incremental Sync

1. Run a one-shot sync locally with the same env vars used in CI:

   ```bash
   python scripts/sync_live_exports.py \
     --output-root /tmp/evidence-gate-live \
     --visible-root /tmp/evidence-gate-live \
     --max-runs 1
   ```

2. Inspect `/tmp/evidence-gate-live/sync-state.json` and verify every enabled
   source has a recent `last_synced_at`.
3. If one provider is stale, rerun with that provider's token only and confirm
   the export directory updates.
4. If the cursor is ahead of the last good export, move only that provider's
   `last_synced_at` backward by a few minutes and rerun one sync.
5. If Docker is involved, confirm the same export directory is mounted into both
   the action runner and the Evidence Gate API container.
6. Re-run the gate and confirm the strongest evidence now includes the expected
   external Jira, Slack, Confluence, or PagerDuty sources.

## Shadow Mode Guidance

For a first design-partner pilot, run the GitHub Action in `GATING_MODE=shadow`.

- blocked decisions should emit a non-failing annotation
- the audit ledger should still record the blocked decision
- the dashboard should still count the avoided risk
- only switch to enforce mode after the team reviews at least one full sprint of
  shadow-mode results

## Rollback

If live connectors destabilize CI or flood the gate with incomplete data:

1. Set `GATING_MODE=shadow`.
2. Remove the failing provider token from the environment.
3. Re-run a one-shot sync for the remaining providers.
4. If needed, fall back to the last known-good static export path for that
   provider until the token or rate-limit issue is resolved.
