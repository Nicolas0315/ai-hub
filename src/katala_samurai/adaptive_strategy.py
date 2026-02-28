"""
Adaptive Strategy Engine — Dynamic strategy switching mid-verification.

IQ160 PhD advantage: they change approach MID-REASONING when something feels off.
This module gives KS that ability:
  - Strategy repertoire (7 strategies for different situations)
  - Trigger-based switching (not just sequential execution)
  - Backtracking when a strategy fails
  - Multi-strategy fusion for ambiguous claims

Target: Self-Regulation 90% → 95%, Metacognitive Planning 90% → 95%

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional, Tuple
from collections import deque


# ── Strategy Repertoire ──

STRATEGIES = {
    "depth_first": {
        "description": "Go deep on the most promising layer before broadening",
        "best_for": ["causal", "logical"],
        "layer_weights": {"L5_causal": 1.5, "L1_formal": 1.3, "L7_adv": 1.0},
        "early_stop": True,
    },
    "breadth_first": {
        "description": "Run all layers equally, synthesize at the end",
        "best_for": ["unknown", "empirical"],
        "layer_weights": {},  # all equal
        "early_stop": False,
    },
    "adversarial_first": {
        "description": "Try to DISPROVE first, then verify what survives",
        "best_for": ["normative", "historical"],
        "layer_weights": {"L7_adv": 2.0, "L6_stat": 1.3},
        "early_stop": False,
    },
    "statistical_focus": {
        "description": "Heavy statistical scrutiny for quantitative claims",
        "best_for": ["statistical"],
        "layer_weights": {"L6_stat": 2.0, "L7_adv": 1.5, "L4_meta": 1.0},
        "early_stop": True,
    },
    "consensus_seeking": {
        "description": "Maximize agreement across independent layers",
        "best_for": ["empirical", "historical"],
        "layer_weights": {"L2_domain": 1.3, "L4_meta": 1.3, "L3_analogy": 1.2},
        "early_stop": False,
    },
    "devil_advocate": {
        "description": "Deliberately argue against the claim to stress-test",
        "best_for": ["normative", "causal"],
        "layer_weights": {"L7_adv": 2.5, "L5_causal": 1.0},
        "early_stop": False,
    },
    "minimal": {
        "description": "Quick check for trivially true/false claims",
        "best_for": ["definitional"],
        "layer_weights": {"L1_formal": 2.0, "L2_domain": 1.5},
        "early_stop": True,
    },
}


class AdaptiveStrategy:
    """Select, execute, and switch strategies dynamically."""
    
    def __init__(self):
        self._strategy_history = deque(maxlen=50)
        self._switch_log = []
        self._backtrack_count = 0
    
    def select_initial(self, claim_type: str, difficulty: str) -> Tuple[str, Dict]:
        """Select initial strategy based on claim type and difficulty."""
        # Find best match
        scores = {}
        for name, strat in STRATEGIES.items():
            score = 0
            if claim_type in strat["best_for"]:
                score += 3
            if difficulty == "HIGH" and not strat["early_stop"]:
                score += 1  # Hard claims need thorough strategies
            if difficulty == "LOW" and strat["early_stop"]:
                score += 2  # Easy claims can use fast strategies
            scores[name] = score
        
        best = max(scores, key=scores.get)
        return best, STRATEGIES[best]
    
    def evaluate_switch(self, current_strategy: str, mid_results: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """Check if we should switch strategy mid-verification.
        
        Returns: (new_strategy, reason) or None
        """
        conf = mid_results.get("confidence", 0.5)
        
        # ── Trigger 1: Dead zone → switch to adversarial_first ──
        if 0.4 <= conf <= 0.6 and current_strategy != "adversarial_first" and current_strategy != "devil_advocate":
            return ("devil_advocate", f"Dead zone (conf={conf:.2f}) — switching to devil's advocate to force resolution")
        
        # ── Trigger 2: Statistical issues found → focus statistical ──
        l6 = mid_results.get("L6_statistical", {})
        if l6.get("modifier", 0) < -0.1 and current_strategy != "statistical_focus":
            return ("statistical_focus", f"L6 found issues (mod={l6['modifier']:.2f}) — switching to statistical focus")
        
        # ── Trigger 3: Too fast confidence → adversarial stress test ──
        if conf > 0.85 and current_strategy not in ("adversarial_first", "devil_advocate"):
            return ("adversarial_first", f"Suspiciously high confidence ({conf:.2f}) early — stress testing")
        
        # ── Trigger 4: All layers agree → consensus might be wrong ──
        reg = mid_results.get("self_regulation", {})
        if reg.get("health") == "HEALTHY" and conf > 0.8:
            insight = mid_results.get("emergent_insights", {})
            if insight.get("count", 0) == 0:
                return ("devil_advocate", "Perfect consensus with no insights — switching to challenge assumptions")
        
        return None
    
    def should_backtrack(self, current_strategy: str, result: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """After getting a result, should we backtrack and try a different strategy?"""
        conf = result.get("confidence", 0.5)
        corrections = result.get("self_correction", {})
        
        # Backtrack if too many corrections were needed
        if corrections.get("applied", 0) >= 3:
            # Try breadth_first as safe fallback
            if current_strategy != "breadth_first":
                self._backtrack_count += 1
                return ("breadth_first", f"Too many corrections ({corrections['applied']}) — backtracking to breadth-first")
        
        # Backtrack if fragility detected
        if "fragile_verdict" in corrections.get("types", []):
            if current_strategy in ("minimal", "depth_first"):
                self._backtrack_count += 1
                return ("consensus_seeking", "Fragile verdict with narrow strategy — backtracking to consensus")
        
        return None
    
    def record(self, strategy: str, claim_type: str, result_confidence: float, corrections: int):
        """Record strategy outcome for future learning."""
        self._strategy_history.append({
            "strategy": strategy,
            "claim_type": claim_type,
            "confidence": result_confidence,
            "corrections": corrections,
        })
    
    def strategy_report(self) -> Dict[str, Any]:
        """Which strategies work best for which claim types?"""
        if not self._strategy_history:
            return {"total": 0}
        
        perf = {}
        for entry in self._strategy_history:
            key = f"{entry['strategy']}:{entry['claim_type']}"
            if key not in perf:
                perf[key] = {"runs": 0, "avg_corrections": 0, "confidences": []}
            perf[key]["runs"] += 1
            perf[key]["confidences"].append(entry["confidence"])
            perf[key]["avg_corrections"] += entry["corrections"]
        
        for k in perf:
            perf[k]["avg_corrections"] = round(perf[k]["avg_corrections"] / perf[k]["runs"], 2)
            confs = perf[k]["confidences"]
            perf[k]["avg_confidence"] = round(sum(confs)/len(confs), 3)
            del perf[k]["confidences"]
        
        return {
            "total_runs": len(self._strategy_history),
            "backtracks": self._backtrack_count,
            "performance": perf,
        }
