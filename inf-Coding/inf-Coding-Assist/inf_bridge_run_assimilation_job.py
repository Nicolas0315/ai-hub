#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_bridge import run_inf_bridge  # noqa: E402


def main() -> int:
    command = "observation assimilation run"
    bridge = run_inf_bridge(command)
    ctl = bridge.get("observation_assimilation_control") or {}
    job = ctl.get("recommended_job") or {}

    script = str(job.get("script") or "")
    inp = str(job.get("input") or "")
    out = str(job.get("output") or "")
    top_n = int(job.get("top_n_per_genre") or 500)
    if not (script and inp and out):
        print(json.dumps({"ok": False, "reason": "missing_job_spec"}, ensure_ascii=False))
        return 2

    proc = subprocess.run(["python3", script, inp, str(top_n), out], cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        print(json.dumps({"ok": False, "rc": proc.returncode, "stderr": proc.stderr[-1000:]}, ensure_ascii=False))
        return proc.returncode

    print(json.dumps({"ok": True, "control_mode": ctl.get("mode"), "output": out, "stdout": proc.stdout.strip()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
