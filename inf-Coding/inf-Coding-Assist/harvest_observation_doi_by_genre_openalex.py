#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

TARGET_PER_GENRE = 10000
# Stop a genre early when consecutive query passes add zero new DOI rows.
NO_GROWTH_STOP_QUERIES = 3
ROOT = Path("inf-Coding/inf-Coding-Assist")
STATE = ROOT / "observation_doi_by_genre_state_20260306.json"

GENRE_QUERIES = {
    "cosmology_tensions": [
        "hubble tension observation", "S8 tension weak lensing", "CMB BAO cosmology constraints", "sigma8 tension"
    ],
    "precision_anomalies": [
        "muon g-2 measurement", "W boson mass measurement", "electric dipole moment upper limit", "precision anomaly particle physics"
    ],
    "flavor_physics": [
        "RK RK* anomaly measurement", "rare decay B meson measurement", "CKM fit tension", "flavor physics observation"
    ],
    "neutrino_sector": [
        "neutrino oscillation measurement", "neutrino CP violation measurement", "neutrino mass hierarchy observation", "delta m2 neutrino"
    ],
    "gw_strong_gravity": [
        "gravitational wave ringdown test", "strong gravity test ligo", "black hole merger observation", "general relativity test gravitational wave"
    ],
    "dark_sector": [
        "dark matter direct detection limit", "axion search observation", "dark sector constraint", "indirect dark matter detection"
    ],
    "early_universe_bbn": [
        "big bang nucleosynthesis abundance measurement", "N_eff constraint observation", "primordial helium deuterium measurement", "early universe observation"
    ],
}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "katala-openalex-genre-harvester/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def norm_doi(v: str | None) -> str | None:
    if not v:
        return None
    d = str(v).strip().lower()
    if d.startswith("https://doi.org/"):
        d = d[len("https://doi.org/"):]
    return d or None


def load_seen(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                d = norm_doi(rec.get("doi"))
                if d:
                    out.add(d)
            except Exception:
                continue
    return out


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def harvest_genre(genre: str, queries: list[str]) -> dict:
    out_path = ROOT / f"observation_doi_{genre}_20260306.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = load_seen(out_path)

    no_growth_streak = 0
    stop_reason = "target_reached"

    with out_path.open("a", encoding="utf-8") as out:
        q_idx = 0
        while len(seen) < TARGET_PER_GENRE:
            q = queries[q_idx % len(queries)]
            q_idx += 1
            cursor = "*"
            before_query = len(seen)
            while cursor and len(seen) < TARGET_PER_GENRE:
                params = {
                    "search": q,
                    "filter": "has_doi:true,type:article",
                    "per-page": "200",
                    "cursor": cursor,
                    "select": "id,doi,display_name,publication_year,publication_date",
                    "sort": "publication_date:desc",
                }
                url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
                try:
                    payload = fetch(url)
                except Exception:
                    time.sleep(1.5)
                    continue
                results = payload.get("results") or []
                for w in results:
                    d = norm_doi(w.get("doi"))
                    if not d or d in seen:
                        continue
                    rec = {
                        "genre": genre,
                        "doi": d,
                        "title": w.get("display_name"),
                        "publication_year": w.get("publication_year"),
                        "publication_date": w.get("publication_date"),
                        "openalex_id": w.get("id"),
                        "source": "openalex",
                        "query": q,
                    }
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    seen.add(d)
                    if len(seen) % 200 == 0:
                        out.flush()
                meta = payload.get("meta") or {}
                cursor = meta.get("next_cursor")
                if not results:
                    break
                time.sleep(0.08)

            added = len(seen) - before_query
            if added == 0:
                no_growth_streak += 1
            else:
                no_growth_streak = 0

            if no_growth_streak >= NO_GROWTH_STOP_QUERIES:
                stop_reason = f"no_growth_{NO_GROWTH_STOP_QUERIES}_queries"
                break

    if len(seen) < TARGET_PER_GENRE and stop_reason == "target_reached":
        stop_reason = "source_exhausted_or_limited"

    return {
        "genre": genre,
        "count": len(seen),
        "target": TARGET_PER_GENRE,
        "out": str(out_path),
        "stop_reason": stop_reason,
        "no_growth_stop_queries": NO_GROWTH_STOP_QUERIES,
    }


def main() -> int:
    state = {"started_at": time.time(), "target_per_genre": TARGET_PER_GENRE, "genres": {}}
    save_state(state)
    for genre, queries in GENRE_QUERIES.items():
        res = harvest_genre(genre, queries)
        state["genres"][genre] = res
        state["updated_at"] = time.time()
        save_state(state)
    state["done"] = True
    state["finished_at"] = time.time()
    save_state(state)
    print(json.dumps({"ok": True, "state": str(STATE), "genres": state["genres"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
