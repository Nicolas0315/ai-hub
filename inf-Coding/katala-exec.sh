#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" katala-exec "$@"
fi

if [[ "$#" -eq 0 ]]; then
  echo "[katala-exec] Usage: ./katala-exec.sh <command...>" >&2
  exit 64
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
cd "$KATALA_ROOT"
"$SCRIPT_DIR/order-enforce.sh"

set +e
"$@"
RC=$?
set -e

exit $RC
