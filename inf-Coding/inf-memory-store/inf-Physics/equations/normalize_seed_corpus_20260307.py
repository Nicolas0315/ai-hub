#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-memory-store/inf-Physics')
RAW = ROOT / 'raw'
NORM = ROOT / 'normalized'
INDEX = ROOT / 'indexed'
NORM.mkdir(parents=True, exist_ok=True)
INDEX.mkdir(parents=True, exist_ok=True)

INPUTS = [
    ('relativity_seed_metadata_20260307.json', 'Category1', 'relativity'),
    ('quantum_seed_metadata_20260307.json', 'Category2', 'quantum'),
]


def source_kind(rec: dict) -> str:
    title = (rec.get('matched_title') or '').lower()
    container = (rec.get('container_title') or '').lower()
    if any(x in title for x in ['faksimile', 'facsimile', 'reprint']) or any(x in container for x in ['reprint', 'faksimile']):
        return 'reprint'
    if '978-' in (rec.get('doi') or '') or 'chapter' in container:
        return 'chapter'
    return 'journal_or_primary'


def normalize_file(name: str, category: str, theory_domain: str) -> list[dict]:
    obj = json.loads((RAW / name).read_text(encoding='utf-8'))
    out = []
    for r in obj['records']:
        out.append({
            'seed_id': r['seed_id'],
            'category': category,
            'theory_domain': theory_domain,
            'topic': r['seed_topic'],
            'title': r['matched_title'] or r['seed_title'],
            'seed_title': r['seed_title'],
            'authors': r.get('authors') or [],
            'year': r.get('year'),
            'doi': r.get('doi'),
            'url': r.get('url'),
            'publisher': r.get('publisher'),
            'container_title': r.get('container_title'),
            'source_kind': source_kind(r),
            'doi_present': bool(r.get('doi')),
        })
    return out


def main() -> int:
    records = []
    for name, category, theory_domain in INPUTS:
        records.extend(normalize_file(name, category, theory_domain))

    corpus = {
        'schema': 'inf-physics-seed-corpus-v1',
        'record_count': len(records),
        'records': records,
    }
    (NORM / 'physics_seed_corpus_20260307.json').write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding='utf-8')

    index = {
        'schema': 'inf-physics-seed-corpus-index-v1',
        'by_category': {},
        'by_theory_domain': {},
        'by_topic': {},
        'doi_present_count': sum(1 for r in records if r['doi_present']),
        'record_count': len(records),
    }
    for r in records:
        index['by_category'].setdefault(r['category'], []).append(r['seed_id'])
        index['by_theory_domain'].setdefault(r['theory_domain'], []).append(r['seed_id'])
        index['by_topic'].setdefault(r['topic'], []).append(r['seed_id'])
    (INDEX / 'physics_seed_corpus_index_20260307.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'record_count': len(records)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
