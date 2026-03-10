#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
DATA_ROOT="${REPO_ROOT}/data"
FASTAPI_DIR="${DATA_ROOT}/repos/fastapi"
API_URL="${EVIDENCE_GATE_API_URL:-http://127.0.0.1:8000}"
MCP_URL="${EVIDENCE_GATE_MCP_URL:-http://127.0.0.1:8001/mcp}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command docker
require_command git
require_command curl

mkdir -p "${FASTAPI_DIR%/*}"

if [ ! -d "${FASTAPI_DIR}/.git" ]; then
  git clone --depth 1 https://github.com/fastapi/fastapi "${FASTAPI_DIR}"
else
  git -C "${FASTAPI_DIR}" fetch --depth 1 origin
  git -C "${FASTAPI_DIR}" reset --hard origin/HEAD
fi

(
  cd "${REPO_ROOT}"
  EVIDENCE_GATE_REPO_MOUNT="${FASTAPI_DIR}" docker compose up -d --build
)

echo "Waiting for Evidence Gate API..."
for attempt in $(seq 1 90); do
  if curl -fsS "${API_URL}/health" >/dev/null; then
    break
  fi
  sleep 1
  if [ "${attempt}" -eq 90 ]; then
    echo "Evidence Gate API did not become ready in time." >&2
    exit 1
  fi
done

INGEST_RESPONSE=$(curl -fsS -X POST "${API_URL}/v1/knowledge-bases/ingest" \
  -H "content-type: application/json" \
  -d '{"repo_path": "/workspace/target"}')

echo
echo "Evidence Gate demo sandbox is ready."
echo
echo "Ingest response:"
echo "${INGEST_RESPONSE}"
echo
echo "Copy-paste test commands:"
cat <<'EOF'
curl -X POST http://127.0.0.1:8000/v1/decide/change-impact \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "change_summary": "If we change OAuth2PasswordRequestForm validation behavior, what is impacted?",
    "changed_paths": ["fastapi/security/oauth2.py"]
  }'

curl -X POST http://127.0.0.1:8000/v1/decide/action \
  -H "content-type: application/json" \
  -d '{
    "repo_path": "/workspace/target",
    "action_summary": "Before modifying OAuth2PasswordRequestForm validation, verify the change is supported.",
    "changed_paths": ["fastapi/security/oauth2.py"]
  }'
EOF
echo
echo "FastAPI repo mount: ${FASTAPI_DIR}"
echo "HTTP API: ${API_URL}"
echo "MCP streamable-http: ${MCP_URL}"
