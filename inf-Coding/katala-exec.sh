#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTER_SH="$SCRIPT_DIR/inf-Coding-Assist/ksi1-route.sh"

if [[ "$#" -eq 0 ]]; then
  echo "[katala-exec] Usage: ./katala-exec.sh <command...>" >&2
  exit 64
fi

# Mandatory KL gate for router-external execution path (fail-close)
# Compatibility note: env/packet keys remain KQ_* until lower layers are fully renamed.
export KQ_MANDATORY_GATE=1
export KQ_ALWAYS_ON=1
KQ_MANDATORY_GATE="${KQ_MANDATORY_GATE:-1}"
if [[ "$KQ_MANDATORY_GATE" =~ ^(1|true|yes|on)$ ]]; then
  if [[ -z "${KQ_INPUT_PACKET_JSON:-}" ]]; then
    echo "[katala-exec] blocked: missing KQ_INPUT_PACKET_JSON under mandatory KQ gate" >&2
    exit 74
  fi
  if ! python3 - <<'PY' >/dev/null 2>&1
import json, os, sys
raw=os.getenv('KQ_INPUT_PACKET_JSON','').strip()
try:
    json.loads(raw)
except Exception:
    sys.exit(1)
sys.exit(0)
PY
  then
    echo "[katala-exec] blocked: invalid KQ_INPUT_PACKET_JSON under mandatory KQ gate" >&2
    exit 74
  fi
  if [[ -z "${KSI_SOLVER_UNIT_JSON:-}" ]]; then
    echo "[katala-exec] blocked: missing KSI_SOLVER_UNIT_JSON under mandatory KQ gate" >&2
    exit 74
  fi
  if ! python3 - <<'PY' >/dev/null 2>&1
import json, os, sys
raw=os.getenv('KSI_SOLVER_UNIT_JSON','').strip()
try:
    data=json.loads(raw)
except Exception:
    sys.exit(1)
gate=(data.get('mandatory_gate') or {})
if not bool(gate.get('required')):
    sys.exit(1)
sys.exit(0)
PY
  then
    echo "[katala-exec] blocked: invalid KSI_SOLVER_UNIT_JSON under mandatory KQ gate" >&2
    exit 74
  fi
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

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
trap cleanup_ephemeral_caches EXIT
"$SCRIPT_DIR/order-enforce.sh"

if [[ "${KL_PASSED:-0}" != "1" ]]; then
  exec "$ROUTER_SH" "$@"
fi

cd "$KATALA_ROOT"

set +e
"$@"
RC=$?
set -e

exit $RC
