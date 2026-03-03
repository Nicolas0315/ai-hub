#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$#" -eq 0 ]]; then
  echo "[katala-exec] Usage: ./katala-exec.sh <command...>" >&2
  exit 64
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
cd "$KATALA_ROOT"

"$SCRIPT_DIR/log-to-cache.sh" katala-exec:start "$*"

# inf-Coding経由でのみ Katala コマンドを実行するラッパー
set +e
"$@"
RC=$?
set -e

"$SCRIPT_DIR/log-to-cache.sh" katala-exec:end "rc=$RC cmd=$*"
exit $RC
