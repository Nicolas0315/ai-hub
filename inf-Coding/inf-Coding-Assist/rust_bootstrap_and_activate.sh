#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 2
fi

if ! command -v maturin >/dev/null 2>&1; then
  echo "[rust-bootstrap] maturin not found -> installing with pip --user"
  python3 -m pip install --user maturin
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[rust-bootstrap] running rust activation pipeline"
cd "$ROOT/inf-Coding"
python3 inf-Coding-Assist/rust_activation_pipeline.py
