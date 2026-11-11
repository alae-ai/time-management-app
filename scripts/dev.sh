#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

HOST="${TM_HOST:-127.0.0.1}"
PORT="${TM_PORT:-4317}"
API_PID=""

cleanup() {
  if [[ -n "$API_PID" ]]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Reuse an already-running API, otherwise start one.
if ! curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null 2>&1; then
  .venv/bin/uvicorn tm.api.app:app --host "$HOST" --port "$PORT" --reload &
  API_PID=$!
fi

if [[ "${TM_API_ONLY:-0}" == "1" || ! -d web/node_modules ]]; then
  if [[ ! -d web/node_modules ]]; then
    echo "Frontend dependencies are missing. Run: cd web && npm install"
  fi
  if [[ -z "$API_PID" ]]; then
    echo "API already running at http://${HOST}:${PORT}"
    exit 0
  fi
  echo "API: http://${HOST}:${PORT}"
  wait "$API_PID"
  exit $?
fi

echo "API: http://${HOST}:${PORT}"
echo "Web: http://${HOST}:5173"
cd web
TM_API_URL="http://${HOST}:${PORT}" npm run dev -- --host "$HOST"
