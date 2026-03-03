#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR/inf-Coding-Order"
STATE_FILE="$STATE_DIR/order-state.env"

mkdir -p "$STATE_DIR"

CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  echo "Usage: ./order-set.sh <clean|katala-off|katala-on>" >&2
  exit 64
fi

now="$(date -Is)"

case "$CMD" in
  clean)
    "$SCRIPT_DIR/cache-clean.sh"
    "$SCRIPT_DIR/log-to-cache.sh" order "clean by human"
    echo "[order] cache cleaned"
    ;;
  katala-off)
    cat > "$STATE_FILE" <<EOF
KATALA_ALLOWED=0
LAST_UPDATED=$now
UPDATED_BY=human
EOF
    "$SCRIPT_DIR/log-to-cache.sh" order "katala-off"
    echo "[order] Katala usage: OFF"
    ;;
  katala-on)
    cat > "$STATE_FILE" <<EOF
KATALA_ALLOWED=1
LAST_UPDATED=$now
UPDATED_BY=human
EOF
    "$SCRIPT_DIR/log-to-cache.sh" order "katala-on"
    echo "[order] Katala usage: ON"
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: ./order-set.sh <clean|katala-off|katala-on>" >&2
    exit 64
    ;;
esac
