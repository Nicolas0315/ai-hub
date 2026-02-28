"""
KS33b — Katala Samurai 33b: Resilient Architecture Upgrade

KS33a + 6 architectural fixes:
  #1 Pipeline Resilience: fallback chains + parallel execution
  #2 Content Bridge: bidirectional content↔formal layer
  #4 Template Extractor: auto-extract from OpenAlex papers
  #5 Session Guardian: time-based reset with user confirmation
  #6 Causal Domain Mapper: Domain Bridge → DAG node mapping
  #7 Verification Terminator: auto-stop on convergence

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks33a import KS33a, Claim
    from .pipeline_resilience import FallbackChain, SessionCache, run_parallel
    from .content_bridge import bridge_content
    from .content_understanding import analyze_content
    from .session_guardian import SessionGuardian
    from .verification_terminator import should_terminate
    from .causal_domain_mapper import map_propositions_to_dag
    from .stage_store import StageStore
except ImportError:
    from ks33a import KS33a, Claim
    from pipeline_resilience import FallbackChain, SessionCache, run_parallel
    from content_bridge import bridge_content
    from content_understanding import analyze_content
    from session_guardian import SessionGuardian
    from verification_terminator import should_terminate
    from causal_domain_mapper import map_propositions_to_dag
    from stage_store import StageStore


class KS33b(KS33a):
    """KS33a + Resilient Architecture.
    
    New features:
      - Pipeline resilience (fallback + parallel)
      - Content Bridge (content ↔ S01-S27 translator)
      - Session Guardian (reset prompts)
      - Verification Terminator (auto-stop)
      - Causal Domain Mapper (Domain Bridge → DAG)
    """
    
    VERSION = "KS33b"
    
    def __init__(self, ephemeral=True, time_limit=3600, verify_limit=50, **kwargs):
        super().__init__(ephemeral=ephemeral, **kwargs)
        self.guardian = SessionGuardian(
            self.session, time_limit=time_limit, verify_limit=verify_limit
        )
        self.cache = SessionCache()
        self._verification_history = []
    
    def verify(self, claim, store=None, skip_s28=True):
        """Full KS33b verification with architectural enhancements."""
        if store is None:
            store = StageStore()
        
        if isinstance(claim, str):
            claim = Claim(text=claim, evidence=[])
        
        # ── Session Guardian check ──
        guardian_status = self.guardian.check()
        if guardian_status["reset_recommended"]:
            # Don't block — include prompt in result
            pass
        
        # ── Content Understanding + Bridge ──
        cu_result = analyze_content(claim.text)
        cb_result = bridge_content(cu_result)
        
        # Inject content signals as additional evidence
        content_evidence = [
            s["proposition"] for s in cb_result.get("signals", [])
            if s.get("proposition")
        ]
        if content_evidence:
            if not hasattr(claim, '_original_evidence'):
                claim._original_evidence = list(claim.evidence) if claim.evidence else []
            claim.evidence = list(claim.evidence or []) + content_evidence[:5]
        
        # ── Run KS33a verification (with fallback protection) ──
        try:
            result = super().verify(claim, store=store, skip_s28=skip_s28)
        except Exception as e:
            # Graceful degradation
            result = {
                "verdict": "ERROR",
                "confidence": 0.0,
                "error": str(e)[:200],
                "trace": [],
            }
        
        # ── Content Bridge annotations ──
        result["content_bridge"] = {
            "signals": cb_result.get("signals_generated", 0),
            "confidence_modifier": cb_result["annotations"]["total_confidence_modifier"],
            "flags": cb_result["annotations"]["content_flags"],
        }
        
        # Apply content bridge modifier
        if cb_result["annotations"]["total_confidence_modifier"] != 0:
            old_conf = result.get("confidence", 0.5)
            new_conf = max(0.0, min(1.0, old_conf + cb_result["annotations"]["total_confidence_modifier"]))
            result["confidence"] = round(new_conf, 4)
        
        # ── Domain → DAG mapping ──
        domain_info = None
        for step in result.get("trace", []):
            if step.get("layer") == "DomainBridge":
                domain_info = step
                break
        
        if domain_info:
            # Get domain propositions from store
            domain_data = store._stages.get("domain_bridge", {}) if hasattr(store, '_stages') else {}
            props = domain_data.get("propositions", []) if isinstance(domain_data, dict) else []
            if props:
                dag_mapping = map_propositions_to_dag(props)
                result["causal_domain_mapping"] = {
                    "nodes": dag_mapping["node_count"],
                    "edges": dag_mapping["edge_count"],
                    "dag_ready": dag_mapping["dag_ready"],
                }
        
        # ── Verification history + termination check ──
        self._verification_history.append({
            "round": len(self._verification_history) + 1,
            "confidence": result.get("confidence", 0),
            "verdict": result.get("verdict", "UNKNOWN"),
        })
        
        gi_data = result.get("autonomous_goals", {}).get("intelligence", {})
        coverage = {
            "coverage_ratio": gi_data.get("coverage_ratio", 0),
            "uncovered": gi_data.get("uncovered_angles", []),
        } if gi_data else None
        
        termination = should_terminate(
            self._verification_history, coverage
        )
        result["termination"] = termination
        
        # ── Guardian status ──
        result["version"] = self.VERSION
        result["session_guardian"] = guardian_status
        if guardian_status.get("prompt"):
            result["session_prompt"] = guardian_status["prompt"]
        
        # ── Cache stats ──
        result["cache"] = self.cache.stats()
        
        if store:
            store.write("ks33b_meta", {
                "content_bridge_signals": cb_result.get("signals_generated", 0),
                "termination": termination.get("terminate", False),
                "guardian": guardian_status["status"],
            })
        
        return result
    
    def reset_learning(self):
        """Reset learning + clear verification history + cache."""
        super().reset_learning()
        self._verification_history.clear()
        self.cache.clear()


# Backward compat
KS33a_upgraded = KS33b
