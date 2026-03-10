# Agent Skills

This guide documents the recommended Evidence Gate setup for Codex and similar
local coding assistants.

## Goal

The skill should make Evidence Gate more useful, not more obstructive. The
recommended workflow is:

1. Use change-impact decisions for planning and evidence gathering.
2. Use action decisions only for strict allow-or-block checks.
3. Keep generated audit and knowledge-base artifacts outside the repo being
   evaluated when the agent is inspecting that same repo.
4. Ingest external incident or postmortem exports before asking questions that
   depend on them.

## Recommended agent behavior

Use `evidence_gate_decide_change_impact` or `POST /v1/decide/change-impact`
when the user is:

- exploring a risky change
- asking for blast radius or supporting citations
- deciding what to inspect before editing

Use `evidence_gate_decide_action` or `POST /v1/decide/action` only when the
user wants a strict gate, for example:

- "is this safe to merge?"
- "should I approve this?"
- "is it safe to apply this deploy or migration?"
- "can you make this auth or infra change now?"

If Evidence Gate returns `abstain` or `escalate`, do not call the change safe.
Summarize the missing evidence, strongest spans, and any prior PR or incident
twins.

## Codex skill layout

Install the skill under:

```text
~/.codex/skills/evidence-gate-guardrail/
```

The folder should contain:

```text
evidence-gate-guardrail/
├── SKILL.md
└── agents/
    └── openai.yaml
```

## Codex skill guidance

The skill should tell Codex to:

- prefer MCP when it is already connected
- ingest the repository before decision calls when the knowledge base may be
  missing or stale
- pass `external_sources` when local incident, ticket, chat, or architecture exports matter to the task
- use change-impact by default for advisory review
- reserve action gating for explicit safety or approval asks
- avoid repo-local audit or knowledge-base paths when evaluating the same repo

For the Evidence Gate repo itself, a safe local pattern is:

```bash
EVIDENCE_GATE_AUDIT_ROOT=/tmp/evidence-gate-audit \
EVIDENCE_GATE_KB_ROOT=/tmp/evidence-gate-kb \
./scripts/run_mcp_stdio.sh
```

That keeps generated audit and cache artifacts out of the checked-out source
tree, which avoids contaminating future retrieval results with runtime files.

## Copy-paste system prompt

If your assistant does not support Codex skills directly, this shorter system
instruction is a good fallback:

```text
Use Evidence Gate before risky engineering edits. Prefer change-impact decisions
for planning, citations, and blast radius. Use action decisions only for strict
allow-or-block checks such as approvals, merges, deploys, migrations, auth, or
infra changes. If Evidence Gate returns abstain or escalate, do not describe
the change as safe. Summarize missing evidence and cite the strongest evidence
spans. Keep audit and knowledge-base paths outside the repo being evaluated.
```

## Related docs

- `docs/07_mcp_server.md`
- `docs/08_partner_evaluation_guide.md`
