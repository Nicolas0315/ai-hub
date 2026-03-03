#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="$SCRIPT_DIR/inf-Coding-cache"

mkdir -p "$CACHE_DIR"

# READMEは残し、それ以外を削除（手動運用向け）
find "$CACHE_DIR" -mindepth 1 -maxdepth 1 ! -name 'README.md' -exec rm -rf {} +

"$SCRIPT_DIR/log-to-cache.sh" cache-cleaned "manual clean completed"
echo "[cache-clean] done: $CACHE_DIR"
