#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import subprocess


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "code": p.returncode,
        "ok": p.returncode == 0,
        "stdout": (p.stdout or "")[-1000:],
        "stderr": (p.stderr or "")[-1000:],
    }


def main() -> int:
    checks = []
    checks.append(run(["bash", "-lc", "which rustc || true"]))
    checks.append(run(["bash", "-lc", "which cargo || true"]))
    checks.append(run(["bash", "-lc", "rustc -V"]))
    checks.append(run(["bash", "-lc", "cargo -V"]))
    checks.append(run(["bash", "-lc", "python3 -m pip show maturin || true"]))

    rustc_ok = checks[2]["ok"]
    cargo_ok = checks[3]["ok"]

    advice = []
    if not rustc_ok or not cargo_ok:
        advice.append("rust toolchain appears unhealthy on host (possible rustc segfault)")
        advice.append("recommended: reinstall rustup stable toolchain on clean shell / host reboot")
        advice.append("continue validation in CI rust-hotpath-check while host toolchain is repaired")
    else:
        advice.append("rust toolchain healthy; run iut_next5_steps.py under KQ_RUST_ONLY=1")

    out = {
        "ok": rustc_ok and cargo_ok,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "env": {
            "KQ_RUST_ONLY": os.getenv("KQ_RUST_ONLY", ""),
        },
        "checks": [{k: v for k, v in c.items() if k in {"cmd", "ok", "code", "stdout", "stderr"}} for c in checks],
        "advice": advice,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
