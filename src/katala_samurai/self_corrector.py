"""
Self-Corrector — Autonomous error detection and correction during verification.

IQ160+PhD researchers catch their own mistakes mid-reasoning:
  - "Wait, I assumed X but that contradicts Y"
  - "My conclusion changed when I removed one piece of evidence — fragile"
  - "I'm more confident than my evidence supports — recalibrate"
  - Ablation: systematically remove each layer's contribution to test robustness

Target: Failure Learning 40% → 85%+, Self-Monitoring boost.

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional
import copy


class SelfCorrector:
    """Detect and correct errors in verification results autonomously."""
    
    def __init__(self):
        self._corrections_log = []
    
    def correct(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze result for self-correctable errors. Returns corrections."""
        corrections = []
        
        # ── 1) Fragility Test (ablation) ──
        corrections.extend(self._test_fragility(result))
        
        # ── 2) Confidence Calibration Check ──
        corrections.extend(self._check_calibration(result))
        
        # ── 3) Verdict Consistency Check ──
        corrections.extend(self._check_verdict_consistency(result))
        
        # ── 4) Dead Zone Escape ──
        corrections.extend(self._escape_dead_zone(result))
        
        # ── 5) Contradiction Resolution ──
        corrections.extend(self._resolve_contradictions(result))
        
        # Apply corrections
        applied = []
        conf_adj = 0
        new_verdict = None
        
        for c in corrections:
            if c.get("auto_apply"):
                applied.append(c)
                conf_adj += c.get("confidence_adjustment", 0)
                if c.get("verdict_override"):
                    new_verdict = c["verdict_override"]
        
        total_adj = max(-0.2, min(0.1, conf_adj))
        
        self._corrections_log.extend(corrections)
        if len(self._corrections_log) > 200:
            self._corrections_log = self._corrections_log[-200:]
        
        return {
            "corrections": corrections,
            "applied": len(applied),
            "total": len(corrections),
            "confidence_adjustment": round(total_adj, 4),
            "verdict_override": new_verdict,
            "details": [c["type"] for c in corrections],
        }
    
    def _test_fragility(self, result: Dict) -> List[Dict]:
        """Would removing any single layer's contribution flip the verdict?"""
        corrections = []
        conf = result.get("confidence", 0.5)
        
        removable = {
            "L6": result.get("L6_statistical", {}).get("modifier", 0),
            "L7": result.get("L7_adversarial", {}).get("modifier", 0),
            "deep_causal": result.get("deep_causal", {}).get("adjustment",
                           result.get("deep_causal", {}).get("confidence_adjustment", 0)),
            "trace": result.get("metacognition", {}).get("trace_modifier", 0),
            "regulation": result.get("metacognition", {}).get("regulation_modifier", 0),
        }
        
        for layer, mod in removable.items():
            if mod == 0:
                continue
            conf_without = conf - mod
            
            # Would verdict change?
            original_verdict = result.get("verdict", "")
            if conf > 0.65 and conf_without < 0.5:
                corrections.append({
                    "type": "fragile_verdict",
                    "detail": f"Removing {layer} (mod={mod:+.3f}) drops conf {conf:.2f}→{conf_without:.2f} — verdict depends on single layer",
                    "severity": "high",
                    "auto_apply": True,
                    "confidence_adjustment": -0.05,
                    "recommendation": f"Verdict fragile: entirely dependent on {layer}",
                })
            elif conf < 0.35 and conf_without > 0.5:
                corrections.append({
                    "type": "fragile_rejection",
                    "detail": f"Removing {layer} (mod={mod:+.3f}) raises conf {conf:.2f}→{conf_without:.2f} — rejection depends on single layer",
                    "severity": "high",
                    "auto_apply": True,
                    "confidence_adjustment": 0.05,
                    "verdict_override": "EXPLORING",
                    "recommendation": f"Rejection fragile: reconsider with {layer} results weighted lower",
                })
        
        return corrections
    
    def _check_calibration(self, result: Dict) -> List[Dict]:
        """Is confidence consistent with uncertainty estimate?"""
        corrections = []
        
        unc = result.get("uncertainty", {})
        ci = unc.get("ci_95", [0, 1])
        conf = result.get("confidence", 0.5)
        calibration = unc.get("calibration", "")
        
        if calibration == "MISCALIBRATED":
            corrections.append({
                "type": "miscalibrated",
                "detail": f"Confidence {conf:.2f} outside 95% CI [{ci[0]:.2f}, {ci[1]:.2f}]",
                "severity": "high",
                "auto_apply": True,
                "confidence_adjustment": -0.05,
                "recommendation": "Recalibrate: confidence should fall within bootstrap CI",
            })
        
        # 2nd-order uncertainty too high → reduce confidence
        second_order = unc.get("second_order", 0)
        if second_order > 0.25 and conf > 0.7:
            corrections.append({
                "type": "high_meta_uncertainty",
                "detail": f"2nd-order uncertainty {second_order:.2f} with confidence {conf:.2f} — we're uncertain about how uncertain we are",
                "severity": "medium",
                "auto_apply": True,
                "confidence_adjustment": -0.03,
                "recommendation": "High meta-uncertainty should cap confidence",
            })
        
        return corrections
    
    def _check_verdict_consistency(self, result: Dict) -> List[Dict]:
        """Does the verdict match the confidence level?"""
        corrections = []
        conf = result.get("confidence", 0.5)
        verdict = result.get("verdict", "")
        
        mismatches = [
            (verdict == "VERIFIED" and conf < 0.7, "EXPLORING", "VERIFIED at low confidence"),
            (verdict == "UNVERIFIED" and conf > 0.5, "EXPLORING", "UNVERIFIED at moderate confidence"),
        ]
        
        for condition, override, desc in mismatches:
            if condition:
                corrections.append({
                    "type": "verdict_mismatch",
                    "detail": f"{desc}: verdict={verdict} conf={conf:.2f}",
                    "severity": "medium",
                    "auto_apply": True,
                    "verdict_override": override,
                    "confidence_adjustment": 0,
                    "recommendation": f"Verdict should be {override} at this confidence level",
                })
        
        return corrections
    
    def _escape_dead_zone(self, result: Dict) -> List[Dict]:
        """Confidence stuck in 0.4-0.6 dead zone — acknowledge genuine uncertainty."""
        corrections = []
        conf = result.get("confidence", 0.5)
        
        if 0.4 <= conf <= 0.6:
            corrections.append({
                "type": "dead_zone",
                "detail": f"Confidence {conf:.2f} in dead zone [0.4-0.6] — this IS the answer: genuine uncertainty",
                "severity": "low",
                "auto_apply": False,  # Don't auto-adjust, just acknowledge
                "confidence_adjustment": 0,
                "recommendation": "Dead zone = honest signal. Report uncertainty bounds rather than forcing a verdict.",
            })
        
        return corrections
    
    def _resolve_contradictions(self, result: Dict) -> List[Dict]:
        """Try to resolve contradictions found by insight detector."""
        corrections = []
        
        insights = result.get("emergent_insights", {}).get("insights", [])
        for insight in insights:
            if insight.get("type") == "self_deception_risk":
                corrections.append({
                    "type": "self_deception_correction",
                    "detail": "Insight detector flagged self-deception risk — applying confidence penalty",
                    "severity": "high",
                    "auto_apply": True,
                    "confidence_adjustment": -0.08,
                    "recommendation": "Low monitoring + high confidence = systematic blind spot",
                })
            elif insight.get("type") == "suspicious_unanimity":
                corrections.append({
                    "type": "unanimity_skepticism",
                    "detail": "All layers agree too perfectly — real claims have nuance",
                    "severity": "medium",
                    "auto_apply": True,
                    "confidence_adjustment": -0.03,
                    "recommendation": "Perfect agreement suggests shared assumptions, not truth",
                })
        
        return corrections
    
    def correction_stats(self) -> Dict[str, Any]:
        """Summary statistics of all corrections made."""
        if not self._corrections_log:
            return {"total": 0}
        
        from collections import Counter
        types = Counter(c["type"] for c in self._corrections_log)
        severities = Counter(c.get("severity", "?") for c in self._corrections_log)
        
        return {
            "total": len(self._corrections_log),
            "by_type": dict(types),
            "by_severity": dict(severities),
            "most_common": types.most_common(3),
        }
