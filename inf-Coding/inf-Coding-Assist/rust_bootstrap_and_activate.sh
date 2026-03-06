#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 2
fi

if ! command -v rustc >/dev/null 2>&1; then
  echo "[rust-bootstrap] rustc not found -> installing rustup toolchain"
  curl https://sh.rustup.rs -sSf | sh -s -- -y
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
elif ! rustc -V >/dev/null 2>&1; then
  echo "[rust-bootstrap] rustc exists but is unhealthy -> reinstalling toolchain"
  rustup toolchain install stable -c rustfmt -c clippy || true
  rustup default stable || true
fi

if ! command -v maturin >/dev/null 2>&1; then
  echo "[rust-bootstrap] maturin not found -> installing with pip --user"
  python3 -m pip install --user --break-system-packages maturin
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[rust-bootstrap] running rust activation pipeline"
cd "$ROOT/inf-Coding"
python3 inf-Coding-Assist/rust_activation_pipeline.py
