"""
KS33b #1: Pipeline Resilience — fallback chains + parallel execution.

Wraps external API calls with:
  - Timeout protection
  - Fallback chain (ConceptNet → OpenAlex → local cache)
  - Parallel execution where possible
  - Graceful degradation (never crash, always return partial result)
"""

import time
import concurrent.futures
from functools import wraps

# ─── Timeout + Fallback Decorator ───────────────────────────────────────────

def with_fallback(timeout_sec=10, fallback_value=None):
    """Decorator: timeout + fallback for any function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    return future.result(timeout=timeout_sec)
            except (concurrent.futures.TimeoutError, Exception) as e:
                return fallback_value if fallback_value is not None else {
                    "error": str(e)[:100],
                    "fallback": True,
                    "source": func.__name__,
                }
        return wrapper
    return decorator


# ─── Parallel Execution ─────────────────────────────────────────────────────

def run_parallel(tasks, timeout_sec=15):
    """Run multiple tasks in parallel with timeout.
    
    Args:
        tasks: list of (name, callable, args, kwargs)
        timeout_sec: max time for all tasks
    
    Returns:
        dict of {name: result}
    """
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
        futures = {}
        for name, func, args, kwargs in tasks:
            futures[executor.submit(func, *args, **kwargs)] = name
        
        done, not_done = concurrent.futures.wait(
            futures.keys(), timeout=timeout_sec
        )
        
        for future in done:
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = {"error": str(e)[:100], "fallback": True}
        
        for future in not_done:
            name = futures[future]
            results[name] = {"error": "timeout", "fallback": True}
            future.cancel()
    
    return results


# ─── Fallback Chain ─────────────────────────────────────────────────────────

class FallbackChain:
    """Execute a chain of functions, falling back on failure."""
    
    def __init__(self, *funcs, timeout_per_func=8):
        self.funcs = funcs
        self.timeout = timeout_per_func
    
    def execute(self, *args, **kwargs):
        """Try each function in order. Return first success."""
        errors = []
        
        for func in self.funcs:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(func, *args, **kwargs)
                    result = future.result(timeout=self.timeout)
                    if result and not (isinstance(result, dict) and result.get("error")):
                        return {
                            "result": result,
                            "source": func.__name__,
                            "fallback_used": func != self.funcs[0],
                            "attempts": len(errors) + 1,
                        }
            except Exception as e:
                errors.append({"func": func.__name__, "error": str(e)[:80]})
        
        return {
            "result": None,
            "source": "none",
            "fallback_used": True,
            "attempts": len(errors),
            "errors": errors,
        }


# ─── Local Cache (minimal, session-scoped) ──────────────────────────────────

class SessionCache:
    """Session-scoped cache for API results. Volatile — no persistence."""
    
    def __init__(self, max_entries=100, ttl_seconds=300):
        self._cache = {}
        self._max = max_entries
        self._ttl = ttl_seconds
    
    def get(self, key):
        entry = self._cache.get(key)
        if entry and (time.time() - entry["ts"]) < self._ttl:
            return entry["value"]
        return None
    
    def put(self, key, value):
        if len(self._cache) >= self._max:
            # Evict oldest
            oldest = min(self._cache, key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest]
        self._cache[key] = {"value": value, "ts": time.time()}
    
    def clear(self):
        self._cache.clear()
    
    def stats(self):
        return {"entries": len(self._cache), "max": self._max}
