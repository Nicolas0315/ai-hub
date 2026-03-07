#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

TARGET = 10000
OUT_JSONL = Path("inf-Coding/inf-Coding-Assist/observation_doi_harvest_20260306.jsonl")
OUT_STATE = Path("inf-Coding/inf-Coding-Assist/observation_doi_harvest_state_20260306.json")

QUERIES = [
    "hubble tension observation",
    "S8 tension weak lensing observation",
    "muon g-2 measurement",
    "baryon acoustic oscillation measurement",
    "cosmic microwave background anisotropy observation",
    "gravitational wave ringdown test general relativity",
    "neutrino oscillation measurement",
    "dark matter direct detection limit",
    "big bang nucleosynthesis abundance measurement",
    "rare decay flavor anomaly measurement",
    "electric dipole moment upper limit",
    "W boson mass measurement",
]


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "katala-openalex-harvester/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def doi_from_work(w: dict) -> str | None:
    doi = w.get("doi")
    if not doi:
        return None
    doi = str(doi).strip()
    if doi.lower().startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    return doi.lower() if doi else None


def main() -> int:
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if OUT_JSONL.exists():
        with OUT_JSONL.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                d = (rec.get("doi") or "").lower().strip()
                if d:
                    seen.add(d)

    with OUT_JSONL.open("a", encoding="utf-8") as out:
        qidx = 0
        while len(seen) < TARGET:
            q = QUERIES[qidx % len(QUERIES)]
            qidx += 1
            cursor = "*"
            while cursor and len(seen) < TARGET:
                params = {
                    "search": q,
                    "filter": "has_doi:true,type:article",
                    "per-page": "200",
                    "cursor": cursor,
                    "select": "id,doi,display_name,publication_year,primary_location,authorships",
                    "sort": "cited_by_count:desc",
                }
                url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
                try:
                    payload = fetch(url)
                except Exception:
                    time.sleep(2.0)
                    continue

                results = payload.get("results") or []
                for w in results:
                    doi = doi_from_work(w)
                    if not doi or doi in seen:
                        continue
                    rec = {
                        "doi": doi,
                        "title": w.get("display_name"),
                        "year": w.get("publication_year"),
                        "openalex_id": w.get("id"),
                        "source": "openalex",
                        "query": q,
                    }
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    seen.add(doi)
                    if len(seen) % 100 == 0:
                        out.flush()
                        OUT_STATE.write_text(json.dumps({"count": len(seen), "target": TARGET, "updated_at": time.time(), "last_query": q}, ensure_ascii=False, indent=2), encoding="utf-8")
                    if len(seen) >= TARGET:
                        break

                meta = payload.get("meta") or {}
                cursor = meta.get("next_cursor")
                if not results:
                    break
                time.sleep(0.12)

            OUT_STATE.write_text(json.dumps({"count": len(seen), "target": TARGET, "updated_at": time.time(), "last_query": q}, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT_STATE.write_text(json.dumps({"count": len(seen), "target": TARGET, "updated_at": time.time(), "done": True}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "count": len(seen), "target": TARGET, "out": str(OUT_JSONL)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
