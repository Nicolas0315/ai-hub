"""
Session State Manager — Safe Ephemeral Memory for KS Agent Mode.

Anti-Tay compliant: all state auto-expires after TTL.
Toxicity Guard integration: contaminated entries are purged.

Design: Youta Hilono (requirements) + Shirokuma (implementation)
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── Constants ──
DEFAULT_TTL_SECONDS = 1800       # 30 minutes default
MAX_TTL_SECONDS = 7200           # 2 hours hard cap (Anti-Tay)
MAX_ENTRIES = 500                # Memory limit
TOXICITY_PURGE_THRESHOLD = 0.7   # Purge if toxicity score > 0.7
CONFIDENCE_FLOOR = 0.3           # Don't store low-confidence results


@dataclass
class StateEntry:
    """Single memory entry with automatic expiry."""
    key: str
    value: Any
    confidence: float
    source: str             # SELF / DESIGNER / EXTERNAL / AMBIGUOUS
    created_at: float = field(default_factory=time.time)
    ttl: float = DEFAULT_TTL_SECONDS
    access_count: int = 0
    toxicity_score: float = 0.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl

    @property
    def is_toxic(self) -> bool:
        return self.toxicity_score > TOXICITY_PURGE_THRESHOLD

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_toxic


class SessionStateManager:
    """
    Ephemeral state store for KS agent mode.

    Guarantees:
    - All entries expire after TTL (default 30min, max 2hr)
    - Toxic entries are auto-purged on access
    - Low-confidence results are rejected
    - Total entries capped at MAX_ENTRIES (FIFO eviction)
    - Thread-safe
    """

    def __init__(self, default_ttl: float = DEFAULT_TTL_SECONDS):
        self._store: Dict[str, StateEntry] = {}
        self._lock = threading.Lock()
        self._default_ttl = min(default_ttl, MAX_TTL_SECONDS)
        self._history: List[Dict[str, Any]] = []

    def store(self, key: str, value: Any, confidence: float,
              source: str = "SELF", ttl: Optional[float] = None,
              toxicity_score: float = 0.0) -> bool:
        """Store a value. Returns False if rejected."""
        if confidence < CONFIDENCE_FLOOR:
            return False
        if toxicity_score > TOXICITY_PURGE_THRESHOLD:
            return False

        effective_ttl = min(ttl or self._default_ttl, MAX_TTL_SECONDS)

        with self._lock:
            if len(self._store) >= MAX_ENTRIES and key not in self._store:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                self._evict(oldest_key, reason="capacity")

            entry = StateEntry(
                key=key, value=value, confidence=confidence,
                source=source, ttl=effective_ttl,
                toxicity_score=toxicity_score
            )
            self._store[key] = entry
            self._log("store", key, confidence=confidence, source=source)
            return True

    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a value. Returns None if expired/toxic/missing."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if not entry.is_valid:
                self._evict(key, reason="expired" if entry.is_expired else "toxic")
                return None
            entry.access_count += 1
            return entry.value

    def retrieve_with_meta(self, key: str) -> Optional[StateEntry]:
        """Retrieve entry with full metadata."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None or not entry.is_valid:
                if entry and not entry.is_valid:
                    self._evict(key, reason="invalid")
                return None
            entry.access_count += 1
            return entry

    def purge_expired(self) -> int:
        """Remove all expired/toxic entries."""
        with self._lock:
            to_remove = [k for k, v in self._store.items() if not v.is_valid]
            for k in to_remove:
                self._evict(k, reason="sweep")
            return len(to_remove)

    def purge_all(self) -> int:
        """Nuclear option: clear everything."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._log("purge_all", "*", reason="emergency")
            return count

    def mark_toxic(self, key: str, score: float = 1.0) -> bool:
        """Mark an entry as toxic."""
        with self._lock:
            entry = self._store.get(key)
            if entry:
                entry.toxicity_score = score
                self._log("mark_toxic", key, toxicity=score)
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            valid = sum(1 for v in self._store.values() if v.is_valid)
            expired = sum(1 for v in self._store.values() if v.is_expired)
            toxic = sum(1 for v in self._store.values() if v.is_toxic)
            return {
                "total": len(self._store), "valid": valid,
                "expired": expired, "toxic": toxic,
                "history_len": len(self._history),
            }

    @property
    def audit_trail(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def _evict(self, key: str, reason: str) -> None:
        if key in self._store:
            del self._store[key]
            self._log("evict", key, reason=reason)

    def _log(self, action: str, key: str, **kwargs) -> None:
        self._history.append({
            "action": action, "key": key,
            "time": time.time(), **kwargs
        })
