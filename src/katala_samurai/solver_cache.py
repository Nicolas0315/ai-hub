"""
Solver Cache — Session-scoped response cache for external API calls.

Eliminates redundant ConceptNet/OpenAlex/web queries within a session.
TTL-based expiry. Anti-accumulation compliant (session-scoped, no persistence).

Design: Youta Hilono, 2026-02-28
"""

import time
import hashlib
from typing import Any, Optional, Dict


class SolverCache:
    """In-memory cache for solver results and external API responses."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: Dict[str, Dict] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
    
    @staticmethod
    def _key(namespace: str, query: str) -> str:
        h = hashlib.md5(f"{namespace}:{query}".encode()).hexdigest()[:16]
        return f"{namespace}:{h}"
    
    def get(self, namespace: str, query: str) -> Optional[Any]:
        key = self._key(namespace, query)
        entry = self._cache.get(key)
        if entry and (time.time() - entry["ts"]) < self._ttl:
            self._hits += 1
            return entry["value"]
        if entry:
            del self._cache[key]
        self._misses += 1
        return None
    
    def put(self, namespace: str, query: str, value: Any):
        if len(self._cache) >= self._max_size:
            # Evict oldest
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest_key]
        key = self._key(namespace, query)
        self._cache[key] = {"value": value, "ts": time.time()}
    
    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 3),
        }
    
    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0
