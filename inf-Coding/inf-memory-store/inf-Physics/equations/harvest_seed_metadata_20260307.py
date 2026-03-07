#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-memory-store/inf-Physics')
EQ = ROOT / 'equations'
RAW = ROOT / 'raw'
RAW.mkdir(parents=True, exist_ok=True)

SEEDS = [
    ('relativity_seed_papers_20260307.json', 'relativity_seed_metadata_20260307.json'),
    ('quantum_seed_papers_20260307.json', 'quantum_seed_metadata_20260307.json'),
]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw-Katala/1.0 (seed metadata harvest)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8', 'ignore'))


def crossref_lookup(title: str, author: str | None, year: int | None) -> dict:
    q = title
    if author:
        q += f' {author}'
    params = {
        'query.bibliographic': q,
        'rows': 3,
        'sort': 'score',
        'order': 'desc',
    }
    url = 'https://api.crossref.org/works?' + urllib.parse.urlencode(params)
    data = fetch_json(url)
    items = (data.get('message') or {}).get('items') or []
    best = None
    for item in items:
        issued = (((item.get('issued') or {}).get('date-parts') or [[None]])[0][0])
        score = item.get('score', 0)
        if year and issued == year:
            score += 50
        title_list = item.get('title') or []
        item_title = title_list[0] if title_list else ''
        if title.lower() in item_title.lower() or item_title.lower() in title.lower():
            score += 30
        cand = {'score2': score, 'item': item}
        if not best or cand['score2'] > best['score2']:
            best = cand
    return best['item'] if best else {}


def normalize_item(seed: dict, item: dict) -> dict:
    authors = []
    for a in item.get('author', []) or []:
        name = ' '.join(x for x in [a.get('given'), a.get('family')] if x)
        if name:
            authors.append(name)
    issued = (((item.get('issued') or {}).get('date-parts') or [[None]])[0][0])
    return {
        'seed_id': seed['seed_id'],
        'seed_title': seed['title'],
        'seed_topic': seed['topic'],
        'matched_title': (item.get('title') or [''])[0],
        'authors': authors,
        'year': issued,
        'doi': item.get('DOI'),
        'type': item.get('type'),
        'publisher': item.get('publisher'),
        'container_title': (item.get('container-title') or [''])[0],
        'url': item.get('URL'),
    }


def process(seed_file: Path, out_file: Path) -> None:
    seeds = json.loads(seed_file.read_text(encoding='utf-8'))['seed_papers']
    out = []
    for seed in seeds:
        author = seed.get('author', [None])[0]
        item = crossref_lookup(seed['title'], author, seed.get('year'))
        out.append(normalize_item(seed, item) if item else {
            'seed_id': seed['seed_id'], 'seed_title': seed['title'], 'seed_topic': seed['topic'], 'matched_title': None,
            'authors': [], 'year': None, 'doi': None, 'type': None, 'publisher': None, 'container_title': None, 'url': None,
        })
        time.sleep(0.3)
    payload = {
        'schema': 'inf-physics-seed-metadata-v1',
        'source_seed_file': str(seed_file.name),
        'record_count': len(out),
        'records': out,
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    for seed_name, out_name in SEEDS:
        process(EQ / seed_name, RAW / out_name)
    print(json.dumps({'ok': True, 'outputs': [out for _, out in SEEDS]}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
