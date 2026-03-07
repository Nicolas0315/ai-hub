#!/usr/bin/env python3
from __future__ import annotations

import os
import sys


def mark(text: str) -> str:
    if os.getenv("INF_CODING_PASSED") == "1":
        if text.startswith("[inf-Coding通過]"):
            return text
        return f"[inf-Coding通過] {text}"
    return text


def main() -> int:
    data = sys.stdin.read()
    sys.stdout.write(mark(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
