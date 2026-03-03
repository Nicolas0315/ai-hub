#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" guard
fi

INF_DIR="$SCRIPT_DIR"
KATALA_ROOT="$(cd "$INF_DIR/.." && pwd)"

if [[ ! -d "$KATALA_ROOT/src" ]]; then
  echo "[guard] Katala ルートを検出できません: $KATALA_ROOT" >&2
  exit 1
fi

CALLER_DIR="$(pwd)"
case "$CALLER_DIR" in
  "$INF_DIR"|"$INF_DIR"/*) ;;
  *)
    echo "[guard] NG: inf-Coding 経由で実行してください。" >&2
    echo "[guard] 例: cd \"$INF_DIR\" && ./open-katala.sh" >&2
    exit 2
    ;;
esac

echo "$KATALA_ROOT"
