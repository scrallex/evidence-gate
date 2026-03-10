# Repo Audit and Delivery Gameplan

## Executive Read

This repository is now a real alpha implementation surface for `Evidence Gate`,
not only a planning workspace. That is the good news.

The main repo-quality issue before promotion was not lack of code. It was lack of
discipline around presentation:

- generated runtime outputs were mixed into the repo surface
- the README still read like a planning folder
- key docs still described a pre-build state that is no longer true

Those issues make the project look less mature than it actually is.

## Current repo reality

### What is here now

- a FastAPI service under `app/evidence_gate/`
- structural retrieval and truth-pack verification
- blast radius support for code-oriented questions
- persisted repository knowledge bases
- audit logging for decisions
- knowledge-base lifecycle and maintenance endpoints
- regression tests

### What the alpha already demonstrates

For a target repository, the service can:

1. build a local structural knowledge base
2. retrieve supporting evidence spans
3. surface twin PR or incident cases
4. compute a blast radius
5. decide `admit | abstain | escalate`
6. persist the decision record

That is a meaningful technical preview, not only an idea.

## Repo-quality audit

### What needed correction

1. Generated files should not be presented as source.
2. Runtime knowledge bases under `var/knowledge_bases/` should be treated as
   cache artifacts, not repo assets.
3. Python bytecode and test caches should not be tracked.
4. Exploratory research archives should not be shipped in the public repo.
5. The GitHub landing page should lead with the current alpha and its limits.
6. Planning docs should not contradict the implemented service.

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

That is strong enough to be credible and restrained enough to be honest.

The repo should not yet claim:

- production readiness
- benchmarked superiority across corpora
- a finished MCP product
- a polished self-serve experience

## What is worth showing today

A prospective reviewer can already inspect and run:

- the decision contract
- the API surface
- structural retrieval and verification behavior
- knowledge-base persistence and maintenance flows
- test coverage proving the current slice works

That is enough for:

- technical diligence
- architecture review
- design-partner discussion

It is not yet enough for:

- broad public launch
- paid pilot without guided setup
- independent proof of ROI

The repo should not ship archived QFH or trading papers in the public tree at
all. If historical provenance needs to be retained, keep it in a private
archive so the GitHub surface stays implementation-first.

## Delivery gameplan from this point

### Track 1: repo and packaging hygiene

Goal:
make the repo easy to review and run.

Tasks:

1. Keep runtime outputs out of source control.
2. Keep the README concise and current.
3. Maintain a clean quickstart and sample requests.
4. Add CI and basic linting.
5. Add a one-command local run path such as Docker.

### Track 2: proof of value

Goal:
show that the system is useful on a real engineering corpus.

Tasks:

1. Select one real target repository.
2. Assemble supporting docs, PR notes, and incident material.
3. Create a benchmark set with labeled expectations.
4. Compare against a simple baseline.
5. Publish a short results summary.

### Track 3: partner review package

Goal:
make the system tangible for an external technical reviewer.

Tasks:

1. Prepare a short walkthrough:
   - ingest
   - query
   - change-impact request
   - interpretation of `admit | abstain | escalate`
2. Add a demo script or copy-paste curl flow.
3. Summarize known limitations clearly.
4. Include one evaluation or benchmark summary.
5. Add MCP delivery once the API demo is benchmarked.

## Practical conclusion

This repo is past the "idea only" stage.

The next threshold is not more internal architecture work for its own sake. The
next threshold is external proof:

- clean repo
- repeatable demo
- benchmark evidence
- partner-review package

Once those exist, the project is credible to send to a prospective design
partner in a way that lets them evaluate real value rather than only the thesis.
