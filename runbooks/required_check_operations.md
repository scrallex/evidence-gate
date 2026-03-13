# Required Check Operations

This runbook covers the GitHub required-check workflow, the GitLab merge-request
wrapper, and the prebuilt CI image used to deliver Evidence Gate in protected
branch workflows.

## Scope and blast radius

- Delivery surfaces: `.github/workflows/evidence-gate-guardrail.yml`,
  `action.yml`, `ci/gitlab/evidence-gate-required-check.yml`,
  `scripts/run_required_check.py`, `scripts/run_action_guardrail.py`
- Runtime dependencies: local FastAPI API, live connector tokens, git diff base
  and head SHAs, optional LSIF or SCIP sidecars under `.evidence-gate/graphs`
- Failure modes: missing diff SHAs, stale prebuilt image, live connector auth
  failures, or test-link regressions that under-report downstream tests

## Standard operating mode

- GitHub required check:
  - Use `.github/workflows/evidence-gate-guardrail.yml`
  - Run with `gating_mode: enforce` when moving out of pilot mode
  - Use `gating_mode: shadow` only during a time-boxed pilot or rollout
- GitLab required check:
  - Start from `ci/gitlab/evidence-gate-required-check.yml`
  - Require the `evidence_gate_required_check` job before merge
- Container delivery:
  - Default image: `ghcr.io/scrallex/evidence-gate:latest`
  - If the pull fails or a hotfix has not been published yet, set
    `force_local_build: true` in GitHub or pin a known-good image tag in GitLab

## Troubleshooting

### The required check says there are no changed paths

- Confirm the CI job has both the base and head commit available locally.
- GitHub:
  - Ensure checkout uses `fetch-depth: 0`
  - Confirm `GITHUB_EVENT_PATH` includes `pull_request.base.sha` and
    `pull_request.head.sha`
- GitLab:
  - Confirm the job is running in a merge-request pipeline
  - Confirm `CI_MERGE_REQUEST_DIFF_BASE_SHA` is populated
- Manual fallback:
  - Pass `--base-sha` and `--head-sha` explicitly to
    `scripts/run_required_check.py`

### The job blocks because test evidence is still missing

- Confirm the changed code has at least one directly linked test in the repo or
  in the diff.
- For JS or TS repos:
  - Check that path-linked tests follow recognizable conventions such as
    `*.test.tsx`, `*.spec.ts`, or `__tests__/`
  - If the repo relies on dynamic imports or generated routing, add LSIF or
    SCIP sidecars under `.evidence-gate/graphs` so retrieval can boost
    compiler-grade neighbors instead of relying only on filename heuristics
- If the gate is still missing the test:
  - rerun ingestion with `refresh=true`
  - inspect the decision artifact and verify whether the linked test path
    surfaced in `evidence_spans` or the blast radius

### The prebuilt image is stale or broken

- Pin the workflow or GitLab job to a known-good immutable tag or SHA tag.
- For GitHub Action users, set `force_local_build: true` until GHCR is healthy
  again.
- For GitLab, temporarily swap the job image to a previous tag.

### Live connector fetches fail inside the required check

- Rotate the relevant token following `runbooks/live_connector_operations.md`
- Reduce scope first:
  - GitHub-only precedent via `github_token`
  - Jira or PagerDuty next
  - Slack and Confluence last
- If the merge gate is business-critical, disable the failing connector before
  disabling the gate entirely

## Rollback and recovery

- Fast rollback:
  - switch GitHub or GitLab from `enforce` to `shadow`
  - keep artifact generation enabled so the org still collects blocked-risk data
- Safer forward fix:
  - update the policy preset or inline policy instead of deleting the workflow
  - refresh the knowledge base or pin a known-good container image
- Incident review:
  - archive the blocked decision JSON and markdown summary from CI artifacts
  - link them to the relevant Jira or PagerDuty incident so future gates have
    precedent instead of repeating the same blind spot
