#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
# Bind locally by default; the synthetic-login route is development-only.
exec npm run dev --workspace @iopsych/web -- --hostname "${WEB_HOST:-127.0.0.1}" --port "${WEB_PORT:-3101}"
