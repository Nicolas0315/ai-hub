"""
ArtSearch Layer — Fallback media search across YouTube, Spotify, SoundCloud, Pixiv.

DESIGN PRINCIPLES (Youta Hilono):
  - FALLBACK ONLY: Never runs as primary verification path
  - MINIMAL CONTAMINATION: Results are isolated, read-only, never fed back into L1-L7
  - SANDBOXED: Own StageStore namespace, separate from core verification
  - NON-LLM: All searches via public APIs/scraping, no LLM dependency

Supported platforms:
  - YouTube (via yt-dlp search)
  - Spotify (via web search fallback)
  - SoundCloud (via web search fallback)
  - Pixiv (via web search fallback)

Design: Youta Hilono, 2026-02-28
"""

import os
import re
import json
import subprocess
from typing import Dict, Any, List, Optional


_FAST_MODE = os.environ.get("KS_FAST_MODE", "0") == "1"


def search_youtube(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search YouTube via yt-dlp (no API key needed)."""
    if _FAST_MODE:
        return [{"title": f"[FAST_MODE] YouTube: {query}", "url": "", "platform": "youtube"}]
    
    try:
        cmd = [
            "yt-dlp", "--flat-playlist", "--dump-json",
            f"ytsearch{max_results}:{query}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append({
                    "title": data.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                    "duration": data.get("duration"),
                    "uploader": data.get("uploader", ""),
                    "view_count": data.get("view_count"),
                    "platform": "youtube",
                })
            except json.JSONDecodeError:
                pass
        return entries
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        return [{"error": str(e)[:100], "platform": "youtube"}]


def search_spotify(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search Spotify via web scraping fallback."""
    if _FAST_MODE:
        return [{"title": f"[FAST_MODE] Spotify: {query}", "url": "", "platform": "spotify"}]
    
    try:
        import urllib.request
        import urllib.parse
        encoded = urllib.parse.quote(query)
        url = f"https://open.spotify.com/search/{encoded}"
        # Can't scrape Spotify directly without auth — use web search as proxy
        search_url = f"https://api.duckduckgo.com/?q=site:open.spotify.com+{encoded}&format=json"
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        
        results = []
        for item in data.get("RelatedTopics", [])[:max_results]:
            text = item.get("Text", "")
            first_url = item.get("FirstURL", "")
            if "spotify" in first_url.lower():
                results.append({
                    "title": text[:100],
                    "url": first_url,
                    "platform": "spotify",
                })
        
        if not results:
            results.append({
                "title": query,
                "url": f"https://open.spotify.com/search/{encoded}",
                "platform": "spotify",
                "note": "direct_search_link",
            })
        return results
    except Exception as e:
        return [{"title": query, "url": f"https://open.spotify.com/search/{urllib.parse.quote(query) if 'urllib' in dir() else query}", "platform": "spotify", "fallback": True}]


def search_soundcloud(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search SoundCloud via yt-dlp or web fallback."""
    if _FAST_MODE:
        return [{"title": f"[FAST_MODE] SoundCloud: {query}", "url": "", "platform": "soundcloud"}]
    
    try:
        cmd = [
            "yt-dlp", "--flat-playlist", "--dump-json",
            f"scsearch{max_results}:{query}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append({
                    "title": data.get("title", ""),
                    "url": data.get("url", data.get("webpage_url", "")),
                    "uploader": data.get("uploader", ""),
                    "platform": "soundcloud",
                })
            except json.JSONDecodeError:
                pass
        return entries if entries else [{"title": query, "url": f"https://soundcloud.com/search?q={query}", "platform": "soundcloud", "fallback": True}]
    except Exception:
        import urllib.parse
        return [{"title": query, "url": f"https://soundcloud.com/search?q={urllib.parse.quote(query)}", "platform": "soundcloud", "fallback": True}]


def search_pixiv(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search Pixiv via web search fallback."""
    if _FAST_MODE:
        return [{"title": f"[FAST_MODE] Pixiv: {query}", "url": "", "platform": "pixiv"}]
    
    try:
        import urllib.request
        import urllib.parse
        encoded = urllib.parse.quote(query)
        # Pixiv search URL (no auth needed for search page)
        return [{
            "title": query,
            "url": f"https://www.pixiv.net/en/tags/{encoded}/artworks",
            "platform": "pixiv",
            "search_url": True,
        }]
    except Exception:
        return [{"title": query, "platform": "pixiv", "error": "search_failed"}]


def art_search(
    query: str,
    platforms: Optional[List[str]] = None,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Unified art/media search across multiple platforms.
    
    Args:
        query: Search query.
        platforms: List of platforms to search. Default: all.
        max_results: Max results per platform.
    
    Returns:
        Dict with results grouped by platform.
    """
    if platforms is None:
        platforms = ["youtube", "spotify", "soundcloud", "pixiv"]
    
    searchers = {
        "youtube": search_youtube,
        "spotify": search_spotify,
        "soundcloud": search_soundcloud,
        "pixiv": search_pixiv,
    }
    
    results = {}
    total = 0
    
    for platform in platforms:
        if platform in searchers:
            try:
                r = searchers[platform](query, max_results)
                results[platform] = r
                total += len(r)
            except Exception as e:
                results[platform] = [{"error": str(e)[:100]}]
    
    return {
        "query": query,
        "platforms_searched": platforms,
        "total_results": total,
        "results": results,
    }
