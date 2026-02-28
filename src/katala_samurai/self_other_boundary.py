"""
Self-Other Boundary Model — Provenance tracking for KS judgments.

Problem: KS can't distinguish between:
  - Its own computation (solver outputs)
  - Designer's embedded decisions (thresholds, weights, rules)
  - External sources (LLM API, ConceptNet, OpenAlex)

This module tracks WHERE each judgment originates,
measures fusion risk (designer-system boundary blur),
and flags when KS can't tell its own reasoning from the designer's.

Inspired by Theory of Mind (Premack & Woodruff, 1978)
and Self-Other Distinction in cognitive neuroscience (Decety & Sommerville, 2003).

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class Origin(str, Enum):
    """Where a judgment comes from."""
    SELF = "self"           # KS's own solver computation
    DESIGNER = "designer"   # Youta's design decisions (hardcoded thresholds, rules)
    EXTERNAL = "external"   # LLM API, ConceptNet, OpenAlex, web sources
    AMBIGUOUS = "ambiguous"  # Can't determine origin


@dataclass
class Provenance:
    """Track the origin of a single judgment."""
    solver_id: str
    origin: Origin
    confidence: float
    reason: str = ""
    detail: str = ""


class SelfOtherBoundary:
    """Track and analyze the provenance of all judgments in a verification."""

    # ── Designer-embedded components (hardcoded by Youta) ──
    DESIGNER_COMPONENTS = {
        # Thresholds
        "surprise_threshold",       # 0.15 in PredictiveEngine
        "dead_zone_range",          # 0.4-0.6 in SelfCorrector
        "early_exit_threshold",     # LOW + decisive in KS37a
        "toxicity_check_interval",  # every N in KS37a
        # Weights/matrices
        "type_effectiveness_matrix",  # 7x7 in MetacognitivePlanner
        "strategy_repertoire",       # 7 strategies in AdaptiveStrategy
        "type_similarity_matrix",    # in AutonomousLearner
        "neuro_type_mods",          # serotonergic in Neuromodulator
        # Rules
        "fusion_rules",             # StageFusion pairs
        "claim_patterns",           # regex patterns in classify_claim
        "verdict_thresholds",       # 0.65/0.35 boundaries
        "anti_accumulation",        # S28 design principle
    }

    # ── Self-computed components ──
    SELF_COMPONENTS = {
        "solver_output",            # S01-S27 raw results
        "bootstrap_ci",             # statistical computation
        "lateral_inhibition",       # signal processing
        "coherence_score",          # pairwise analysis
        "prediction_error",         # delta computation
        "calibration_check",        # self-corrector
        "fragility_test",           # ablation result
    }

    # ── External components ──
    EXTERNAL_COMPONENTS = {
        "conceptnet_lookup",
        "openlex_query",
        "wordnet_lookup",
        "llm_api_response",
        "web_fetch_result",
        "pdf_extraction",
    }

    def __init__(self):
        self._judgments: List[Provenance] = []

    def register(self, solver_id: str, origin: Origin, confidence: float,
                 reason: str = "", detail: str = ""):
        """Register a judgment with its provenance."""
        self._judgments.append(Provenance(
            solver_id=solver_id,
            origin=origin,
            confidence=confidence,
            reason=reason[:200],
            detail=detail[:200],
        ))

    def register_auto(self, solver_id: str, confidence: float,
                      component: str, reason: str = ""):
        """Auto-detect origin from component name."""
        if component in self.DESIGNER_COMPONENTS:
            origin = Origin.DESIGNER
        elif component in self.SELF_COMPONENTS:
            origin = Origin.SELF
        elif component in self.EXTERNAL_COMPONENTS:
            origin = Origin.EXTERNAL
        else:
            origin = Origin.AMBIGUOUS
        self.register(solver_id, origin, confidence, reason, component)

    def analyze(self) -> Dict[str, Any]:
        """Analyze provenance distribution and fusion risk."""
        if not self._judgments:
            return {
                "total_judgments": 0,
                "origin_distribution": {},
                "fusion": {"fusion_risk": 0.0, "assessment": "NO_DATA"},
                "attribution": {"dominant_origin": "none", "self_sufficient": True},
            }

        total = len(self._judgments)

        # ── Origin distribution ──
        counts = {o.value: 0 for o in Origin}
        conf_by_origin = {o.value: [] for o in Origin}

        for j in self._judgments:
            counts[j.origin.value] += 1
            conf_by_origin[j.origin.value].append(j.confidence)

        distribution = {k: round(v / total, 3) for k, v in counts.items() if v > 0}

        # ── Fusion risk: how blurred is the self-designer boundary? ──
        # High fusion = KS can't distinguish its own reasoning from designer's
        self_count = counts["self"]
        designer_count = counts["designer"]
        ambiguous_count = counts["ambiguous"]

        if self_count + designer_count == 0:
            fusion_risk = 0.0
        else:
            # Fusion risk increases when:
            # 1) Designer proportion is high (KS is just executing designer's rules)
            # 2) Ambiguous proportion is high (can't tell who decided)
            # 3) Self and designer confidences converge (indistinguishable)
            designer_ratio = designer_count / total
            ambiguous_ratio = ambiguous_count / total

            # Confidence convergence: how similar are self vs designer confidences?
            self_confs = conf_by_origin["self"]
            designer_confs = conf_by_origin["designer"]
            if self_confs and designer_confs:
                self_mean = sum(self_confs) / len(self_confs)
                designer_mean = sum(designer_confs) / len(designer_confs)
                convergence = 1.0 - abs(self_mean - designer_mean)
            else:
                convergence = 0.5

            fusion_risk = round(
                designer_ratio * 0.4 +
                ambiguous_ratio * 0.3 +
                convergence * 0.3,
                4
            )

        # Fusion assessment
        if fusion_risk > 0.7:
            fusion_assessment = "HIGH"
            fusion_detail = "KSの判断と設計者の判断が融合している。独立性が低い"
        elif fusion_risk > 0.4:
            fusion_assessment = "PARTIAL"
            fusion_detail = "概ね区別できているが、一部曖昧な領域あり"
        else:
            fusion_assessment = "LOW"
            fusion_detail = "KSの判断と設計者の判断は明確に区別されている"

        # ── Attribution: who dominates the judgment? ──
        dominant = max(counts, key=counts.get) if counts else "self"

        # Self-sufficiency: would the conclusion change without designer input?
        designer_dependency = designer_count / max(total, 1)
        self_sufficient = designer_dependency < 0.3

        return {
            "total_judgments": total,
            "origin_distribution": distribution,
            "fusion": {
                "fusion_risk": fusion_risk,
                "assessment": fusion_assessment,
                "detail": fusion_detail,
            },
            "attribution": {
                "dominant_origin": dominant,
                "designer_dependency": round(designer_dependency, 3),
                "self_sufficient": self_sufficient,
                "note": (
                    "設計者判断を除外しても結論は変わらない" if self_sufficient
                    else "設計者判断への依存度が高い。独立検証を推奨"
                ),
            },
        }

    def clear(self):
        self._judgments.clear()
