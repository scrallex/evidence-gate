#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

export EVIDENCE_GATE_AUDIT_ROOT="${EVIDENCE_GATE_AUDIT_ROOT:-${REPO_ROOT}/var/audit}"
export EVIDENCE_GATE_KB_ROOT="${EVIDENCE_GATE_KB_ROOT:-${REPO_ROOT}/var/knowledge_bases}"

exec evidence-gate-mcp "$@"
