#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from collections import defaultdict

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-memory-store/inf-Physics')
NORM = ROOT / 'normalized'
RAW = ROOT / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
SEED_CORPUS = NORM / 'physics_seed_corpus_20260307.json'
OUT_RAW = RAW / 'physics_seed_expansion_pilot_20260307.json'
OUT_INDEX = ROOT / 'indexed' / 'physics_seed_expansion_pilot_index_20260307.json'

TRIAL_PER_CATEGORY = 1000
ROWS_PER_QUERY = 20


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw-Katala/1.0 (physics expansion pilot)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8', 'ignore'))


def crossref_search(title: str, author: str | None, year: int | None) -> list[dict]:
    q = title
    if author:
        q += ' ' + author
    params = {
        'query.bibliographic': q,
        'rows': ROWS_PER_QUERY,
        'sort': 'score',
        'order': 'desc',
    }
    if year:
        params['filter'] = f'from-pub-date:{year-2},until-pub-date:{year+25}'
    url = 'https://api.crossref.org/works?' + urllib.parse.urlencode(params)
    data = fetch_json(url)
    return (data.get('message') or {}).get('items') or []


def normalized_title(t: str | None) -> str:
    return ' '.join((t or '').lower().split())


def source_kind(item: dict) -> str:
    title = normalized_title((item.get('title') or [''])[0])
    cont = normalized_title((item.get('container-title') or [''])[0])
    doi = item.get('DOI') or ''
    if any(x in title for x in ['reprint', 'facsimile', 'faksimile']) or any(x in cont for x in ['reprint', 'facsimile', 'faksimile']):
        return 'reprint'
    if '978-' in doi or 'chapter' in cont:
        return 'chapter'
    return 'journal_or_primary'


def is_peer_review_friendly(item: dict) -> bool:
    typ = item.get('type') or ''
    return typ in {'journal-article', 'proceedings-article', 'book-chapter'}


def item_to_record(seed: dict, item: dict) -> dict:
    authors = []
    for a in item.get('author', []) or []:
        nm = ' '.join(x for x in [a.get('given'), a.get('family')] if x)
        if nm:
            authors.append(nm)
    issued = (((item.get('issued') or {}).get('date-parts') or [[None]])[0][0])
    return {
        'category': seed['category'],
        'theory_domain': seed['theory_domain'],
        'seed_id': seed['seed_id'],
        'seed_topic': seed['topic'],
        'matched_title': (item.get('title') or [''])[0],
        'authors': authors,
        'year': issued,
        'doi': item.get('DOI'),
        'type': item.get('type'),
        'publisher': item.get('publisher'),
        'container_title': (item.get('container-title') or [''])[0],
        'url': item.get('URL'),
        'score': item.get('score'),
        'source_kind': source_kind(item),
        'peer_review_priority': is_peer_review_friendly(item),
    }


def main() -> int:
    seeds = json.loads(SEED_CORPUS.read_text(encoding='utf-8'))['records']
    out = []
    seen_doi = set()
    seen_title_year = set()
    counts = defaultdict(int)
    for seed in seeds:
        if counts[seed['category']] >= TRIAL_PER_CATEGORY:
            continue
        author = (seed.get('authors') or [None])[0]
        items = crossref_search(seed['title'], author, seed.get('year'))
        for item in items:
            rec = item_to_record(seed, item)
            doi = rec.get('doi')
            title_year = (normalized_title(rec.get('matched_title')), rec.get('year'))
            if doi and doi in seen_doi:
                continue
            if title_year in seen_title_year:
                continue
            if counts[seed['category']] >= TRIAL_PER_CATEGORY:
                break
            out.append(rec)
            if doi:
                seen_doi.add(doi)
            seen_title_year.add(title_year)
            counts[seed['category']] += 1
        time.sleep(0.25)

    payload = {
        'schema': 'inf-physics-seed-expansion-pilot-v1',
        'record_count': len(out),
        'records': out,
    }
    OUT_RAW.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    index = {
        'schema': 'inf-physics-seed-expansion-pilot-index-v1',
        'by_category': dict(counts),
        'peer_review_priority_count': sum(1 for r in out if r['peer_review_priority']),
        'record_count': len(out),
    }
    OUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'record_count': len(out), 'by_category': dict(counts)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
