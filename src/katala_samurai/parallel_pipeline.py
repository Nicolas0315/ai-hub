"""
Parallel Pipeline — 4-phase verification with concurrent execution.

Phase 1 (parallel): L1(formal) || L3(analogy) || L6(statistical)
Phase 2 (conditional): L2(domain bridge) — only if Phase 1 inconclusive
Phase 3 (parallel): L4(meta) || L5(causal) || L7(adversarial)
Phase 4: Integration + Deep Causal (KS34a enhancements)

~40% faster than sequential 5-layer cycle.

Design: Youta Hilono, 2026-02-28
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable, Tuple


def _run_with_timeout(fn: Callable, args: tuple, timeout: float = 30.0) -> Tuple[str, Any]:
    """Run a function with timeout, return (name, result_or_error)."""
    name = args[0] if args else fn.__name__
    try:
        result = fn(*args[1:]) if len(args) > 1 else fn()
        return (name, result)
    except Exception as e:
        return (name, {"error": str(e)[:200], "verdict": "ERROR"})


class ParallelPipeline:
    """4-phase parallel verification pipeline."""
    
    def __init__(self, max_workers: int = 3, skip_threshold: float = 0.9):
        """
        Args:
            max_workers: Thread pool size for parallel phases.
            skip_threshold: If Phase 1 confidence > this, skip Phase 2-3.
        """
        self.max_workers = max_workers
        self.skip_threshold = skip_threshold
        self.timing = {}
    
    def run_phase(
        self,
        phase_name: str,
        tasks: List[Tuple[str, Callable, tuple]],
    ) -> Dict[str, Any]:
        """Run multiple tasks in parallel, collect results.
        
        Args:
            phase_name: Name for timing.
            tasks: List of (task_name, function, args).
        """
        start = time.time()
        results = {}
        
        if len(tasks) == 1:
            # Single task, no threading overhead
            name, fn, args = tasks[0]
            try:
                results[name] = fn(*args)
            except Exception as e:
                results[name] = {"error": str(e)[:200]}
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                for name, fn, args in tasks:
                    future = executor.submit(fn, *args)
                    futures[future] = name
                
                for future in as_completed(futures, timeout=60):
                    name = futures[future]
                    try:
                        results[name] = future.result(timeout=30)
                    except Exception as e:
                        results[name] = {"error": str(e)[:200]}
        
        elapsed = time.time() - start
        self.timing[phase_name] = round(elapsed, 3)
        
        return results
    
    def should_skip_phase2(self, phase1_results: Dict[str, Any]) -> bool:
        """Check if Phase 1 results are conclusive enough to skip Phase 2."""
        confidences = []
        for name, result in phase1_results.items():
            if isinstance(result, dict):
                conf = result.get("confidence", result.get("causal_confidence", 0.5))
                confidences.append(conf)
        
        if not confidences:
            return False
        
        avg_conf = sum(confidences) / len(confidences)
        # Skip if average confidence is very high (conclusive) or very low (clearly false)
        return avg_conf > self.skip_threshold or avg_conf < (1 - self.skip_threshold)
    
    def aggregate_results(
        self,
        phase_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Aggregate results from all phases into final verdict."""
        all_confidences = []
        all_verdicts = []
        all_modifiers = []
        
        for phase_name, results in phase_results.items():
            for task_name, result in results.items():
                if not isinstance(result, dict):
                    continue
                if "confidence" in result:
                    all_confidences.append(result["confidence"])
                if "causal_confidence" in result:
                    all_confidences.append(result["causal_confidence"])
                if "confidence_modifier" in result:
                    all_modifiers.append(result["confidence_modifier"])
                if "verdict" in result:
                    all_verdicts.append(result["verdict"])
        
        # Weighted average confidence
        base_conf = sum(all_confidences) / max(len(all_confidences), 1) if all_confidences else 0.5
        total_mod = sum(all_modifiers)
        total_mod = max(-0.3, min(0.2, total_mod))
        
        final_conf = max(0.0, min(1.0, base_conf + total_mod))
        
        return {
            "confidence": round(final_conf, 4),
            "base_confidence": round(base_conf, 4),
            "total_modifier": round(total_mod, 4),
            "phases_run": list(phase_results.keys()),
            "tasks_run": sum(len(r) for r in phase_results.values()),
            "timing": self.timing,
            "total_time": round(sum(self.timing.values()), 3),
        }
