#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUST_DIR = ROOT / "rust" / "katala_rust_hotpath"


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> dict:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    return {
        "ok": p.returncode == 0,
        "code": p.returncode,
        "cmd": " ".join(cmd),
        "stdout": (p.stdout or "")[-2000:],
        "stderr": (p.stderr or "")[-2000:],
    }


def main() -> int:
    out: dict[str, object] = {"ok": False, "steps": []}
    steps: list[dict] = []

    maturin = shutil.which("maturin")
    if not maturin:
        out["reason"] = "maturin-not-found"
        out["hint"] = "run inf-Coding-Assist/rust_bootstrap_and_activate.sh to auto-install maturin and retry"
        out["ok"] = False
        out["steps"] = steps
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    steps.append(run([maturin, "develop", "--release"], cwd=RUST_DIR))

    env = os.environ.copy()
    env["KQ_RUST_ONLY"] = "1"

    steps.append(run(["python3", "inf-Coding/inf-Coding-Assist/rust_no_fallback_check.py"], cwd=ROOT, env=env))
    steps.append(run(["python3", "inf-Coding/inf-Coding-Assist/rust_hotpath_parity_check.py"], cwd=ROOT, env=env))
    steps.append(run(["python3", "inf-Coding-Assist/iut_subset_scaffold.py"], cwd=ROOT / "inf-Coding", env={**env, "IUT_STAGED_CHECK": "0"}))

    out["steps"] = [{k: v for k, v in s.items() if k not in {"stdout", "stderr"}} for s in steps]
    out["ok"] = all(s.get("ok") for s in steps)
    if not out["ok"]:
        out["failed"] = [
            {"cmd": s.get("cmd"), "code": s.get("code"), "stderr": s.get("stderr")} for s in steps if not s.get("ok")
        ]

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
