#!/usr/bin/env bash
set -euo pipefail

# assist-cycle.sh
# Task-unit workflow with mandatory KS + KCS checks,
# 3 cycles of (test/build/fix), and one final unified confirmation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
KATALA_ROOT="$($INF_DIR/guard.sh)"

# Enforce order layers
"$INF_DIR/order-enforce.sh"
STATE_FILE="$INF_DIR/inf-Coding-Order/order-state.env"
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi
if [[ "${ASSIST_MODE:-auto}" != "on" ]]; then
  echo "[assist-cycle] BLOCKED: require 'assist-on'" >&2
  exit 78
fi

TASK_ID="${1:-}"
if [[ -z "$TASK_ID" ]]; then
  echo "Usage: ./inf-Coding-Assist/assist-cycle.sh <task-id> [target-file]" >&2
  exit 64
fi

TARGET_FILE="${2:-src/katala_coding/kcs1a.py}"
cd "$KATALA_ROOT"

CACHE_TASK_DIR="$INF_DIR/inf-Coding-cache/tasks/$TASK_ID"
mkdir -p "$CACHE_TASK_DIR"
# Task-unit context minimization
: > "$CACHE_TASK_DIR/cycle.log"

log(){
  printf '%s | %s\n' "$(date -Is)" "$*" | tee -a "$CACHE_TASK_DIR/cycle.log" >/dev/null
}

run_ks_kcs(){
  python3 - <<'PY' "$TARGET_FILE" "$CACHE_TASK_DIR/ks_kcs.json" "$TASK_ID"
import json,sys,os
from pathlib import Path

target = sys.argv[1]
out = sys.argv[2]
task = sys.argv[3]
root = Path('.').resolve()

# KS
sys.path.insert(0, str(root / 'src' / 'katala_samurai'))
sys.path.insert(0, str(root / 'src'))
ks_ver = None
ks_conf = None
ks_err = None
try:
    from katala_samurai.ks36d import KS36d
    r = KS36d().verify(f"Task {task}: validate coding operation stability")
    ks_ver = r.get('verdict') if isinstance(r, dict) else None
    ks_conf = r.get('confidence') if isinstance(r, dict) else None
except Exception as e:
    ks_err = str(e)

# KCS
kcs_grade = None
kcs_fidelity = None
kcs_err = None
try:
    from katala_coding.kcs1a import KCS1a
    design = f"Task {task}: implement safely with small diff, test/build/fix cycles"
    p = root / target
    if p.exists():
        verdict = KCS1a(project='katala').verify_file(design, str(p))
        kcs_grade = verdict.grade
        kcs_fidelity = verdict.total_fidelity
    else:
        kcs_err = f"target not found: {target}"
except Exception as e:
    kcs_err = str(e)

data = {
    'task_id': task,
    'ks': {'verdict': ks_ver, 'confidence': ks_conf, 'error': ks_err},
    'kcs': {'grade': kcs_grade, 'fidelity': kcs_fidelity, 'error': kcs_err},
}
Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(data, ensure_ascii=False))
PY
}

run_cycle(){
  local cycle="$1"
  log "cycle=$cycle phase=start"

  # mandatory KS + KCS pass per cycle
  run_ks_kcs | tee -a "$CACHE_TASK_DIR/cycle.log" >/dev/null

  local t_rc=0 b_rc=0 f_rc=0
  npm run -s test >/dev/null 2>&1 || t_rc=$?
  npm run -s build >/dev/null 2>&1 || b_rc=$?

  if [[ $t_rc -ne 0 || $b_rc -ne 0 ]]; then
    # light auto-fix path (best effort)
    npm run -s lint -- --fix >/dev/null 2>&1 || f_rc=$?
    npm run -s test >/dev/null 2>&1 || t_rc=$?
    npm run -s build >/dev/null 2>&1 || b_rc=$?
  fi

  log "cycle=$cycle test_rc=$t_rc build_rc=$b_rc fix_rc=$f_rc"
}

# absolute condition: 3 cycles
run_cycle 1
run_cycle 2
run_cycle 3

# one-time final confirmation (3-line fixed format)
LAST_LINE="$(tail -n 1 "$CACHE_TASK_DIR/cycle.log")"
STATUS="SUCCESS"
if grep -q 'test_rc=[1-9]\|build_rc=[1-9]' "$CACHE_TASK_DIR/cycle.log"; then
  STATUS="NEEDS_REVIEW"
fi

echo "RESULT: $STATUS"
echo "DETAIL: task=$TASK_ID target=$TARGET_FILE cycles=3 ks+kcs=enabled"
echo "NEXT: review $CACHE_TASK_DIR/cycle.log and apply focused patch if needed"
