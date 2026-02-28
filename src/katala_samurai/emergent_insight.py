"""
Emergent Insight Detector — Find non-obvious patterns across verification layers.

IQ160+PhD researchers don't just verify — they notice unexpected connections:
  - Cross-layer contradictions that reveal hidden assumptions
  - Patterns that no single layer detected but emerge from combining results
  - Structural similarities between unrelated claims (analogical transfer)
  - "Wait, this implies..." moments from combining partial evidence

Target: Beyond PhD — emergent reasoning from mechanical verification layers.

Design: Youta Hilono, 2026-02-28
"""

import re
from typing import Dict, Any, List, Optional
from collections import defaultdict


class InsightDetector:
    """Detect emergent insights from cross-layer verification results."""
    
    def __init__(self):
        self._insight_cache = []
    
    def analyze(self, result: Dict[str, Any], plan: Dict[str, Any] = None) -> Dict[str, Any]:
        """Find emergent insights from a completed verification result."""
        insights = []
        
        # ── 1) Cross-Layer Contradiction Mining ──
        insights.extend(self._mine_contradictions(result))
        
        # ── 2) Implicit Assumption Detection ──
        insights.extend(self._detect_implicit_assumptions(result, plan))
        
        # ── 3) Unexpected Correlation ──
        insights.extend(self._find_unexpected_correlations(result))
        
        # ── 4) Plan-Reality Divergence Insight ──
        if plan:
            insights.extend(self._plan_divergence_insight(result, plan))
        
        # ── 5) Structural Pattern Recognition ──
        insights.extend(self._structural_patterns(result))
        
        # Rank by novelty
        for i, insight in enumerate(insights):
            insight["id"] = f"INS-{i:03d}"
        
        # Confidence modifier: genuine insights should increase uncertainty
        # (discovering hidden complexity means we know LESS, not more)
        has_high = any(i["novelty"] == "high" for i in insights)
        modifier = -0.03 * len([i for i in insights if i["novelty"] == "high"])
        
        self._insight_cache.extend(insights)
        if len(self._insight_cache) > 100:
            self._insight_cache = self._insight_cache[-100:]
        
        return {
            "insights": insights,
            "count": len(insights),
            "high_novelty": len([i for i in insights if i["novelty"] == "high"]),
            "confidence_modifier": round(max(-0.15, modifier), 4),
            "summary": "; ".join(i["insight"][:60] for i in insights[:3]) if insights else "no emergent insights",
        }
    
    def _mine_contradictions(self, result: Dict[str, Any]) -> List[Dict]:
        """Find layers that contradict each other in interesting ways."""
        insights = []
        
        l6 = result.get("L6_statistical", {})
        l7 = result.get("L7_adversarial", {})
        deep = result.get("deep_causal", {})
        trace = result.get("reasoning_trace", {})
        
        l6_mod = l6.get("modifier", 0)
        l7_mod = l7.get("modifier", 0)
        
        # L6 says stats OK but L7 says adversarial concerns
        if l6_mod > 0 and l7_mod < 0:
            insights.append({
                "type": "cross_layer_contradiction",
                "insight": "Statistics pass but adversarial concerns exist — claim may be technically correct but misleadingly framed",
                "layers": ["L6", "L7"],
                "novelty": "high",
                "implication": "Check for cherry-picked statistics or missing context",
            })
        
        # High confidence but many reasoning leaps
        conf = result.get("confidence", 0.5)
        leaps = trace.get("leaps", 0)
        if conf > 0.7 and leaps > 5:
            insights.append({
                "type": "confidence_leap_mismatch",
                "insight": f"Confidence {conf:.0%} despite {leaps} unjustified reasoning leaps — possible false certainty",
                "layers": ["trace", "core"],
                "novelty": "high",
                "implication": "Confidence may be inflated by mutually-reinforcing assumptions",
            })
        
        # Deep causal enhanced but L7 found hidden assumptions
        if deep.get("status") == "enhanced" and l7_mod < 0:
            insights.append({
                "type": "causal_adversarial_tension",
                "insight": "Causal structure verified but adversarial layer found vulnerabilities — causal model may be too simple",
                "layers": ["L5_deep", "L7"],
                "novelty": "medium",
                "implication": "Missing confounders not in ConceptNet",
            })
        
        return insights
    
    def _detect_implicit_assumptions(self, result: Dict, plan: Dict = None) -> List[Dict]:
        """Find assumptions the verification implicitly relied on."""
        insights = []
        
        claim = result.get("claim", "")
        
        # Temporal assumption: claim uses present tense but may be historically contingent
        if re.search(r'\b(is|are|has|does)\b', claim) and not re.search(r'\b(always|forever|necessarily)\b', claim.lower()):
            if result.get("confidence", 0) > 0.7:
                insights.append({
                    "type": "temporal_assumption",
                    "insight": "High confidence assumes current truth — claim may be time-dependent",
                    "novelty": "medium",
                    "implication": "Consider: was this true 50 years ago? Will it be true in 50 years?",
                })
        
        # Scope assumption: claim may be culture/region specific
        if not re.search(r'\b(worldwide|universally|everywhere|all)\b', claim.lower()):
            if result.get("confidence", 0) > 0.8:
                insights.append({
                    "type": "scope_assumption",
                    "insight": "Verification assumed universal scope — claim may be culturally/regionally specific",
                    "novelty": "low",
                    "implication": "KS29B cultural solvers would catch this with regional variation",
                })
        
        return insights
    
    def _find_unexpected_correlations(self, result: Dict) -> List[Dict]:
        """Find unexpected patterns across layer outputs."""
        insights = []
        
        # If monitoring score is low but confidence is high → self-deception risk
        trace = result.get("reasoning_trace", {})
        monitoring = trace.get("monitoring_score", 1.0)
        conf = result.get("confidence", 0.5)
        
        if monitoring < 0.5 and conf > 0.6:
            insights.append({
                "type": "self_deception_risk",
                "insight": f"Low monitoring quality ({monitoring:.0%}) with moderate+ confidence ({conf:.0%}) — potential self-deception",
                "novelty": "high",
                "implication": "The verification process itself may have systematic blind spots on this claim type",
            })
        
        return insights
    
    def _plan_divergence_insight(self, result: Dict, plan: Dict) -> List[Dict]:
        """Extract insights from plan vs reality divergence."""
        insights = []
        
        eval_ = result.get("plan_evaluation", {})
        surprise = eval_.get("surprise", 0)
        
        if surprise > 0.15:
            accuracy = eval_.get("accuracy", "")
            insights.append({
                "type": "plan_surprise",
                "insight": f"Plan predicted {plan.get('criteria',{}).get('expected_range','?')} but got {eval_.get('actual_confidence','?')} — {accuracy}",
                "novelty": "medium",
                "implication": f"Claim type '{plan.get('primary_type','?')}' model needs recalibration",
            })
        
        return insights
    
    def _structural_patterns(self, result: Dict) -> List[Dict]:
        """Detect structural patterns in the verification result itself."""
        insights = []
        
        # All layers agree → suspicious unanimity (real disagreement expected)
        reg = result.get("self_regulation", {})
        if reg.get("health") == "HEALTHY" and result.get("confidence", 0) > 0.8:
            l6_mod = result.get("L6_statistical", {}).get("modifier", 0)
            l7_mod = result.get("L7_adversarial", {}).get("modifier", 0)
            if l6_mod >= 0 and l7_mod >= 0:
                insights.append({
                    "type": "suspicious_unanimity",
                    "insight": "All layers agree with high confidence — real-world claims rarely achieve full consensus",
                    "novelty": "medium",
                    "implication": "May indicate the claim is trivially true or the layers share a common blind spot",
                })
        
        return insights
