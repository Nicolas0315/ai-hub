#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INF_DIR="$SCRIPT_DIR"
KATALA_ROOT="$(cd "$INF_DIR/.." && pwd)"

# このスクリプトが想定ディレクトリにいることを保証
if [[ ! -d "$KATALA_ROOT/src" ]]; then
  echo "[guard] Katala ルートを検出できません: $KATALA_ROOT" >&2
  exit 1
fi

# 呼び出し元が inf-Coding 配下であることを要求（絶対入口ガード）
CALLER_DIR="$(pwd)"
case "$CALLER_DIR" in
  "$INF_DIR"|"$INF_DIR"/*) ;;
  *)
    echo "[guard] NG: inf-Coding 経由で実行してください。" >&2
    echo "[guard] 例: cd \"$INF_DIR\" && ./open-katala.sh" >&2
    exit 2
    ;;
esac

# 目印（現フェーズ: cache 側へ記録）
mkdir -p "$INF_DIR/inf-Coding-cache"
echo "$(date -Is) | guard-pass | caller=$CALLER_DIR" >> "$INF_DIR/inf-Coding-cache/activity.log"

echo "$KATALA_ROOT"
