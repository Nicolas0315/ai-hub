#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_BIN="$SCRIPT_DIR/inf-Coding-core/target/release/inf-coding-core"

if [[ -x "$CORE_BIN" ]]; then
  exec "$CORE_BIN" katala-exec "$@"
fi

if [[ "$#" -eq 0 ]]; then
  echo "[katala-exec] Usage: ./katala-exec.sh <command...>" >&2
  exit 64
fi

# Mandatory KL gate for router-external execution path (fail-close)
# Compatibility note: env/packet keys remain KQ_* until lower layers are fully renamed.
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
fi

KATALA_ROOT="$($SCRIPT_DIR/guard.sh)"
cd "$KATALA_ROOT"
"$SCRIPT_DIR/order-enforce.sh"

set +e
"$@"
RC=$?
set -e

exit $RC
