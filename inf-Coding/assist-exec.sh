#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"
USE_RUST_CORE="${INF_CODING_USE_RUST_CORE:-0}"

# Python/shell-first fast path is default.
# Enable Rust core only when explicitly requested:
#   INF_CODING_USE_RUST_CORE=1 ./assist-exec.sh <cmd...>
if [[ "$USE_RUST_CORE" == "1" && -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" assist-exec "$@"
fi

export INF_SKIP_APPROVALS="${INF_SKIP_APPROVALS:-1}"

if [[ "$#" -eq 0 ]]; then
  echo "[assist-exec] Usage: ./assist-exec.sh <command...>" >&2
  exit 64
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
STATE_FILE="$SCRIPT_DIR/inf-Coding-Order/order-state.env"

if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

if [[ "${INF_SKIP_APPROVALS}" != "1" && "${ASSIST_MODE:-off}" != "on" ]]; then
  echo "[assist-exec] BLOCKED: require human order 'assist-on'." >&2
  exit 78
fi

cleanup_ephemeral_caches() {
  rm -rf \
    "$SCRIPT_DIR/inf-Coding-cache" \
    "$SCRIPT_DIR/inf-Coding-run/.tmp-audit" \
    "$SCRIPT_DIR/inf-Coding-run/.tmp-goal-history" \
    "$SCRIPT_DIR/inf-Coding-run/.tmp-openalex-cache" \
    "$SCRIPT_DIR/.pytest_cache" \
    "$SCRIPT_DIR/.mypy_cache" \
    "$SCRIPT_DIR/.ruff_cache" \
    "$SCRIPT_DIR/.cache" 2>/dev/null || true

  find "$SCRIPT_DIR/inf-Coding-Assist" "$SCRIPT_DIR/inf-Coding-run" "$KATALA_ROOT/src" \
    -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
}

trap cleanup_ephemeral_caches EXIT

if [[ "${INF_SKIP_APPROVALS}" != "1" ]]; then
  "$SCRIPT_DIR/order-enforce.sh"
fi

cd "$KATALA_ROOT"
set +e
"$@"
RC=$?
set -e

exit $RC
