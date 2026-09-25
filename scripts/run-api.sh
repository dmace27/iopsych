#!/usr/bin/env bash

# Load optional local overrides while retaining safe development defaults.
set -euo pipefail

if [[ -f apps/api/.env ]]; then
  set -a
  # shellcheck disable=SC1091 -- the local environment file is intentionally optional.
  source apps/api/.env
  set +a
fi

exec .venv/bin/python -m uvicorn app.main:app \
  --reload \
  --app-dir apps/api \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}" \
  --log-level "${LOG_LEVEL:-info}"
