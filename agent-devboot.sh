#!/usr/bin/env bash
# Launch the mypi-agent dev shell for agent use (no background processes)
set -euo pipefail
cd "$(dirname "$0")/dev"
devenv shell -- "$@"
