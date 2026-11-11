#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

exec .venv/bin/uvicorn tm.api.app:app --host "${TM_HOST:-127.0.0.1}" --port "${TM_PORT:-4317}" --reload
