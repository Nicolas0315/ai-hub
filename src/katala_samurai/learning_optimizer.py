"""
Learning Optimizer — addresses weakness ③: Autonomous Learning 72%.

Optimizes ephemeral learning speed and efficiency:
  O1: Fast Calibration — fewer samples needed for E1 weight adjustment
  O2: Adaptive Patterns — E2 detects patterns faster with momentum
  O3: Chain Acceleration — E3 derives insights from 2 results instead of 3

Non-LLM: statistical optimization on EphemeralSession.
"""

import math


class LearningOptimizer:
    """Wraps EphemeralSession with optimization strategies."""
    
    def __init__(self, session):
        self.session = session
        self._momentum = {}  # pattern → momentum value
        self._fast_cal_threshold = 2  # Reduced from 3 to 2
    
    # ─── O1: Fast Calibration ───────────────────────────────────────────
    
    def fast_calibrate(self, solver_id, passed, confidence=None):
        """Faster E1 calibration with Bayesian-inspired updates.
        
        Instead of waiting for 3 results, uses weighted running average
        with prior (0.5 pass rate assumed).
        """
        self.session.record_solver_result(solver_id, passed, confidence)
        
        # Override weight calculation with faster convergence
        results = self.session._solver_results.get(solver_id, [])
        if len(results) >= self._fast_cal_threshold:
            # Bayesian update: prior=0.5, weight evidence more as count grows
            n = len(results)
            pass_count = sum(1 for r in results if r["passed"])
            # Prior strength decreases as evidence accumulates
            prior_weight = 2.0 / (n + 2)
            evidence_weight = 1.0 - prior_weight
            posterior_pass_rate = prior_weight * 0.5 + evidence_weight * (pass_count / n)
            
            # Map pass rate to weight
            if posterior_pass_rate < 0.3:
                weight = 0.5 + posterior_pass_rate  # 0.5-0.8
            elif posterior_pass_rate > 0.8:
                weight = 0.95 - (posterior_pass_rate - 0.8) * 0.5  # Slight reduction for overconfidence
            else:
                weight = 1.0
            
            self.session._solver_weight_adj[solver_id] = round(weight, 3)
    
    # ─── O2: Adaptive Patterns with Momentum ───────────────────────────
    
    def record_pattern_with_momentum(self, pattern_type, pattern_key):
        """E2 pattern recording with exponential momentum.
        
        Patterns that appear repeatedly gain momentum,
        making bias detection faster.
        """
        self.session.record_domain_pattern(pattern_type, pattern_key)
        
        key = f"{pattern_type}:{pattern_key}"
        current = self._momentum.get(key, 0.0)
        # Momentum: each occurrence adds 1.0 * decay factor
        self._momentum[key] = current * 0.8 + 1.0
        
        # If momentum exceeds threshold, trigger early bias detection
        if self._momentum[key] > 2.5:
            return {
                "early_bias_detected": True,
                "pattern": key,
                "momentum": round(self._momentum[key], 2),
            }
        return {"early_bias_detected": False}
    
    # ─── O3: Chain Acceleration ─────────────────────────────────────────
    
    def accelerated_chain_record(self, goal_text, verdict, confidence):
        """E3 chain learning with faster insight derivation.
        
        Derives insights from 2 results instead of 3.
        Uses confidence trend for early detection.
        """
        self.session.record_goal_result(goal_text, verdict, confidence)
        
        history = self.session._goal_history
        if len(history) < 2:
            return {"insight": None}
        
        recent = history[-3:] if len(history) >= 3 else history[-2:]
        
        # Confidence trend analysis
        confidences = [g["confidence"] for g in recent]
        if len(confidences) >= 2:
            trend = confidences[-1] - confidences[0]
            
            if trend < -0.3:
                insight = {
                    "type": "confidence_collapse",
                    "detail": f"Confidence dropped {abs(trend):.0%} in {len(recent)} verifications",
                    "recommendation": "Fundamental issue likely — consider rejecting claim",
                    "confidence_penalty": -0.15,
                }
                if not any(i.get("type") == "confidence_collapse" for i in self.session._chain_insights):
                    self.session._chain_insights.append(insight)
                return {"insight": insight}
            
            elif trend > 0.2:
                insight = {
                    "type": "confidence_growth",
                    "detail": f"Confidence grew {trend:.0%} in {len(recent)} verifications",
                    "recommendation": "Claim gaining support from multiple angles",
                    "confidence_bonus": 0.08,
                }
                if not any(i.get("type") == "confidence_growth" for i in self.session._chain_insights):
                    self.session._chain_insights.append(insight)
                return {"insight": insight}
        
        # Fast consecutive failure detection (2 instead of 3)
        consecutive_fails = 0
        for g in reversed(recent):
            if g["verdict"] == "UNVERIFIED":
                consecutive_fails += 1
            else:
                break
        
        if consecutive_fails >= 2:
            insight = {
                "type": "early_failure",
                "detail": f"{consecutive_fails} consecutive failures (accelerated detection)",
                "recommendation": "Claim likely problematic",
                "confidence_penalty": -0.1 * consecutive_fails,
            }
            if not any(i.get("type") == "early_failure" for i in self.session._chain_insights):
                self.session._chain_insights.append(insight)
            return {"insight": insight}
        
        return {"insight": None}
    
    def get_optimization_stats(self):
        """Get optimization effectiveness stats."""
        return {
            "fast_cal_threshold": self._fast_cal_threshold,
            "momentum_patterns": len(self._momentum),
            "high_momentum": {k: round(v, 2) for k, v in self._momentum.items() if v > 2.0},
            "chain_insights_accelerated": len([
                i for i in self.session._chain_insights 
                if i.get("type") in ("early_failure", "confidence_collapse", "confidence_growth")
            ]),
        }
