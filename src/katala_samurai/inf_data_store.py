from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class BinaryStorageRecord:
    source: str
    title: str
    doi: str | None
    url: str | None
    sha256: str
    bytes: int
    binary_path: str
    metadata_path: str


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_binary_storage_record(file_path: str | Path, source: str, title: str, doi: str | None = None, url: str | None = None, base_dir: str | Path = "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-memory-store") -> BinaryStorageRecord:
    src = Path(file_path)
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    digest = sha256_file(src)
    ext = src.suffix or ".bin"
    binary_name = f"{digest}{ext}"
    metadata_name = f"{digest}.json"

    binary_path = base / binary_name
    metadata_path = base / metadata_name

    if not binary_path.exists():
        binary_path.write_bytes(src.read_bytes())

    meta: dict[str, Any] = {
        "source": source,
        "title": title,
        "doi": doi,
        "url": url,
        "sha256": digest,
        "bytes": binary_path.stat().st_size,
        "binary_path": str(binary_path),
        "metadata_path": str(metadata_path),
    }
    metadata_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return BinaryStorageRecord(**meta)
