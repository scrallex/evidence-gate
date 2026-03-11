<!-- evidence-gate-comment -->
## Evidence Gate: Block (Escalate)

- Decision ID: `4eca9f6d0be64de09d66cbfcd499ecf5`
- Blast radius: 1 files, 0 tests, 0 docs, 0 runbooks
- Failure reason: Action blocked because Evidence Gate safety thresholds were violated: Policy requires supporting test evidence.
- Policy violations: Policy requires supporting test evidence.
- Missing evidence: No supporting test evidence was found for the affected flow.; Safety policy violation: Policy requires supporting test evidence.
- Strongest evidence: .github/actions/evidence-gate/scripts/scaffold_agent_healing_demo.py, billing/api.py, .github/actions/evidence-gate/scripts/publish_agent_healing_demo.py
- Explanation: Decision escalate based on support score 0.65, blast radius of 1 files, and 3 missing evidence flags. Open-source corpus profile ignored enterprise-only runbook and precedent gaps. Safety policy violations: Policy requires supporting test evidence.

### Suggested Retry Prompt

Evidence Gate blocked the previous attempt because: No supporting test evidence was found for the affected flow.; Safety policy violation: Policy requires supporting test evidence.. Write the missing tests or update the supported files, then retry the gate.
