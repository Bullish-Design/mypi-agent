#!/usr/bin/env bash
# Launch the mypi-agent development shell (uses dev/ environment, not the public surface)
set -euo pipefail
cd "$(dirname "$0")"
devenv up -d --from path:./dev
echo
devenv shell --from path:./dev zsh
