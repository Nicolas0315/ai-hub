from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any

TARGET_DATABASES = {
    "jstor": "https://www.jstor.org",
    "springer": "https://link.springer.com",
    "web_of_science": "https://www.webofscience.com",
}


def _fetch(url: str, timeout: float = 4.0) -> tuple[str, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Katala-Quantum/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (r.geturl() or url, r.read(250000), (r.headers.get("Content-Type") or "").lower())


def check_reachability() -> dict[str, Any]:
    out: dict[str, Any] = {"targets": {}, "reachable": []}
    for name, url in TARGET_DATABASES.items():
        try:
            final_url, _, _ = _fetch(url, timeout=6.0)
            out["targets"][name] = {"ok": True, "url": url, "final_url": final_url}
            out["reachable"].append(name)
        except Exception as e:
            out["targets"][name] = {"ok": False, "url": url, "error": str(e)[:120]}
    return out


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    doi = str(item.get("doi") or "").replace("https://doi.org/", "").strip()
    url = str(item.get("url") or "").strip()
    return {
        "title": title,
        "doi": doi,
        "url": url,
        "source": item.get("source") or "unknown",
        "year": item.get("year"),
        "journal": item.get("journal") or "",
    }


def trace_html_fulltext(url: str, doi: str = "") -> dict[str, Any]:
    candidates = []
    if url:
        candidates.append(url)
    if doi:
        candidates.append(f"https://doi.org/{doi.replace('https://doi.org/', '').strip()}")

    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        try:
            final_url, raw, ct = _fetch(c)
            if "pdf" in ct or final_url.lower().endswith(".pdf") or raw.startswith(b"%PDF-"):
                continue
            html = raw.decode("utf-8", errors="ignore")
            text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            links = []
            for lk in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.I):
                abs_u = urllib.parse.urljoin(final_url, lk)
                if abs_u.startswith("http"):
                    links.append(abs_u)

            return {
                "ok": len(text) >= 200,
                "final_url": final_url,
                "content_type": ct,
                "text_len": len(text),
                "text_preview": text[:500],
                "links_sample": links[:10],
            }
        except Exception as e:
            err = str(e)[:120]
            last = {"ok": False, "error": err, "final_url": c}
    return locals().get("last", {"ok": False, "error": "unresolved"})
