"""
Self-Other Boundary Model — KS39a

Provenance tracking + self-other distinction for verification processes.

3 components:
  1) Provenance Tracker: tags every judgment with origin (SELF/DESIGNER/EXTERNAL/INHERITED)
  2) Boundary Detector: identifies when KS is executing designer cognition vs its own
  3) Attribution Auditor: post-hoc audit of "who decided what"

Design request: Youta Hilono, 2026-02-28
Implementation: Shirokuma, 2026-02-28
"""

from typing import Dict, List, Any, Optional
from enum import Enum
import hashlib
import time


class Origin(Enum):
    """Who originated this judgment?"""
    SELF = "self"              # KS's own solver/pipeline computation
    DESIGNER = "designer"      # Youta's architectural decision (hardcoded logic)
    EXTERNAL = "external"      # LLM API response, web data, user input
    INHERITED = "inherited"    # Carried from parent KS version without re-derivation
    AMBIGUOUS = "ambiguous"    # Cannot determine origin


class ProvenanceRecord:
    """Single provenance entry."""
    __slots__ = ("stage", "origin", "confidence", "reasoning", "timestamp", "fingerprint")
    
    def __init__(self, stage: str, origin: Origin, confidence: float,
                 reasoning: str = "", timestamp: float = 0):
        self.stage = stage
        self.origin = origin
        self.confidence = confidence
        self.reasoning = reasoning
        self.timestamp = timestamp or time.time()
        self.fingerprint = hashlib.sha256(
            f"{stage}:{origin.value}:{confidence}:{reasoning}".encode()
        ).hexdigest()[:12]


class ProvenanceTracker:
    """Tags every judgment with its origin."""
    
    def __init__(self):
        self._records: List[ProvenanceRecord] = []
        # Designer-originated components (hardcoded architectural decisions)
        self._designer_stages = {
            "anti_accumulation",      # Design principle: don't accumulate
            "ephemeral_toggle",       # E1/E2/E3 toggle design
            "solver_weights",         # Initial solver weight assignment
            "layer_priority",         # L1-L7 ordering
            "inhibition_params",      # Lateral inhibition parameters
            "neuromod_curves",        # Neuromodulation sensitivity curves
            "predictive_priors",      # Predictive coding priors
            "reason_space_topology",  # Space of reasons graph structure
        }
    
    def record(self, stage: str, confidence: float, reasoning: str = "",
               origin: Optional[Origin] = None) -> ProvenanceRecord:
        """Record a judgment with provenance."""
        if origin is None:
            origin = self._classify_origin(stage, reasoning)
        
        rec = ProvenanceRecord(stage, origin, confidence, reasoning)
        self._records.append(rec)
        return rec
    
    def _classify_origin(self, stage: str, reasoning: str) -> Origin:
        """Auto-classify origin based on stage name and reasoning content."""
        # Designer decisions
        if stage in self._designer_stages:
            return Origin.DESIGNER
        
        # External: LLM responses, web fetches
        external_markers = ["llm_response", "api_", "web_", "openalex", "semantic_bridge"]
        if any(m in stage.lower() for m in external_markers):
            return Origin.EXTERNAL
        
        # Self: solver computations, statistical tests, formal logic
        self_markers = ["S0", "S1", "S2", "L1", "L2", "L3", "L4", "L5", "L6", "L7",
                        "bootstrap", "cosine", "entropy", "inhibit", "coherence"]
        if any(m in stage for m in self_markers):
            return Origin.SELF
        
        # Inherited: version tags, parent results
        if "inherit" in stage.lower() or "parent" in stage.lower():
            return Origin.INHERITED
        
        return Origin.AMBIGUOUS
    
    def get_all(self) -> List[Dict[str, Any]]:
        return [
            {
                "stage": r.stage,
                "origin": r.origin.value,
                "confidence": r.confidence,
                "reasoning": r.reasoning[:100],
                "fingerprint": r.fingerprint,
            }
            for r in self._records
        ]
    
    def summary(self) -> Dict[str, Any]:
        """Provenance summary: who contributed how much?"""
        counts = {o.value: 0 for o in Origin}
        conf_sums = {o.value: 0.0 for o in Origin}
        
        for r in self._records:
            counts[r.origin.value] += 1
            conf_sums[r.origin.value] += r.confidence
        
        total = len(self._records) or 1
        return {
            "total_judgments": len(self._records),
            "origin_distribution": {
                k: {"count": v, "pct": round(v / total * 100, 1)}
                for k, v in counts.items() if v > 0
            },
            "avg_confidence_by_origin": {
                k: round(conf_sums[k] / counts[k], 4) if counts[k] > 0 else None
                for k in counts if counts[k] > 0
            },
        }


class BoundaryDetector:
    """Detects when KS is executing designer cognition vs its own reasoning."""
    
    def __init__(self, tracker: ProvenanceTracker):
        self.tracker = tracker
    
    def detect_fusion(self) -> Dict[str, Any]:
        """Check if self/designer boundary is blurred."""
        records = self.tracker._records
        if not records:
            return {"fusion_risk": 0, "assessment": "NO_DATA"}
        
        ambiguous = sum(1 for r in records if r.origin == Origin.AMBIGUOUS)
        designer = sum(1 for r in records if r.origin == Origin.DESIGNER)
        self_count = sum(1 for r in records if r.origin == Origin.SELF)
        total = len(records)
        
        # Fusion risk: high ambiguity + high designer ratio = can't tell who's thinking
        ambig_ratio = ambiguous / total
        designer_ratio = designer / total if total > 0 else 0
        
        fusion_risk = round(ambig_ratio * 0.6 + designer_ratio * 0.4, 4)
        
        if fusion_risk > 0.7:
            assessment = "FUSED"
            detail = "KSは自己と設計者の判断を区別できていない"
        elif fusion_risk > 0.4:
            assessment = "BLURRED"
            detail = "境界が曖昧。一部の判断の出所が不明"
        elif fusion_risk > 0.15:
            assessment = "PARTIAL"
            detail = "概ね区別できているが、一部曖昧な領域あり"
        else:
            assessment = "CLEAR"
            detail = "自己と設計者の境界が明確"
        
        return {
            "fusion_risk": fusion_risk,
            "assessment": assessment,
            "detail": detail,
            "ambiguous_pct": round(ambig_ratio * 100, 1),
            "designer_pct": round(designer_ratio * 100, 1),
            "self_pct": round(self_count / total * 100, 1) if total > 0 else 0,
        }


class AttributionAuditor:
    """Post-hoc audit: who decided the final verdict?"""
    
    def __init__(self, tracker: ProvenanceTracker):
        self.tracker = tracker
    
    def audit(self, final_verdict: str, final_confidence: float) -> Dict[str, Any]:
        """Audit the final verdict attribution."""
        records = self.tracker._records
        if not records:
            return {"attribution": "UNKNOWN", "dominant_origin": "N/A"}
        
        # Which origin contributed most to the final confidence?
        origin_influence = {}
        for r in records:
            o = r.origin.value
            if o not in origin_influence:
                origin_influence[o] = {"weight_sum": 0, "count": 0}
            origin_influence[o]["weight_sum"] += r.confidence
            origin_influence[o]["count"] += 1
        
        # Dominant origin
        dominant = max(origin_influence.items(), key=lambda x: x[1]["weight_sum"])
        
        # Check if verdict could change without designer components
        designer_records = [r for r in records if r.origin == Origin.DESIGNER]
        self_records = [r for r in records if r.origin == Origin.SELF]
        
        self_only_conf = (
            sum(r.confidence for r in self_records) / len(self_records)
            if self_records else 0.5
        )
        
        dependency = abs(final_confidence - self_only_conf)
        
        return {
            "final_verdict": final_verdict,
            "final_confidence": final_confidence,
            "dominant_origin": dominant[0],
            "origin_influence": {
                k: round(v["weight_sum"] / v["count"], 4)
                for k, v in origin_influence.items()
            },
            "designer_dependency": round(dependency, 4),
            "self_sufficient": dependency < 0.1,
            "note": (
                "設計者判断を除外しても結論は変わらない" if dependency < 0.1
                else f"設計者判断への依存度: {dependency:.1%}"
            ),
        }
