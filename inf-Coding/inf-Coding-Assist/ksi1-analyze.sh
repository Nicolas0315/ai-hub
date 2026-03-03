#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

"$INF_DIR/order-enforce.sh"
STATE_FILE="$INF_DIR/inf-Coding-Order/order-state.env"
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi
if [[ "${ASSIST_MODE:-off}" != "on" ]]; then
  echo "[ksi1-analyze] BLOCKED: require 'assist-on'" >&2
  exit 78
fi

python3 - <<'PY'
import json, sys
sys.path.insert(0, '/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')
from katala_samurai.inf_coding_adapter import summarize_bridge
print(json.dumps(summarize_bridge(limit=1000), ensure_ascii=False, indent=2))
PY
