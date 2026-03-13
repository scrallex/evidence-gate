# Contributing

Thanks for taking a look.

## Local setup

Install the package and dev dependencies:

```bash
python -m pip install -e '.[dev]'
```

## Run the checks

Run the test suite before opening a PR:

```bash
pytest -q
```

If you change the gate, MCP surface, retrieval, or CI wrappers, it is also worth
running the relevant local scripts or workflows called out in the README and
runbooks.

## Scope

Good early contributions:

- bug fixes in retrieval, blast radius, or CI wrappers
- connector hardening
- benchmark improvements
- documentation clarity
- new policy presets or safer defaults

Please keep changes focused. Small PRs are easier to review and safer to
evaluate with the gate.

## Docs

The public docs surface is intentionally small:

- `README.md`
- `VISION.md`
- `GUIDES.md`
- `API.md`
- `BENCHMARKS.md`

Operational runbooks live under `runbooks/` because they are part of the
evidence surface. If you change an operational workflow, update the matching
runbook too.

## Pull requests

- describe what changed and why
- include the relevant command output if you changed behavior or tests
- note any known gaps if you could not fully verify something
