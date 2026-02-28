"""
Failure Learner — Session-scoped learning from verification failures.

IQ160 PhD advantage: they remember WITHIN a session what went wrong and adjust.
This module:
  - Tracks which claim types caused the most corrections/surprises
  - Adjusts strategy selection based on session failures
  - Detects systematic blind spots (same error pattern recurring)
  - Generates "lessons learned" per session (ephemeral, never persisted)

Respects KS anti-accumulation principle: session-scoped only.

Target: Failure Learning 85% → 93%+

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional
from collections import defaultdict


class FailureLearner:
    """Session-scoped failure analysis and adaptation."""
    
    def __init__(self):
        self._failures = []
        self._successes = []
        self._blind_spots = defaultdict(int)
        self._type_adjustments = {}
    
    def record_outcome(self, claim_type: str, verdict: str, confidence: float,
                       corrections: List[str], surprise: float, plan_accuracy: str):
        """Record a verification outcome for learning."""
        entry = {
            "type": claim_type,
            "verdict": verdict,
            "confidence": confidence,
            "corrections": corrections,
            "surprise": surprise,
            "plan_accuracy": plan_accuracy,
        }
        
        is_failure = (
            len(corrections) >= 2 or
            surprise > 0.15 or
            plan_accuracy.startswith("SURPRISED") or
            "fragile_verdict" in corrections or
            "self_deception_correction" in corrections
        )
        
        if is_failure:
            self._failures.append(entry)
            self._update_blind_spots(entry)
        else:
            self._successes.append(entry)
    
    def _update_blind_spots(self, failure: Dict):
        """Track recurring failure patterns."""
        for correction in failure["corrections"]:
            key = f"{failure['type']}:{correction}"
            self._blind_spots[key] += 1
    
    def get_adjustments(self, claim_type: str) -> Dict[str, Any]:
        """Get learned adjustments for a claim type based on session failures."""
        adjustments = {
            "confidence_bias": 0,
            "force_layers": [],
            "warnings": [],
            "strategy_override": None,
        }
        
        # Check blind spots for this type
        type_failures = [f for f in self._failures if f["type"] == claim_type]
        
        if len(type_failures) >= 2:
            # Systematic problem with this type
            avg_surprise = sum(f["surprise"] for f in type_failures) / len(type_failures)
            adjustments["confidence_bias"] = round(-0.05 * len(type_failures), 3)
            adjustments["warnings"].append(
                f"This session has {len(type_failures)} failures on '{claim_type}' claims (avg surprise: {avg_surprise:.2f})"
            )
        
        # Check for recurring corrections
        correction_counts = defaultdict(int)
        for f in type_failures:
            for c in f["corrections"]:
                correction_counts[c] += 1
        
        for correction, count in correction_counts.items():
            if count >= 2:
                adjustments["warnings"].append(f"Recurring: '{correction}' happened {count}x on {claim_type}")
                
                if correction == "fragile_verdict":
                    adjustments["force_layers"].append("L7_adv")
                    adjustments["strategy_override"] = "consensus_seeking"
                elif correction in ("miscalibrated", "high_meta_uncertainty"):
                    adjustments["confidence_bias"] = min(adjustments["confidence_bias"], -0.08)
                elif correction == "self_deception_correction":
                    adjustments["force_layers"].extend(["L7_adv", "L6_stat"])
                    adjustments["strategy_override"] = "devil_advocate"
        
        return adjustments
    
    def detect_systematic_blind_spots(self) -> List[Dict[str, Any]]:
        """Find patterns across ALL failures in this session."""
        spots = []
        
        for key, count in self._blind_spots.items():
            if count >= 2:
                claim_type, correction = key.split(":", 1)
                spots.append({
                    "claim_type": claim_type,
                    "correction_type": correction,
                    "occurrences": count,
                    "severity": "high" if count >= 3 else "medium",
                    "recommendation": f"Session has systematic '{correction}' issue with '{claim_type}' claims",
                })
        
        # Cross-type patterns
        all_corrections = defaultdict(int)
        for f in self._failures:
            for c in f["corrections"]:
                all_corrections[c] += 1
        
        for correction, count in all_corrections.items():
            if count >= 3:
                spots.append({
                    "claim_type": "ALL",
                    "correction_type": correction,
                    "occurrences": count,
                    "severity": "critical",
                    "recommendation": f"'{correction}' is a global session blind spot ({count} occurrences across types)",
                })
        
        return spots
    
    def session_report(self) -> Dict[str, Any]:
        """End-of-session learning summary."""
        total = len(self._failures) + len(self._successes)
        if total == 0:
            return {"total": 0, "lessons": []}
        
        failure_rate = len(self._failures) / total
        
        lessons = []
        spots = self.detect_systematic_blind_spots()
        
        for spot in spots:
            lessons.append(
                f"Blind spot: {spot['correction_type']} on {spot['claim_type']} "
                f"({spot['occurrences']}x, {spot['severity']})"
            )
        
        # Type-specific lessons
        type_failures = defaultdict(int)
        type_total = defaultdict(int)
        for f in self._failures:
            type_failures[f["type"]] += 1
        for s in self._successes:
            type_total[s["type"]] += 1
        for f in self._failures:
            type_total[f["type"]] += 1
        
        for t, count in type_failures.items():
            rate = count / type_total.get(t, 1)
            if rate > 0.5:
                lessons.append(f"Weak on '{t}' claims: {rate:.0%} failure rate this session")
        
        return {
            "total_verifications": total,
            "failures": len(self._failures),
            "failure_rate": round(failure_rate, 3),
            "blind_spots": spots,
            "lessons": lessons,
            "adaptations_applied": sum(1 for t in self._type_adjustments.values() if t),
        }
    
    def reset(self):
        """Session reset — all learning is ephemeral."""
        self._failures.clear()
        self._successes.clear()
        self._blind_spots.clear()
        self._type_adjustments.clear()
