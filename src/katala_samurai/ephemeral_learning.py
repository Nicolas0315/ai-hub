"""
KS33a — Ephemeral Learning: Session-scoped learning with explicit on/off control.

Three learning mechanisms (all session-scoped, all volatile):
  E1: Confidence Calibration — dynamic solver weight adjustment
  E2: Pattern Memory — domain/structural pattern detection
  E3: Verification Chain Learning — goal result feedback

Key design: explicit on/off toggle per mechanism + global switch.
Designed for future UI integration.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma
"""

import time
from collections import defaultdict


class EphemeralSession:
    """Session-scoped volatile learning state.
    
    All state is lost when this object is garbage collected or reset() is called.
    No persistence. No serialization. No accumulation.
    
    Toggle: on/off per mechanism (E1/E2/E3) and globally.
    """
    
    def __init__(self, enabled=True):
        self._global_enabled = enabled
        self._mechanism_enabled = {
            "E1_calibration": True,
            "E2_pattern": True,
            "E3_chain": True,
        }
        self._created_at = time.time()
        self._verification_count = 0
        
        # E1: Solver confidence calibration
        self._solver_results = defaultdict(list)  # solver_id → [pass/fail]
        self._solver_weight_adj = {}  # solver_id → adjustment factor
        
        # E2: Pattern memory
        self._domain_patterns = defaultdict(int)   # pattern → frequency
        self._structural_patterns = defaultdict(int)
        self._detected_biases = []
        
        # E3: Chain learning
        self._goal_history = []  # (goal_text, verdict, confidence)
        self._chain_insights = []  # derived insights from goal chains
    
    # ─── Toggle API ─────────────────────────────────────────────────────
    
    @property
    def enabled(self):
        return self._global_enabled
    
    def toggle(self, enabled=None):
        """Toggle global ephemeral learning on/off.
        
        Args:
            enabled: True/False, or None to flip current state.
        Returns:
            Current state after toggle.
        """
        if enabled is None:
            self._global_enabled = not self._global_enabled
        else:
            self._global_enabled = bool(enabled)
        return self._global_enabled
    
    def toggle_mechanism(self, mechanism, enabled=None):
        """Toggle a specific mechanism on/off.
        
        Args:
            mechanism: "E1_calibration", "E2_pattern", or "E3_chain"
            enabled: True/False, or None to flip.
        Returns:
            Current state after toggle.
        """
        if mechanism not in self._mechanism_enabled:
            raise ValueError(f"Unknown mechanism: {mechanism}. "
                           f"Valid: {list(self._mechanism_enabled.keys())}")
        if enabled is None:
            self._mechanism_enabled[mechanism] = not self._mechanism_enabled[mechanism]
        else:
            self._mechanism_enabled[mechanism] = bool(enabled)
        return self._mechanism_enabled[mechanism]
    
    def is_mechanism_active(self, mechanism):
        """Check if a specific mechanism is currently active."""
        return self._global_enabled and self._mechanism_enabled.get(mechanism, False)
    
    def get_status(self):
        """Get full status of ephemeral learning session."""
        return {
            "global_enabled": self._global_enabled,
            "mechanisms": dict(self._mechanism_enabled),
            "active_mechanisms": [
                k for k, v in self._mechanism_enabled.items()
                if v and self._global_enabled
            ],
            "session_age_seconds": round(time.time() - self._created_at, 1),
            "verification_count": self._verification_count,
            "e1_solvers_tracked": len(self._solver_results),
            "e1_adjustments": len(self._solver_weight_adj),
            "e2_domain_patterns": len(self._domain_patterns),
            "e2_structural_patterns": len(self._structural_patterns),
            "e2_biases_detected": len(self._detected_biases),
            "e3_goals_tracked": len(self._goal_history),
            "e3_chain_insights": len(self._chain_insights),
        }
    
    def reset(self):
        """Hard reset — destroy all session state. Equivalent to session end."""
        self._solver_results.clear()
        self._solver_weight_adj.clear()
        self._domain_patterns.clear()
        self._structural_patterns.clear()
        self._detected_biases.clear()
        self._goal_history.clear()
        self._chain_insights.clear()
        self._verification_count = 0
        self._created_at = time.time()
    
    # ─── E1: Confidence Calibration ─────────────────────────────────────
    
    def record_solver_result(self, solver_id, passed, confidence=None):
        """Record a solver's result for calibration."""
        if not self.is_mechanism_active("E1_calibration"):
            return
        
        self._solver_results[solver_id].append({
            "passed": passed,
            "confidence": confidence,
            "timestamp": time.time(),
        })
        
        # Recalculate weight adjustment
        results = self._solver_results[solver_id]
        if len(results) >= 3:
            recent = results[-5:]  # Last 5 results
            pass_rate = sum(1 for r in recent if r["passed"]) / len(recent)
            
            if pass_rate < 0.3:
                # Solver consistently fails → reduce weight
                self._solver_weight_adj[solver_id] = 0.6
            elif pass_rate > 0.9:
                # Solver consistently passes → might be too lenient
                self._solver_weight_adj[solver_id] = 0.85
            else:
                # Normal range
                self._solver_weight_adj[solver_id] = 1.0
    
    def get_solver_weight(self, solver_id):
        """Get current weight adjustment for a solver."""
        if not self.is_mechanism_active("E1_calibration"):
            return 1.0
        return self._solver_weight_adj.get(solver_id, 1.0)
    
    def get_calibration_report(self):
        """Get E1 calibration status."""
        report = {}
        for sid, results in self._solver_results.items():
            pass_rate = sum(1 for r in results if r["passed"]) / max(len(results), 1)
            report[sid] = {
                "total": len(results),
                "pass_rate": round(pass_rate, 3),
                "weight": self._solver_weight_adj.get(sid, 1.0),
            }
        return report
    
    # ─── E2: Pattern Memory ─────────────────────────────────────────────
    
    def record_domain_pattern(self, pattern_type, pattern_key):
        """Record a domain pattern observation."""
        if not self.is_mechanism_active("E2_pattern"):
            return
        self._domain_patterns[f"{pattern_type}:{pattern_key}"] += 1
    
    def record_structural_pattern(self, template_name, matched):
        """Record which structural templates match in this session."""
        if not self.is_mechanism_active("E2_pattern"):
            return
        key = f"template:{template_name}:{'hit' if matched else 'miss'}"
        self._structural_patterns[key] += 1
    
    def detect_session_bias(self):
        """Analyze session patterns for systematic biases.
        
        Returns list of detected biases with recommendations.
        """
        if not self.is_mechanism_active("E2_pattern"):
            return []
        
        biases = []
        
        # Check for domain concentration
        domain_counts = {}
        for key, count in self._domain_patterns.items():
            parts = key.split(":", 1)
            if len(parts) == 2:
                dtype = parts[0]
                if dtype not in domain_counts:
                    domain_counts[dtype] = 0
                domain_counts[dtype] += count
        
        total_patterns = sum(domain_counts.values())
        if total_patterns > 5:
            for dtype, count in domain_counts.items():
                ratio = count / total_patterns
                if ratio > 0.6:
                    bias = {
                        "type": "domain_concentration",
                        "domain": dtype,
                        "ratio": round(ratio, 2),
                        "recommendation": f"Session heavily focused on {dtype} — increase cross-domain verification",
                    }
                    biases.append(bias)
                    self._detected_biases.append(bias)
        
        # Check for template bias
        template_hits = {}
        template_misses = {}
        for key, count in self._structural_patterns.items():
            parts = key.split(":")
            if len(parts) >= 3:
                tname = parts[1]
                if "hit" in parts[2]:
                    template_hits[tname] = template_hits.get(tname, 0) + count
                else:
                    template_misses[tname] = template_misses.get(tname, 0) + count
        
        # High miss rate on a template = claims don't fit templates well
        for tname, misses in template_misses.items():
            hits = template_hits.get(tname, 0)
            if hits + misses > 3 and misses / (hits + misses) > 0.7:
                bias = {
                    "type": "template_mismatch",
                    "template": tname,
                    "miss_rate": round(misses / (hits + misses), 2),
                    "recommendation": f"Template '{tname}' rarely matches — may need expansion",
                }
                biases.append(bias)
                self._detected_biases.append(bias)
        
        return biases
    
    def get_priority_boost(self, goal_source):
        """Get priority boost based on session patterns.
        
        If session shows a pattern (e.g., many causal claims),
        boost goals that target that pattern.
        """
        if not self.is_mechanism_active("E2_pattern"):
            return 0.0
        
        # Check if pattern suggests boosting certain goal types
        causal_count = sum(v for k, v in self._domain_patterns.items() if "causal" in k.lower())
        total = sum(self._domain_patterns.values())
        
        if total > 3 and causal_count / max(total, 1) > 0.4:
            if "G1" in goal_source:
                return 0.05  # Boost gap detection for causal-heavy sessions
        
        return 0.0
    
    # ─── E3: Verification Chain Learning ─────────────────────────────────
    
    def record_goal_result(self, goal_text, verdict, confidence):
        """Record a goal verification result for chain learning."""
        if not self.is_mechanism_active("E3_chain"):
            return
        
        self._goal_history.append({
            "text": goal_text[:100],
            "verdict": verdict,
            "confidence": confidence,
            "timestamp": time.time(),
        })
        
        self._verification_count += 1
        
        # Derive chain insights
        self._update_chain_insights()
    
    def _update_chain_insights(self):
        """Derive insights from goal verification chains."""
        if len(self._goal_history) < 2:
            return
        
        recent = self._goal_history[-5:]
        
        # Insight: consecutive failures suggest systemic issue
        consecutive_fails = 0
        for g in reversed(recent):
            if g["verdict"] == "UNVERIFIED":
                consecutive_fails += 1
            else:
                break
        
        if consecutive_fails >= 3:
            insight = {
                "type": "systemic_failure",
                "detail": f"{consecutive_fails} consecutive unverified goals",
                "recommendation": "Original claim likely has fundamental issues",
                "confidence_penalty": -0.1 * consecutive_fails,
            }
            # Avoid duplicates
            if not any(i.get("type") == "systemic_failure" for i in self._chain_insights):
                self._chain_insights.append(insight)
        
        # Insight: high pass rate suggests claim is well-supported
        if len(recent) >= 3:
            pass_rate = sum(1 for g in recent if g["verdict"] in ("VERIFIED", "PARTIALLY_VERIFIED")) / len(recent)
            if pass_rate > 0.8:
                insight = {
                    "type": "strong_support",
                    "detail": f"Goal pass rate: {pass_rate:.0%}",
                    "recommendation": "Claim has strong auxiliary support",
                    "confidence_bonus": 0.05,
                }
                if not any(i.get("type") == "strong_support" for i in self._chain_insights):
                    self._chain_insights.append(insight)
    
    def get_chain_modifier(self):
        """Get confidence modifier from chain learning."""
        if not self.is_mechanism_active("E3_chain"):
            return 0.0
        
        modifier = 0.0
        for insight in self._chain_insights:
            modifier += insight.get("confidence_bonus", 0.0)
            modifier += insight.get("confidence_penalty", 0.0)
        
        return max(-0.3, min(0.15, modifier))  # Cap at [-0.3, +0.15]
    
    def get_chain_insights(self):
        """Get all derived chain insights."""
        return list(self._chain_insights)
