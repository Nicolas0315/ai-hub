#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" order-enforce
fi

STATE_FILE="$SCRIPT_DIR/inf-Coding-Order/order-state.env"

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
else
  KATALA_ALLOWED=0
  ASSIST_MODE=off
fi

if [[ "${KATALA_ALLOWED:-0}" == "1" && "${ASSIST_MODE:-off}" != "on" ]]; then
  echo "[order] INVALID STATE: katala-on requires assist-on." >&2
  exit 76
fi

if [[ "${KATALA_ALLOWED:-0}" != "1" ]]; then
  echo "[order] Katala is DISABLED by human order (katala-off)." >&2
  exit 77
fi
