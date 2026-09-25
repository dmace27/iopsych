#!/usr/bin/env bash

# Keep the API environment local to the repository so root npm scripts can use it.
set -euo pipefail

python_bin="${PYTHON_BIN:-python3}"

# Fail early with a useful message instead of surfacing an opaque dependency error.
"${python_bin}" -c 'import sys; assert (3, 12) <= sys.version_info[:2] < (3, 15), "Python 3.12-3.14 is required"'

"${python_bin}" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --upgrade --upgrade-strategy eager -r apps/api/requirements-dev.txt
