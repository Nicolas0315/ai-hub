#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"

"$SCRIPT_DIR/log-to-cache.sh" open-katala "enter shell at $KATALA_ROOT"
cd "$KATALA_ROOT"
exec "${SHELL:-/bin/bash}"
