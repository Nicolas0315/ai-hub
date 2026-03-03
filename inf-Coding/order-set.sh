#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR/inf-Coding-Order"
STATE_FILE="$STATE_DIR/order-state.env"

mkdir -p "$STATE_DIR"

# defaults
KATALA_ALLOWED=1
ASSIST_MODE=auto
LAST_UPDATED=""
UPDATED_BY="human"

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

write_state() {
  cat > "$STATE_FILE" <<EOF
KATALA_ALLOWED=$KATALA_ALLOWED
ASSIST_MODE=$ASSIST_MODE
LAST_UPDATED=$LAST_UPDATED
UPDATED_BY=$UPDATED_BY
EOF
}

CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  echo "Usage: ./order-set.sh <clean|katala-off|katala-on|assist-off|assist-on>" >&2
  exit 64
fi

now="$(date -Is)"
UPDATED_BY="human"

case "$CMD" in
  clean)
    "$SCRIPT_DIR/cache-clean.sh"
    "$SCRIPT_DIR/log-to-cache.sh" order "clean by human"
    echo "[order] cache cleaned"
    ;;
  katala-off)
    KATALA_ALLOWED=0
    LAST_UPDATED="$now"
    write_state
    "$SCRIPT_DIR/log-to-cache.sh" order "katala-off"
    echo "[order] Katala usage: OFF"
    ;;
  katala-on)
    KATALA_ALLOWED=1
    LAST_UPDATED="$now"
    write_state
    "$SCRIPT_DIR/log-to-cache.sh" order "katala-on"
    echo "[order] Katala usage: ON"
    ;;
  assist-off)
    ASSIST_MODE=off
    LAST_UPDATED="$now"
    write_state
    "$SCRIPT_DIR/log-to-cache.sh" order "assist-off"
    echo "[order] inf-Coding-Assist: OFF"
    ;;
  assist-on)
    ASSIST_MODE=on
    LAST_UPDATED="$now"
    write_state
    "$SCRIPT_DIR/log-to-cache.sh" order "assist-on"
    echo "[order] inf-Coding-Assist: ON"
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: ./order-set.sh <clean|katala-off|katala-on|assist-off|assist-on>" >&2
    exit 64
    ;;
esac
