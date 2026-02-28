"""
KS37b — Katala Samurai 37b: 100x Speed Optimization

KS37a + 3 speed optimizations:
  1) Solver Pruning: Planner-driven — only run solvers relevant to claim type
  2) Response Cache: session-scoped cache for ConceptNet/OpenAlex/web results
  3) Local-Only Fast Path: for claims solvable without external APIs

Target: 12-40s → 120-400ms for cached/simple claims (100x)
Score: same as KS37a (no capability reduction)

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os, os, time
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks37a import KS37a, Claim
    from .stage_store import StageStore
    from .solver_cache import SolverCache
    from .metacognitive_planner import plan_verification, _LAYER_EFFECTIVENESS
except ImportError:
    from ks37a import KS37a, Claim
    from stage_store import StageStore
    from solver_cache import SolverCache
    from metacognitive_planner import plan_verification, _LAYER_EFFECTIVENESS

from typing import Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed


# Solver → layer mapping for pruning
_SOLVER_LAYERS = {
    "S01": "L1", "S02": "L1", "S03": "L1", "S04": "L1", "S05": "L1",
    "S06": "L1", "S07": "L1", "S08": "L1", "S09": "L1", "S10": "L1",
    "S11": "L1", "S12": "L1", "S13": "L1", "S14": "L1", "S15": "L1",
    "S16": "L1", "S17": "L1", "S18": "L1", "S19": "L1", "S20": "L1",
    "S21": "L1", "S22": "L2", "S23": "L2", "S24": "L2", "S25": "L2",
    "S26": "L3", "S27": "L3", "S28": "L3",
    "A01": "L3", "A02": "L3", "A03": "L3", "A04": "L3", "A05": "L3", "A06": "L3",
}

# Solvers that need external APIs (slow)
_EXTERNAL_SOLVERS = {
    "S07",  # OpenAlex
    "S22", "S23", "S24",  # Domain (may use web)
    "A04", "A05",  # ConceptNet
    "A06",  # Chain decomposition (OpenAlex)
}

# Solvers that are pure local (fast)
_LOCAL_SOLVERS = set(_SOLVER_LAYERS.keys()) - _EXTERNAL_SOLVERS


class KS37b(KS37a):
    """KS37a + 100x Speed Optimization."""
    
    VERSION = "KS37b"
    
    def __init__(self, cache_size: int = 1000, **kwargs):
        super().__init__(**kwargs)
        self.cache = SolverCache(max_size=cache_size)
        self._speed_stats = {"fast_path": 0, "pruned": 0, "full": 0}
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        t0 = time.time()
        claim_text = claim.text if hasattr(claim, 'text') else str(claim)
        
        # ═══ PHASE 0: PLAN (reuse from parent) ═══
        plan = plan_verification(claim_text)
        claim_type = plan["primary_type"]
        difficulty = plan["difficulty"]["label"]
        
        # ═══ CACHE CHECK: exact claim hit? ═══
        cached = self.cache.get("verify", claim_text)
        if cached is not None:
            cached["_cached"] = True
            cached["pipeline"]["total_ms"] = int((time.time() - t0) * 1000)
            self._speed_stats["fast_path"] += 1
            return cached
        
        # ═══ SOLVER PRUNING: which solvers to actually run? ═══
        skip_solvers = self._compute_skip_set(plan)
        
        # ═══ FAST PATH: can we solve locally only? ═══
        effectiveness = _LAYER_EFFECTIVENESS.get(claim_type, {})
        needs_external = (
            effectiveness.get("L3_analogy", 0) > 0.5 or
            effectiveness.get("L2_domain", 0) > 0.7 or
            difficulty == "HIGH"
        )
        
        if not needs_external and difficulty == "LOW":
            # Local-only fast path: skip all external solvers
            skip_solvers.update(_EXTERNAL_SOLVERS)
            self._speed_stats["fast_path"] += 1
        elif skip_solvers:
            self._speed_stats["pruned"] += 1
        else:
            self._speed_stats["full"] += 1
        
        # ═══ INJECT SKIP SET INTO ENV ═══
        # KS37a inherits KS35c → KS34a → ... → KS30c which runs solvers
        # We set an env var that solver runners can check
        old_skip = os.environ.get("KS_SKIP_SOLVERS", "")
        os.environ["KS_SKIP_SOLVERS"] = ",".join(skip_solvers)
        
        try:
            result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        finally:
            if old_skip:
                os.environ["KS_SKIP_SOLVERS"] = old_skip
            else:
                os.environ.pop("KS_SKIP_SOLVERS", None)
        
        t_end = time.time()
        
        if isinstance(result, dict):
            result["version"] = self.VERSION
            result["optimization"] = {
                "solvers_skipped": len(skip_solvers),
                "skip_set": sorted(skip_solvers)[:10],
                "fast_path": not needs_external and difficulty == "LOW",
                "cache_stats": self.cache.stats(),
            }
            
            # Update pipeline timing
            if "pipeline" in result:
                result["pipeline"]["total_ms"] = int((t_end - t0) * 1000)
            
            # Cache the result
            self.cache.put("verify", claim_text, result)
        
        return result
    
    def _compute_skip_set(self, plan: Dict) -> Set[str]:
        """Determine which solvers to skip based on planner output."""
        skip = set()
        claim_type = plan["primary_type"]
        effectiveness = _LAYER_EFFECTIVENESS.get(claim_type, {})
        
        # Skip solvers in low-effectiveness layers
        for solver, layer in _SOLVER_LAYERS.items():
            # Map layer names
            layer_key = {
                "L1": "L1_formal", "L2": "L2_domain", "L3": "L3_analogy",
            }.get(layer, layer)
            
            eff = effectiveness.get(layer_key, 0.5)
            if eff < 0.3:
                skip.add(solver)
        
        # Never skip core formal solvers S01-S05 (always useful)
        skip -= {"S01", "S02", "S03", "S04", "S05"}
        
        return skip
    
    def verify_batch(self, claims: list, store=None, max_workers: int = 4, **kwargs) -> list:
        """Batch verify multiple claims in parallel."""
        results = [None] * len(claims)
        
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for i, claim in enumerate(claims):
                s = store or StageStore()
                futures[pool.submit(self.verify, claim, store=s, **kwargs)] = i
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {"error": str(e)[:200], "version": self.VERSION}
        
        return results
    
    def speed_report(self) -> Dict[str, Any]:
        return {
            "stats": self._speed_stats,
            "cache": self.cache.stats(),
            "total_verifications": sum(self._speed_stats.values()),
        }
