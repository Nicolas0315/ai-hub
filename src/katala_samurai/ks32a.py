"""
KS32a — Katala Samurai 32a: Autonomous Goal-Setting Verification

KS31e + Autonomous Verification Goal Generator (G1+G2+G3)

Architecture:
  Phase 1: KS31e verify() on original claim
  Phase 2: G1 Gap + G2 Contradiction + G3 Scope → Goal Queue
  Phase 3: Auto-verify top-N goals with KS31e
  Phase 4: Integrate original + goal verification results

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks31e import KS31e, Claim
    from .goal_generator import generate_goals
    from .stage_store import StageStore
except ImportError:
    from ks31e import KS31e, Claim
    from goal_generator import generate_goals
    from stage_store import StageStore


class KS32a(KS31e):
    """KS31e + Autonomous Goal Setting.
    
    After verifying the original claim, autonomously generates
    additional verification goals and runs them through KS31e.
    """
    
    VERSION = "KS32a"
    
    def __init__(self, auto_goal_limit=5, **kwargs):
        super().__init__(**kwargs)
        self.auto_goal_limit = auto_goal_limit
    
    def verify(self, claim, store=None, skip_s28=True):
        """Full verification with autonomous goal generation.
        
        Phase 1: Verify original claim (KS31e)
        Phase 2: Generate goals from verification results
        Phase 3: Verify top goals (lightweight — skip L4/L5 for speed)
        Phase 4: Integrate results
        """
        if store is None:
            store = StageStore()
        
        # Phase 1: Original claim verification
        if isinstance(claim, str):
            claim = Claim(text=claim, evidence=[])
        
        original_result = super().verify(claim, store=store, skip_s28=skip_s28)
        
        # Phase 2: Generate autonomous goals
        goals = generate_goals(
            claim.text,
            verification_result=original_result,
            store=store,
            max_goals=self.auto_goal_limit,
        )
        
        # Phase 3: Verify top goals (lightweight — L1 only for speed)
        goal_results = []
        for goal_info in goals.get("goals", [])[:self.auto_goal_limit]:
            goal_claim = Claim(
                text=goal_info["target"],
                evidence=list(claim.evidence) if claim.evidence else [],
            )
            try:
                # Lightweight verification: skip expensive layers
                goal_result = self._lightweight_verify(goal_claim, store=store)
                goal_results.append({
                    "goal": goal_info["target"][:80],
                    "source": goal_info["source"],
                    "priority": goal_info["priority"],
                    "verdict": goal_result.get("verdict", "UNKNOWN"),
                    "confidence": goal_result.get("confidence", 0.0),
                })
            except Exception as e:
                goal_results.append({
                    "goal": goal_info["target"][:80],
                    "source": goal_info["source"],
                    "priority": goal_info["priority"],
                    "verdict": "ERROR",
                    "confidence": 0.0,
                    "error": str(e)[:50],
                })
        
        # Phase 4: Integrate
        # Adjust original confidence based on goal verification
        goal_support = sum(1 for g in goal_results if g["verdict"] in ("VERIFIED", "PARTIALLY_VERIFIED"))
        goal_challenge = sum(1 for g in goal_results if g["verdict"] == "UNVERIFIED")
        goal_total = len(goal_results)
        
        if goal_total > 0:
            support_ratio = goal_support / goal_total
            challenge_ratio = goal_challenge / goal_total
            
            # Boost or penalize original confidence
            original_confidence = original_result.get("confidence", 0.5)
            goal_modifier = 0.1 * support_ratio - 0.15 * challenge_ratio
            adjusted_confidence = max(0.0, min(1.0, original_confidence + goal_modifier))
        else:
            adjusted_confidence = original_result.get("confidence", 0.5)
            support_ratio = 0.0
            challenge_ratio = 0.0
        
        # Build KS32a result
        result = dict(original_result)
        result["version"] = self.VERSION
        result["autonomous_goals"] = {
            "generated": goals.get("goal_count", 0),
            "verified": goal_total,
            "supporting": goal_support,
            "challenging": goal_challenge,
            "goal_results": goal_results,
            "sources": goals.get("sources", {}),
        }
        result["original_confidence"] = original_result.get("confidence", 0.5)
        result["adjusted_confidence"] = round(adjusted_confidence, 4)
        result["confidence"] = round(adjusted_confidence, 4)
        
        if store:
            store.write("ks32a_goals", result["autonomous_goals"])
        
        return result
    
    def _lightweight_verify(self, claim, store=None):
        """Lightweight verification for auto-generated goals.
        
        Structural check only — no API calls, no domain bridge.
        Goals are structural probes, not full claims.
        """
        # Ultra-lightweight: just check structural templates
        try:
            from .analogical_transfer import match_templates
        except ImportError:
            from analogical_transfer import match_templates
        
        text = claim.text if hasattr(claim, 'text') else str(claim)
        matches = match_templates(text)
        
        if matches:
            best = matches[0]
            confidence = best.confidence
            verdict = "PARTIALLY_VERIFIED" if confidence > 0.5 else "EXPLORING"
        else:
            confidence = 0.3
            verdict = "UNVERIFIED"
        
        return {
            "verdict": verdict,
            "confidence": confidence,
            "method": "lightweight_template_match",
        }
