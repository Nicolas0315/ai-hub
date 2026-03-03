#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$#" -eq 0 ]]; then
  echo "[katala-exec] Usage: ./katala-exec.sh <command...>" >&2
  exit 64
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
cd "$KATALA_ROOT"

"$SCRIPT_DIR/order-enforce.sh"

CMD_RAW="$*"
if command -v sha256sum >/dev/null 2>&1; then
  CMD_HASH="$(printf '%s' "$CMD_RAW" | sha256sum | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  CMD_HASH="$(printf '%s' "$CMD_RAW" | shasum -a 256 | awk '{print $1}')"
else
  CMD_HASH="hash-unavailable"
fi

"$SCRIPT_DIR/log-to-cache.sh" katala-exec:start "cmd_hash=$CMD_HASH argc=$#"

# inf-Coding経由でのみ Katala コマンドを実行するラッパー
set +e
"$@"
RC=$?
set -e

"$SCRIPT_DIR/log-to-cache.sh" katala-exec:end "rc=$RC cmd_hash=$CMD_HASH argc=$#"
exit $RC
