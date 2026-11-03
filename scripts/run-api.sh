#!/usr/bin/env bash

# Resolve the repository from this script so direct calls work from any directory.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Parse configuration as data before replacing this process with Uvicorn.
exec .venv/bin/python scripts/run_api.py
