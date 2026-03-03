#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" open-shell
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
"$SCRIPT_DIR/order-enforce.sh"
cd "$KATALA_ROOT"
exec "${SHELL:-/bin/bash}"
