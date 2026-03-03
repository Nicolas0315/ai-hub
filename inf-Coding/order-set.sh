#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" order-set "${1:-}"
fi

STATE_DIR="$SCRIPT_DIR/inf-Coding-Order"
STATE_FILE="$STATE_DIR/order-state.env"

mkdir -p "$STATE_DIR"

KATALA_ALLOWED=0
ASSIST_MODE=off
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
    echo "[order] clean is deprecated (no cache/log subsystem)."
    ;;
  katala-off)
    KATALA_ALLOWED=0
    LAST_UPDATED="$now"
    write_state
    echo "[order] Katala usage: OFF"
    ;;
  katala-on)
    KATALA_ALLOWED=1
    ASSIST_MODE=on
    LAST_UPDATED="$now"
    write_state
    echo "[order] Katala usage: ON (assist=$ASSIST_MODE)"
    ;;
  assist-off)
    ASSIST_MODE=off
    KATALA_ALLOWED=0
    LAST_UPDATED="$now"
    write_state
    echo "[order] inf-Coding-Assist: OFF (katala=$KATALA_ALLOWED)"
    ;;
  assist-on)
    ASSIST_MODE=on
    LAST_UPDATED="$now"
    write_state
    echo "[order] inf-Coding-Assist: ON"
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: ./order-set.sh <clean|katala-off|katala-on|assist-off|assist-on>" >&2
    exit 64
    ;;
esac
