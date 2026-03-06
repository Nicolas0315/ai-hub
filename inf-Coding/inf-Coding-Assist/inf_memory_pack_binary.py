#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_data_store import build_binary_storage_record  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack peer-reviewed source file into inf-memory binary store")
    ap.add_argument("--file", required=True, help="Path to source file (pdf/bin)")
    ap.add_argument("--source", required=True, choices=["openalex", "crossref", "pubmed"])
    ap.add_argument("--title", required=True)
    ap.add_argument("--doi", default=None)
    ap.add_argument("--url", default=None)
    args = ap.parse_args()

    rec = build_binary_storage_record(
        file_path=args.file,
        source=args.source,
        title=args.title,
        doi=args.doi,
        url=args.url,
    )
    print(json.dumps(rec.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
