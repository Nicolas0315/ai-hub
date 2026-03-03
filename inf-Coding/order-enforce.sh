#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$SCRIPT_DIR/inf-Coding-Order/order-state.env"

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
else
  KATALA_ALLOWED=1
fi

# Invariant checks:
# C) katala-on => assist-on
if [[ "${KATALA_ALLOWED:-0}" == "1" && "${ASSIST_MODE:-off}" != "on" ]]; then
  "$SCRIPT_DIR/log-to-cache.sh" order:block "invalid state: katala-on requires assist-on"
  echo "[order] INVALID STATE: katala-on requires assist-on." >&2
  exit 76
fi

if [[ "${KATALA_ALLOWED:-0}" != "1" ]]; then
  "$SCRIPT_DIR/log-to-cache.sh" order:block "katala disabled by human order"
  echo "[order] Katala is DISABLED by human order (katala-off)." >&2
  exit 77
fi
