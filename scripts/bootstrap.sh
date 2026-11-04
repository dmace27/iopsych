#!/usr/bin/env bash

# Install both language ecosystems from a clean clone.
set -euo pipefail

npm ci
bash scripts/install-api.sh

echo "Dependencies installed. Follow README.md to copy configuration and prepare the database."
