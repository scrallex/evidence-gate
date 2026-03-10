# Repo Audit and Delivery Gameplan

## Executive Read

This repository is a real alpha implementation surface for `Evidence Gate`, not
only a planning workspace. It also now has one concrete public proof surface:
the checked-in FastAPI benchmark.

The main repo-quality issue before promotion was not lack of code. It was lack
of discipline around presentation:

- generated runtime outputs were mixed into the repo surface
- the README still read like a planning folder
- key docs still described a pre-build or pre-benchmark state

Those issues made the project look less mature than it actually was.

## Current repo reality

### What is here now

- a FastAPI service under `app/evidence_gate/`
- structural retrieval and truth-pack verification
- blast radius support for code-oriented questions
- persisted repository knowledge bases
- audit logging for decisions
- knowledge-base lifecycle and maintenance endpoints
- regression tests
- a reproducible FastAPI benchmark and checked-in report

### What the alpha already demonstrates

For a target repository, the service can:

1. build a local structural knowledge base
2. retrieve supporting evidence spans
3. surface twin PR or incident cases
4. compute a blast radius
5. decide `admit | abstain | escalate`
6. persist the decision record

That is a meaningful technical preview, not only an idea.

### What the benchmark already demonstrates

On the checked-in 50-case FastAPI slice:

- structural binary accuracy is 84.00%
- baseline binary accuracy is 76.00%
- structural false-admit rate is 0.00%
- baseline false-admit rate is 48.00%

That does not prove universal superiority. It does prove the product wedge:
Evidence Gate is materially safer when evidence is weak.

## Repo-quality audit

### What needed correction

1. Generated files should not be presented as source.
2. Runtime knowledge bases under `var/knowledge_bases/` should be treated as
   cache artifacts, not repo assets.
3. Python bytecode and test caches should not be tracked.
4. Exploratory research archives should not be shipped in the public repo.
5. The GitHub landing page should lead with the current alpha and its limits.
6. Planning docs should not contradict the implemented service or checked-in benchmark.

### What a professional presentation requires

- a clean source tree
- a concise README
- honest current-state language
- clear separation between runtime output and source
- a short path from repo clone to first useful request

## Promotion-ready posture

The right public claim for this repo is:

`Evidence Gate: The Reliability Layer for AI Agents.`

The first workflow used to demonstrate that claim is engineering change
intelligence.

That is strong enough to be differentiated and restrained enough to be honest.

The repo should not yet claim:

- production readiness
- benchmarked superiority across many corpora
- mature MCP ecosystem coverage
- a polished self-serve evaluator experience

## What is worth showing today

A prospective reviewer can already inspect and run:

- the decision contract
- the API surface
- the MCP surface for local agent and IDE use
- structural retrieval and verification behavior
- knowledge-base persistence and maintenance flows
- test coverage proving the current slice works
- the FastAPI benchmark report showing low false-admit behavior

That is enough for:

- technical diligence
- architecture review
- design-partner discussion

It is not yet enough for:

- broad public launch
- paid pilot without guided setup
- independent proof of ROI across customer corpora

The repo should not ship archived exploratory papers or internal whitepapers in
the public tree at all. If historical provenance needs to be retained, keep it
in a private archive so the GitHub surface stays implementation-first.

## Delivery gameplan from this point

### Track 1: evaluator kit and packaging

Goal:
make the benchmarked alpha easy for an outside engineer to run.

Tasks:

1. Keep runtime outputs out of source control.
2. Keep the README and core docs current.
3. Add CI for tests.
4. Keep Docker and Compose as the one-command local run path.
5. Keep the demo script and partner walkthrough current.

### Track 2: workflow placement

Goal:
put Evidence Gate into the path where agents and engineers already work.

Tasks:

1. Harden MCP delivery for coding agents and IDEs.
2. Reuse the existing decision contract rather than creating a parallel interface.
3. Add a sample auth or session change-impact walkthrough.
4. Document how a partner points the system at a private repo.
5. Capture known limitations clearly so setup expectations stay honest.

### Track 3: action gating

Goal:
turn the service from advisory intelligence into a delivery-path guardrail.

Tasks:

1. Validate `POST /v1/decide/action` on real CI workflows.
2. Add GitHub and GitLab required-check integration.
3. Fail or escalate when blast radius is high and evidence coverage is weak.
4. Emit citations and missing-evidence reasons in PR feedback.
5. Extend the audit log for repeated gating runs.

### Track 4: broader enterprise memory

Goal:
connect code-change decisions to the surrounding institutional record.

Tasks:

1. Add Jira, PagerDuty or Slack, and Confluence connectors.
2. Link AST-derived blast radius to external incident history.
3. Re-rank twins across code, docs, tickets, and postmortems.
4. Re-benchmark on partner-shaped corpora once connectors exist.

## Practical conclusion

This repo is past the "idea only" stage and past the "unproven alpha" stage on
one public corpus.

The next threshold is not more internal architecture work for its own sake. The
next threshold is packaging and workflow placement:

- clean repo
- repeatable evaluator kit
- MCP integration
- CI gating path
- partner-review package

Once those exist, the project is credible to send to a prospective design
partner in a way that lets them evaluate practical value rather than only the
thesis.
