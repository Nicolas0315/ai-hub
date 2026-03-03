#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" assist-exec "$@"
fi

if [[ "$#" -eq 0 ]]; then
  echo "[assist-exec] Usage: ./assist-exec.sh <command...>" >&2
  exit 64
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
STATE_FILE="$SCRIPT_DIR/inf-Coding-Order/order-state.env"

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

if [[ "${ASSIST_MODE:-off}" != "on" ]]; then
  echo "[assist-exec] BLOCKED: require human order 'assist-on'." >&2
  exit 78
fi

"$SCRIPT_DIR/order-enforce.sh"

cd "$KATALA_ROOT"
set +e
"$@"
RC=$?
set -e

exit $RC
