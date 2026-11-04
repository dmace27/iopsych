#!/usr/bin/env bash
# Resolve paths independently of the caller's working directory.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$repo_root/.venv/bin/python" "$repo_root/scripts/run-api.py"
