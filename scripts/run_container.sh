#!/bin/sh
set -eu

python -m uvicorn evidence_gate.api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!
python -m evidence_gate.mcp --transport streamable-http --host 0.0.0.0 --port 8001 &
MCP_PID=$!

shutdown() {
  kill "$API_PID" "$MCP_PID" 2>/dev/null || true
}

trap shutdown INT TERM

while kill -0 "$API_PID" 2>/dev/null && kill -0 "$MCP_PID" 2>/dev/null; do
  sleep 1
done

wait "$API_PID" || API_STATUS=$?
API_STATUS=${API_STATUS:-0}
wait "$MCP_PID" || MCP_STATUS=$?
MCP_STATUS=${MCP_STATUS:-0}

shutdown

if [ "$API_STATUS" -ne 0 ]; then
  exit "$API_STATUS"
fi

exit "$MCP_STATUS"
