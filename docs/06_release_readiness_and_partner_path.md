# Release Readiness And Partner Path

## Bottom line

`Evidence Gate` is ready today as a benchmarked technical preview for a serious
design partner or technical reviewer.

It is not yet ready as a polished self-serve product or production deployment.
The missing step is no longer basic proof of concept. The missing step is
packaging and workflow placement.

## What evidence exists today

The repo already includes one public proof surface:

- a reproducible FastAPI retrieval-and-decision benchmark over 50 cases
- 84.00% structural binary accuracy versus 76.00% for the baseline
- 0.00% structural false-admit rate versus 48.00% for the baseline

That is meaningful because the product promise is not "retrieve something." It
is "do not admit when the evidence is weak."

## What an external reviewer can do today

With the current repo, a reviewer can:

1. boot the API locally
2. boot the MCP server locally over `stdio` or `streamable-http`
3. ingest a repository into a knowledge base
4. run change-impact and engineering evidence queries
5. inspect citations, twins, blast radius, and decision outputs
6. inspect the test suite and maintenance controls
7. inspect the checked-in benchmark report and rerun it

That is enough for technical diligence and a guided design-partner evaluation.

## Why this is still not a strong self-serve package

The key missing pieces are:

### 1. Evaluator kit is still early

The repo now includes Docker, Compose, and a demo sandbox script, but it still
needs more validation against partner-shaped private corpora.

### 2. MCP packaging needs hardening

The server now exposes a first-cut MCP surface, but it still needs more
copy-paste setup examples, broader client validation, and operational guidance
for path-resolution issues in local IDE clients.

### 3. Action-gating path is implemented but not widely integrated

The service now exposes `POST /v1/decide/action` plus a GitHub Action wrapper,
but it still needs field validation on real CI workflows and clearer policy
defaults for blocking merges.

### 4. Partner adaptation still needs proof on private corpora

The guide now exists, but the product still needs validation on real private
repos with partner-specific docs, runbooks, and incident history.

### 5. No broader enterprise connectors yet

The current system is repository-local. The long-term institutional-memory
story needs connectors for Jira, PagerDuty or Slack, and Confluence.

## What would make this genuinely worthwhile to send broadly

The minimum credible partner-review package should include:

1. a clean GitHub repo
2. a concise README
3. a one-command local startup path
4. one reproducible demo corpus or setup guide
5. sample requests with expected outputs
6. a short benchmark summary
7. a clear list of known limitations
8. documented MCP setup for at least one agent workflow

## Suggested path from here

### Step 1: package the benchmarked alpha

Deliverable:
technical-preview evaluator kit

Tasks:

- validate Docker and Compose on a few partner-shaped environments
- keep README and benchmark summary tight
- keep the demo sandbox current
- add CI for tests

### Step 2: place it in the agent workflow

Deliverable:
MCP-backed design-partner preview

Tasks:

- add example agent configuration
- keep the API and MCP contract aligned
- document a private-repo evaluation flow
- validate the setup against a few target clients such as Cursor and Cline

### Step 3: gate actions in delivery

Deliverable:
CI action-gating preview

Tasks:

- harden `POST /v1/decide/action` policies
- validate GitHub or GitLab check integration
- define escalation rules using blast radius plus missing evidence
- emit auditable machine-readable outputs

### Step 4: expand to enterprise memory

Deliverable:
multi-source reliability layer

Tasks:

- add Jira, incident, and architecture-doc connectors
- link code changes to operational history
- re-benchmark on multi-source corpora

## Recommended near-term milestone

The next milestone worth optimizing for is:

`A partner-validated evaluator kit with Docker, a demo walkthrough, MCP delivery, and a working CI guardrail on one real repository.`

Once that exists, the repo becomes easy to try in the exact environment where
the product claim matters: before an AI agent answers or acts.
