#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
STATE_FILE="$SCRIPT_DIR/inf-Coding-Order/order-state.env"

if [[ "$#" -eq 0 ]]; then
  echo "[assist-exec] Usage: ./assist-exec.sh <command...>" >&2
  exit 64
fi

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

# 1) assist-off のときは絶対に使わない
if [[ "${ASSIST_MODE:-auto}" == "off" ]]; then
  "$SCRIPT_DIR/log-to-cache.sh" assist:block "assist disabled by human order"
  echo "[assist-exec] DISABLED by human order (inf-Coding-Assist-off)." >&2
  exit 78
fi

# Katala 利用可否も強制
"$SCRIPT_DIR/order-enforce.sh"

cd "$KATALA_ROOT"

RAW_CMD="$*"
if command -v sha256sum >/dev/null 2>&1; then
  CMD_HASH="$(printf '%s' "$RAW_CMD" | sha256sum | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  CMD_HASH="$(printf '%s' "$RAW_CMD" | shasum -a 256 | awk '{print $1}')"
else
  CMD_HASH="hash-unavailable"
fi

"$SCRIPT_DIR/log-to-cache.sh" assist-exec:start "cmd_hash=$CMD_HASH argc=$#"

set +e
"$@"
RC=$?
set -e

"$SCRIPT_DIR/log-to-cache.sh" assist-exec:end "rc=$RC cmd_hash=$CMD_HASH argc=$#"
exit $RC
