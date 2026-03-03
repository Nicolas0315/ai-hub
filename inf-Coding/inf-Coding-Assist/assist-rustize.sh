#!/usr/bin/env bash
set -euo pipefail

# assist-rustize.sh
# Heavy-processing migration helper (TS/Python hot path -> Rust candidate list)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
KATALA_ROOT="$(cd "$INF_DIR/.." && pwd)"

"$INF_DIR/order-enforce.sh"
STATE_FILE="$INF_DIR/inf-Coding-Order/order-state.env"
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi
if [[ "${ASSIST_MODE:-off}" != "on" ]]; then
  echo "[assist-rustize] BLOCKED: require 'assist-on'" >&2
  exit 78
fi

cd "$KATALA_ROOT"

echo "# Rustization Candidates ($(date -Is))"
echo "# Heuristic: large files in src likely to contain hot paths"
find src -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.py' \) -printf '%s %p\n' | sort -nr | head -n 40
echo
echo "# Existing Rust modules"
find . -maxdepth 3 -type f \( -path './rust_accel/*' -o -path './ks46/*' -o -path './ks42_core/*' \) 2>/dev/null | sort
echo
echo "RESULT: SUCCESS"
echo "DETAIL: rustization candidates emitted to stdout only (memoryless mode)"
echo "NEXT: pick top 3 hot paths and port incrementally to Rust"
