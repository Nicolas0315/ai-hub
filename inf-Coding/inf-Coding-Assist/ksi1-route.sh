#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$#" -eq 0 ]]; then
  echo "Usage: ./inf-Coding-Assist/ksi1-route.sh <command...>" >&2
  exit 64
fi

"$INF_DIR/order-enforce.sh"
export KQ_MANDATORY_GATE=1
export KQ_ALWAYS_ON=1
STATE_FILE="$INF_DIR/inf-Coding-Order/order-state.env"
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi
if [[ "${ASSIST_MODE:-off}" != "on" ]]; then
  echo "[ksi1-route] BLOCKED: require 'assist-on'" >&2
  exit 78
fi

exec python3 "$SCRIPT_DIR/ksi1-router.py" "$@"
