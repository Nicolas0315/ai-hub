"""
Space of Reasons — Inter-solver justification network.

Sellars/Brandom: beliefs are justified by their position in the "space of reasons".
An isolated belief with no justificatory connections is not knowledge.

Solvers don't just output verdicts — they output REASONS.
This module checks if those reasons are mutually coherent.

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional
import re


class ReasonSpace:
    """Build and analyze a justification network between solver outputs."""
    
    def __init__(self):
        self._reasons = []  # List of (solver, reason_text, confidence)
    
    def register(self, solver_id: str, reason: str, confidence: float,
                 verdict: str = "", evidence_type: str = ""):
        """Register a solver's reason in the space."""
        self._reasons.append({
            "solver": solver_id,
            "reason": reason[:300],
            "confidence": confidence,
            "verdict": verdict,
            "evidence_type": evidence_type,
        })
    
    def analyze_coherence(self) -> Dict[str, Any]:
        """Check mutual coherence of all registered reasons."""
        if len(self._reasons) < 2:
            return {
                "coherence": 1.0,
                "conflicts": [],
                "conflict_count": 0,
                "isolated_solvers": [],
                "support_pairs": 0,
                "confidence_modifier": 0,
                "assessment": "COHERENT",
                "clusters": 0,
            }
        
        conflicts = []
        support_pairs = []
        
        # Pairwise analysis
        for i, r1 in enumerate(self._reasons):
            for j, r2 in enumerate(self._reasons):
                if j <= i:
                    continue
                
                rel = self._assess_relation(r1, r2)
                
                if rel["type"] == "CONFLICT":
                    conflicts.append({
                        "solvers": [r1["solver"], r2["solver"]],
                        "reason": rel["reason"],
                        "severity": rel["severity"],
                    })
                elif rel["type"] == "SUPPORT":
                    support_pairs.append((r1["solver"], r2["solver"]))
        
        # Find isolated solvers (no support connections)
        connected = set()
        for a, b in support_pairs:
            connected.add(a)
            connected.add(b)
        
        all_solvers = set(r["solver"] for r in self._reasons)
        isolated = all_solvers - connected
        
        # Coherence score
        max_conflicts = len(self._reasons) * (len(self._reasons) - 1) / 2
        conflict_ratio = len(conflicts) / max(max_conflicts, 1)
        isolation_ratio = len(isolated) / max(len(all_solvers), 1)
        
        coherence = max(0, 1.0 - conflict_ratio * 2 - isolation_ratio * 0.5)
        
        # Confidence modifier: low coherence should reduce confidence
        modifier = 0
        if coherence < 0.5:
            modifier = -0.1 * (1 - coherence)
        if len(conflicts) >= 3:
            modifier -= 0.05
        
        return {
            "coherence": round(coherence, 4),
            "conflicts": conflicts[:5],  # Top 5
            "conflict_count": len(conflicts),
            "isolated_solvers": sorted(isolated),
            "support_pairs": len(support_pairs),
            "confidence_modifier": round(modifier, 4),
            "assessment": (
                "COHERENT" if coherence > 0.7
                else "PARTIALLY_COHERENT" if coherence > 0.4
                else "INCOHERENT"
            ),
        }
    
    def _assess_relation(self, r1: Dict, r2: Dict) -> Dict[str, Any]:
        """Assess the relation between two solver reasons."""
        # Confidence direction conflict
        c1, c2 = r1["confidence"], r2["confidence"]
        v1, v2 = r1.get("verdict", ""), r2.get("verdict", "")
        
        # Strong directional conflict
        if c1 > 0.7 and c2 < 0.3:
            return {"type": "CONFLICT", "reason": "directional_opposition",
                    "severity": "high"}
        if c1 < 0.3 and c2 > 0.7:
            return {"type": "CONFLICT", "reason": "directional_opposition",
                    "severity": "high"}
        
        # Verdict conflict
        pos = {"VERIFIED", "TRUE", "PASS", "CONSISTENT"}
        neg = {"UNVERIFIED", "FALSE", "FAIL", "INCONSISTENT"}
        v1_pos = any(p in str(v1).upper() for p in pos)
        v1_neg = any(n in str(v1).upper() for n in neg)
        v2_pos = any(p in str(v2).upper() for p in pos)
        v2_neg = any(n in str(v2).upper() for n in neg)
        
        if (v1_pos and v2_neg) or (v1_neg and v2_pos):
            return {"type": "CONFLICT", "reason": "verdict_contradiction",
                    "severity": "medium"}
        
        # Keyword-based support detection
        r1_words = set(re.findall(r'\b\w+\b', r1["reason"].lower()))
        r2_words = set(re.findall(r'\b\w+\b', r2["reason"].lower()))
        overlap = len(r1_words & r2_words)
        
        if overlap >= 3 and abs(c1 - c2) < 0.2:
            return {"type": "SUPPORT", "reason": f"shared_concepts({overlap})",
                    "severity": "none"}
        
        return {"type": "INDEPENDENT", "reason": "no_clear_relation",
                "severity": "none"}
    
    def clear(self):
        self._reasons.clear()
