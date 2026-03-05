#!/usr/bin/env python3
"""
Semantic Scholar API (free tier / no key) helper.

- Default endpoint: /graph/v1/paper/search (relevance search)
- Works without API key.
- If S2_API_KEY is set, it will be attached as x-api-key automatically.

Examples:
  python3 inf-Coding-Assist/semantic_scholar_free.py --query "causal inference" --limit 5
  python3 inf-Coding-Assist/semantic_scholar_free.py --query "LLM agents" --year 2024 --fields "title,year,url,citationCount"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://api.semanticscholar.org/graph/v1/paper/search"


def build_url(query: str, limit: int, offset: int, fields: str, year: str | None, venue: str | None) -> str:
    params = {
        "query": query,
        "limit": str(limit),
        "offset": str(offset),
        "fields": fields,
    }
    if year:
        params["year"] = year
    if venue:
        params["venue"] = venue
    return BASE + "?" + urllib.parse.urlencode(params)


def fetch(url: str, timeout: int = 20, retries: int = 3) -> dict:
    api_key = os.getenv("S2_API_KEY", "").strip()
    headers = {"accept": "application/json", "user-agent": "inf-coding/semantic-scholar-free"}
    if api_key:
        headers["x-api-key"] = api_key

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            last_err = e
            # gentle backoff for free-tier throttling
            sleep_sec = min(2**attempt, 8)
            time.sleep(sleep_sec)

    raise RuntimeError(f"Semantic Scholar request failed after {retries} retries: {last_err}")


def main() -> int:
    p = argparse.ArgumentParser(description="Semantic Scholar free-tier relevance search helper")
    p.add_argument("--query", required=True, help="Search query")
    p.add_argument("--limit", type=int, default=10, help="1-100")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument(
        "--fields",
        default="title,year,url,authors,citationCount,venue,externalIds",
        help="Comma-separated fields",
    )
    p.add_argument("--year", default=None, help="Year filter (e.g. 2025 or 2020-2025)")
    p.add_argument("--venue", default=None, help="Venue filter")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = p.parse_args()

    if args.limit < 1 or args.limit > 100:
        print("--limit must be between 1 and 100", file=sys.stderr)
        return 2

    url = build_url(args.query, args.limit, args.offset, args.fields, args.year, args.venue)
    data = fetch(url)

    if args.pretty:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    # concise output for terminal use
    total = data.get("total")
    print(f"total={total} offset={args.offset} limit={args.limit}")
    for i, paper in enumerate(data.get("data", []), start=1):
        title = paper.get("title", "(no title)")
        year = paper.get("year", "?")
        cc = paper.get("citationCount", 0)
        url = paper.get("url", "")
        print(f"{i:02d}. [{year}] {title} (citations={cc})")
        if url:
            print(f"    {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
