#!/usr/bin/env bash

# Install both language ecosystems from a clean clone.
set -euo pipefail

npm ci
bash scripts/install-api.sh

echo "Setup complete. Run 'npm run dev' to start both applications."
