# Vision

## One-line product claim

Evidence Gate is a reliability layer for AI agents. It decides whether an
agent has enough structural evidence to answer or act safely.

## The problem

Most agent failures in engineering workflows are not model-magic failures. They
are evidence failures:

- the agent edits code without touching the regression test
- the agent ignores the runbook or prior outage tied to the same change
- the agent changes the wrong file and still sounds plausible
- the workflow warns a human instead of telling the next retry what to fix

That is why the product starts with a gate, not with a general chat interface.

## What makes this different

The closest crowded category is "AI PR reviewer." That is not the right frame
for this repo.

AI PR reviewers mostly explain risk to a human after the patch exists.
Evidence Gate is narrower and more operational:

1. retrieve evidence from code, tests, docs, runbooks, incidents, and prior PRs
2. compute blast radius and policy violations
3. return `admit`, `abstain`, or `escalate`
4. if blocked, return machine-readable `missing_evidence` and `retry_prompt`

The important behavior is the healing loop:

- fail
- explain
- repair
- retry

That is why the stronger story is "compiler for agents," not "copilot for code review."

## Product principles

- Safety before throughput: fail safe when the repo cannot support the action.
- Evidence over vibe: cite real files, incidents, runbooks, and twins.
- Operational fit matters: the gate has to sit in the IDE, CI, or agent loop.
- Repairability matters: a block should become a better next attempt, not a dead end.

## What the alpha is for

Today this repo is suitable for:

- evaluating risky code changes on a real repository
- adding a required check to GitHub or GitLab
- integrating with MCP-native IDE agents
- running shadow-mode pilots for engineering leadership
- demonstrating stakeholder value through the dashboard

It is not yet a production SaaS product.

## Near-term roadmap

- validate the required-check wrappers and test-linking improvements on partner repos
- prove end-to-end uplift against a live framework such as OpenHands or SWE-agent
- harden hosted sync, auth, tenancy, and production controls

## What not to pitch

- "universal AI safety"
- "another AI code reviewer"
- "model research platform"
- "general autonomous software engineer"

The sharp claim is simpler: gate agent actions on evidence, block unsafe ones,
and turn the block into a repair contract.
