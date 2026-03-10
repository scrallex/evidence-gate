# Release Readiness And Partner Path

## Bottom line

`Evidence Gate` is not yet ready to hand to an outside team as a polished
self-serve product.

It is ready to send as a technical preview to a serious prospect who is willing
to review code, run a guided setup, and evaluate the workflow on a real corpus.

The missing step between "interesting alpha" and "worth piloting" is proof.

## What an external reviewer can do today

With the current repo, a reviewer can:

1. boot the API locally
2. ingest a repository into a knowledge base
3. run change-impact and engineering evidence queries
4. inspect citations, twins, blast radius, and decision outputs
5. inspect the test suite and maintenance controls

That is enough for technical diligence.

## Why this is not yet a strong external package

The key missing pieces are:

### 1. No benchmarked proof

There is no evaluation report yet showing that the system beats a simple
baseline on citation quality, abstention quality, or change-impact usefulness.

### 2. No polished demo corpus

The repo does not yet ship with a canonical demo target or a repeatable example
project that makes first-run experience predictable.

### 3. No simple packaging path

The service runs locally, but there is not yet a one-command Docker or similar
setup for an outside evaluator.

### 4. No MCP delivery yet

The current API is useful, but many prospective users will want to try it from
an agent or coding-assistant workflow directly.

### 5. No evaluation narrative

A prospect needs not only code, but also an answer to:

"Why should I believe this helps more than ordinary repo search or weak RAG?"

## What would make this genuinely worthwhile to send

The minimum credible partner-review package should include:

1. a clean GitHub repo
2. a concise README
3. a one-command local startup path
4. one demo corpus or reproducible demo setup
5. sample requests with expected outputs
6. a short benchmark or evaluation summary
7. a clear list of known limitations

## Suggested path from here

### Step 1: lock the repo surface

Deliverable:
clean technical-preview repo

Tasks:

- keep generated artifacts out of source control
- keep README and core docs current
- add CI for tests
- add Docker or equivalent local run path

### Step 2: create the demo package

Deliverable:
repeatable demo on one real engineering corpus

Tasks:

- choose one target repository
- collect docs, PR notes, and incident material
- add a script or instructions for ingest
- add 5 to 10 canonical demo prompts
- capture example outputs

### Step 3: prove comparative value

Deliverable:
short evaluation report

Tasks:

- create 25 to 50 benchmark questions
- label expected citations and acceptable abstentions
- compare against a simple baseline
- summarize wins, losses, and failure modes

### Step 4: make it partner-usable

Deliverable:
partner technical preview kit

Tasks:

- add MCP support
- add a maintenance history surface to the audit log
- add deployment notes
- add a short "how to adapt this to your repo" guide

### Step 5: define pilot success

Deliverable:
design-partner pilot plan

Tasks:

- define the target workflow
- define how usefulness will be measured
- define what counts as a good abstention
- define what evidence a partner must provide

## Recommended near-term milestone

The next milestone worth optimizing for is:

`A benchmarked technical preview on one real repository with a demo script and a short evaluation summary.`

Once that exists, the repo is no longer only interesting to read. It becomes
something a prospective partner can actually review, try, and build from in a
tangible way.
