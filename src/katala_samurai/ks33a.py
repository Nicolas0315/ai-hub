"""
KS33a — Katala Samurai 33a: Ephemeral Learning Verification

KS32a + Session-scoped volatile learning (E1+E2+E3)
with explicit on/off toggle for each mechanism.

Architecture:
  KS32a (KS31e + Goals) + EphemeralSession
  - E1 Calibration adjusts solver weights within session
  - E2 Pattern detects domain biases and boosts relevant goals
  - E3 Chain learns from goal verification results

Toggle API:
  session.toggle(True/False)           — global on/off
  session.toggle_mechanism("E1_calibration", True/False)
  session.toggle_mechanism("E2_pattern", True/False)
  session.toggle_mechanism("E3_chain", True/False)
  session.get_status()                 — full status report
  session.reset()                      — hard reset (= session end)

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks32a import KS32a, Claim
    from .ephemeral_learning import EphemeralSession
    from .stage_store import StageStore
    from .content_understanding import analyze_content
    from .goal_quality import filter_goals_by_quality
    from .learning_optimizer import LearningOptimizer
    from .goal_intelligence import enhance_goals
except ImportError:
    from ks32a import KS32a, Claim
    from ephemeral_learning import EphemeralSession
    from stage_store import StageStore
    from content_understanding import analyze_content
    from goal_quality import filter_goals_by_quality
    from learning_optimizer import LearningOptimizer
    from goal_intelligence import enhance_goals


class KS33a(KS32a):
    """KS32a + Ephemeral Learning with toggle control.
    
    Usage:
        ks = KS33a(ephemeral=True)  # learning ON by default
        ks.session.toggle(False)     # turn OFF
        ks.session.toggle_mechanism("E1_calibration", False)  # E1 only OFF
        ks.session.reset()           # hard reset
        status = ks.session.get_status()
    """
    
    VERSION = "KS33a"
    
    def __init__(self, ephemeral=True, **kwargs):
        super().__init__(**kwargs)
        self.session = EphemeralSession(enabled=ephemeral)
        self.optimizer = LearningOptimizer(self.session)
    
    def verify(self, claim, store=None, skip_s28=True):
        """Full verification with ephemeral learning.
        
        If learning is ON:
          - E1: Record solver results → adjust weights
          - E2: Record patterns → detect biases → boost goals
          - E3: Record goal chains → derive insights → adjust confidence
        
        If learning is OFF:
          - Falls through to KS32a.verify() unchanged
        """
        if store is None:
            store = StageStore()
        
        if isinstance(claim, str):
            claim = Claim(text=claim, evidence=[])
        
        # ── Content Understanding Enhancement ──
        cu_result = analyze_content(claim.text, store=store)
        if store:
            store.write("content_understanding", cu_result)

        # Run KS32a verification (includes KS31e + goals)
        result = super().verify(claim, store=store, skip_s28=skip_s28)
        result["content_understanding"] = {
            "negation_count": cu_result["negation"]["negation_count"],
            "meaning_change_risk": cu_result["negation"]["meaning_change_risk"],
            "semantic_roles": cu_result["semantic_roles"]["role_count"],
            "implications": cu_result["implications"]["count"],
            "reliability": cu_result["reliability"],
            "content_depth": cu_result["content_depth"],
        }

        # ── Goal Quality Filtering ──
        goals = result.get("autonomous_goals", {})
        if goals.get("goal_results"):
            quality_result = filter_goals_by_quality(
                goals["goal_results"], claim.text
            )
            result["autonomous_goals"]["quality_filtered"] = {
                "before": quality_result["total"],
                "after": quality_result["filtered"],
                "avg_quality": quality_result["avg_quality"],
            }

        # ── Goal Intelligence Enhancement ──
        if goals.get("goal_results"):
            gi_result = enhance_goals(claim.text, goals["goal_results"], store=store)
            result["autonomous_goals"]["intelligence"] = {
                "coverage_ratio": gi_result["coverage"]["ratio"],
                "covered_angles": gi_result["coverage"]["covered"],
                "uncovered_angles": gi_result["coverage"]["uncovered"],
                "meta_goals_added": gi_result["meta_goals_added"],
                "total_enhanced": gi_result["total_goals"],
            }
        
        if not self.session.enabled:
            result["version"] = self.VERSION
            result["ephemeral"] = {"enabled": False}
            return result
        
        # ── E1: Record solver results and apply calibration ──
        if self.session.is_mechanism_active("E1_calibration"):
            trace = result.get("trace", [])
            for step in trace:
                if step.get("layer") == "L1" and "solver_results" in step:
                    for sid, sr in step["solver_results"].items():
                        self.session.record_solver_result(
                            sid,
                            sr.get("passed", False),
                            sr.get("confidence"),
                        )
        
        # ── E2: Record patterns and detect biases ──
        if self.session.is_mechanism_active("E2_pattern"):
            # Record domain patterns from Domain Bridge
            domain_info = None
            for step in result.get("trace", []):
                if step.get("layer") == "DomainBridge":
                    for ptype in step.get("types", []):
                        self.session.record_domain_pattern("proposition_type", ptype)
                    domain_info = step
            
            # Record structural patterns from Analogical Transfer
            for step in result.get("trace", []):
                if step.get("layer") == "AnalogicalTransfer":
                    template = step.get("template")
                    if template:
                        self.session.record_structural_pattern(template, True)
            
            # Detect biases
            biases = self.session.detect_session_bias()
            if biases:
                result.setdefault("warnings", []).extend(
                    [f"Session bias: {b['recommendation']}" for b in biases]
                )
        
        # ── E3: Record goal results and apply chain learning ──
        if self.session.is_mechanism_active("E3_chain"):
            goals = result.get("autonomous_goals", {})
            for gr in goals.get("goal_results", []):
                self.session.record_goal_result(
                    gr.get("goal", ""),
                    gr.get("verdict", "UNKNOWN"),
                    gr.get("confidence", 0.0),
                )
            
            # Apply chain modifier to confidence
            chain_mod = self.session.get_chain_modifier()
            if chain_mod != 0.0:
                current = result.get("confidence", 0.5)
                adjusted = max(0.0, min(1.0, current + chain_mod))
                result["pre_chain_confidence"] = current
                result["confidence"] = round(adjusted, 4)
                result["chain_modifier"] = round(chain_mod, 4)
        
        # Add ephemeral status to result
        result["version"] = self.VERSION
        result["ephemeral"] = self.session.get_status()
        
        if store:
            store.write("ks33a_ephemeral", result["ephemeral"])
        
        return result
    
    # ─── Public Toggle API ──────────────────────────────────────────────
    
    def set_learning(self, enabled):
        """Global on/off for ephemeral learning.
        
        Args:
            enabled: True to enable, False to disable.
        Returns:
            Current state.
        """
        return self.session.toggle(enabled)
    
    def set_mechanism(self, mechanism, enabled):
        """Toggle a specific learning mechanism.
        
        Args:
            mechanism: "E1_calibration", "E2_pattern", or "E3_chain"
            enabled: True/False
        Returns:
            Current state.
        """
        return self.session.toggle_mechanism(mechanism, enabled)
    
    def learning_status(self):
        """Get full learning status."""
        return self.session.get_status()
    
    def reset_learning(self):
        """Hard reset all learning state. Like ending the session."""
        self.session.reset()


# Backward compat
KS32b = KS33a
