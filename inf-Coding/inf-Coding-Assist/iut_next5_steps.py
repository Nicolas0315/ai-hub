#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> dict:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "ok": p.returncode == 0,
        "code": p.returncode,
        "stdout": (p.stdout or "")[-1500:],
        "stderr": (p.stderr or "")[-1500:],
    }


def main() -> int:
    steps = []

    # precheck) host rust health
    steps.append(run(["python3", "inf-Coding/inf-Coding-Assist/rust_host_diagnose.py"], cwd=ROOT))

    # 1) Rust extension activation
    steps.append(run(["bash", "inf-Coding-Assist/rust_bootstrap_and_activate.sh"], cwd=ROOT / "inf-Coding"))

    env_rust = os.environ.copy()
    env_rust["KQ_RUST_ONLY"] = "1"

    # 2) no-fallback green
    steps.append(run(["python3", "inf-Coding/inf-Coding-Assist/rust_no_fallback_check.py"], cwd=ROOT, env=env_rust))

    # 3) parity green
    steps.append(run(["python3", "inf-Coding/inf-Coding-Assist/rust_hotpath_parity_check.py"], cwd=ROOT, env=env_rust))

    # 4) rust migration coverage smoke (subset run in rust-only)
    env_smoke = env_rust.copy()
    env_smoke["IUT_STAGED_CHECK"] = "0"
    steps.append(run(["python3", "inf-Coding-Assist/iut_subset_scaffold.py"], cwd=ROOT / "inf-Coding", env=env_smoke))

    # 5) strict-heavy compare (stdout-only)
    steps.append(run(["python3", "inf-Coding/inf-Coding-Assist/strict_heavy_compare_stdout.py"], cwd=ROOT, env=env_smoke))

    ok = all(s["ok"] for s in steps)
    out = {
        "ok": ok,
        "steps": [{k: v for k, v in s.items() if k not in {"stdout", "stderr"}} for s in steps],
    }
    if not ok:
        out["failed"] = [
            {"cmd": s["cmd"], "code": s["code"], "stderr": s["stderr"]} for s in steps if not s["ok"]
        ]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
