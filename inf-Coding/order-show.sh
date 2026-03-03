#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$SCRIPT_DIR/inf-Coding-Order/order-state.env"

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
else
  KATALA_ALLOWED=1
  LAST_UPDATED=""
  UPDATED_BY="unknown"
fi

echo "KATALA_ALLOWED=$KATALA_ALLOWED"
echo "LAST_UPDATED=${LAST_UPDATED:-}"
echo "UPDATED_BY=${UPDATED_BY:-}"
