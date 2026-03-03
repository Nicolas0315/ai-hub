#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="$SCRIPT_DIR/inf-Coding-cache"
LOG_FILE="$CACHE_DIR/activity.log"

mkdir -p "$CACHE_DIR"

EVENT="${1:-event}"
shift || true
DETAIL="${*:-no-detail}"

printf '%s | %s | %s\n' "$(date -Is)" "$EVENT" "$DETAIL" >> "$LOG_FILE"
