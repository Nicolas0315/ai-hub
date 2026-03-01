"""
KS34a — Katala Samurai 34a: Deep Causal Reasoning

KS33c + 3 causal reasoning upgrades:
  1) Multi-Step Intervention: do(X)→do(Y)→observe(Z) chains
  2) Temporal Causal Graph: time-aware DAG with precedence enforcement
  3) Confound Detector: automatic confounding variable discovery

Target: Causal Reasoning 85% → 95% (surpass Q* 88%)

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks33c import KS33c, Claim
    from .stage_store import StageStore
    from .multi_step_intervention import enumerate_intervention_chains
    from .temporal_causal_graph import check_temporal_consistency, detect_reverse_causation
    from .confound_detector import detect_confounders
    from .causal_verifier import build_causal_dag, check_dag_structure
except ImportError:
    from ks33c import KS33c, Claim
    from stage_store import StageStore
    from multi_step_intervention import enumerate_intervention_chains
    from temporal_causal_graph import check_temporal_consistency, detect_reverse_causation
    from confound_detector import detect_confounders
    from causal_verifier import build_causal_dag, check_dag_structure


# ── Deep Causal Reasoning Constants ──
TEMPORAL_MAJOR_PENALTY = -0.15
TEMPORAL_MINOR_PENALTY = -0.05
TEMPORAL_CONSISTENT_BONUS = 0.05
REVERSE_CAUSATION_PENALTY = -0.1
REVERSE_CAUSATION_MAX = 3
MULTI_STEP_ROBUST_THRESHOLD = 0.8
MULTI_STEP_FRAGILE_THRESHOLD = 0.2
MULTI_STEP_ROBUST_BONUS = 0.08
MULTI_STEP_FRAGILE_PENALTY = -0.08
HIGH_CONFOUND_PENALTY = -0.15
MODERATE_CONFOUND_PENALTY = -0.08
NO_CONFOUND_BONUS = 0.05
TOTAL_ADJ_FLOOR = -0.3
TOTAL_ADJ_CEILING = 0.2
MAX_CHAIN_LENGTH = 2
MAX_ROOTS = 2
MAX_LEAVES = 2
ERROR_TRUNCATE = 80
DEFAULT_CONFIDENCE = 0.5


class KS34a(KS33c):
    """KS33c + Deep Causal Reasoning.

    Adds three causal verification capabilities on top of the KS33c
    33-solver pipeline:

    1. **Temporal Consistency**: Checks that causal claims respect
       temporal ordering (causes precede effects).
    2. **Multi-Step Intervention**: Tests robustness of causal chains
       via do-calculus intervention sequences.
    3. **Confound Detection**: Identifies potential confounding variables
       that could invalidate causal claims.

    Design: Youta Hilono
    """

    VERSION = "KS34a"
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        """Verify a claim with deep causal reasoning enhancement.

        Extends KS33c.verify() with three additional causal checks:
        temporal consistency, multi-step intervention, and confound detection.
        Adjusts confidence based on causal analysis results.

        Args:
            claim: Claim text or Claim object to verify.
            store: StageStore for intermediate results (created if None).
            skip_s28: Whether to skip S28 LLM solver.
            **kwargs: Passed to parent verify().

        Returns:
            dict with standard verification result plus 'deep_causal' section.
        """
        if store is None:
            store = StageStore()
        
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        # PDF results pass through
        if isinstance(result, dict) and "results" in result:
            return result
        
        # Try to get chain data from store for DAG construction
        chain_data = None
        # Priority: KS31e_R2_L3 has A06 chain decomposition with steps + dependency_edges
        for candidate in ["KS31e_R2_L3", "A_analogy_solvers"]:
            if store.has_stage(candidate):
                try:
                    d = store.read(candidate)
                    if isinstance(d, dict) and d.get("steps"):
                        chain_data = d
                        break
                except Exception:
                    pass
        
        # Fallback: scan for any stage with chain-like data
        if not chain_data:
            for stage_name in store.list_stages():
                if "chain" in stage_name.lower() or "causal" in stage_name.lower():
                    try:
                        d = store.read(stage_name)
                        if isinstance(d, dict) and d.get("steps"):
                            chain_data = d
                            break
                    except Exception:
                        pass
        
        # Fallback: build chain from claim text directly using A06
        if not chain_data:
            try:
                from .analogy_solvers import a06_chain_decompose
            except ImportError:
                try:
                    from analogy_solvers import a06_chain_decompose
                except ImportError:
                    a06_chain_decompose = None
            
            if a06_chain_decompose and isinstance(claim, str):
                try:
                    chain_data = a06_chain_decompose(claim)
                except Exception:
                    pass
            elif a06_chain_decompose and hasattr(claim, 'text'):
                try:
                    chain_data = a06_chain_decompose(claim.text)
                except Exception:
                    pass
        
        if not chain_data or (isinstance(chain_data, dict) and not chain_data.get("steps")):
            result["deep_causal"] = {"status": "no_causal_structure", "enhancements": []}
            result["version"] = self.VERSION
            return result
        
        # Build DAG
        try:
            G = build_causal_dag(chain_data)
        except Exception:
            result["deep_causal"] = {"status": "dag_build_failed", "enhancements": []}
            result["version"] = self.VERSION
            return result
        
        if G.number_of_nodes() < 2:
            result["deep_causal"] = {"status": "insufficient_nodes", "enhancements": []}
            result["version"] = self.VERSION
            return result
        
        enhancements = []
        penalties = []
        bonuses = []
        
        # ── 1) Temporal Consistency ──
        try:
            temporal = check_temporal_consistency(G)
            enhancements.append({"type": "temporal", "verdict": temporal["temporal_verdict"],
                                 "violations": temporal["violation_count"]})
            
            if temporal["temporal_verdict"] == "MAJOR_VIOLATIONS":
                penalties.append(("temporal_violations", TEMPORAL_MAJOR_PENALTY))
            elif temporal["temporal_verdict"] == "MINOR_VIOLATIONS":
                penalties.append(("temporal_minor", TEMPORAL_MINOR_PENALTY))
            else:
                bonuses.append(("temporal_consistent", TEMPORAL_CONSISTENT_BONUS))

            reverse = detect_reverse_causation(G)
            if reverse:
                enhancements.append({"type": "reverse_causation", "count": len(reverse)})
                penalties.append(("reverse_causation", REVERSE_CAUSATION_PENALTY * min(len(reverse), REVERSE_CAUSATION_MAX)))
        except Exception as e:
            enhancements.append({"type": "temporal", "error": str(e)[:ERROR_TRUNCATE]})

        # ── 2) Multi-Step Intervention ──
        try:
            structure = check_dag_structure(G)
            roots = structure.get("roots", [])[:MAX_ROOTS]
            leaves = structure.get("leaves", [])[:MAX_LEAVES]

            for root in roots:
                for leaf in leaves:
                    if root != leaf:
                        chains = enumerate_intervention_chains(G, root, leaf, max_chain_length=MAX_CHAIN_LENGTH)
                        if chains:
                            persists = sum(1 for c in chains if c.get("effect_persists"))
                            robustness = persists / max(len(chains), 1)
                            enhancements.append({
                                "type": "multi_step", "chains": len(chains),
                                "persists": persists, "robustness": round(robustness, 3),
                            })
                            if robustness >= MULTI_STEP_ROBUST_THRESHOLD:
                                bonuses.append(("robust_multi_step", MULTI_STEP_ROBUST_BONUS))
                            elif robustness <= MULTI_STEP_FRAGILE_THRESHOLD:
                                penalties.append(("fragile_causation", MULTI_STEP_FRAGILE_PENALTY))
        except Exception as e:
            enhancements.append({"type": "multi_step", "error": str(e)[:ERROR_TRUNCATE]})
        
        # ── 3) Confound Detection ──
        try:
            for u, v, data in G.edges(data=True):
                if data.get("causal"):
                    conf = detect_confounders(G, u, v)
                    enhancements.append({
                        "type": "confounders", "count": conf["confounder_count"],
                        "assessment": conf["assessment"], "risk": conf["confounding_risk"],
                    })
                    if conf["assessment"] == "HIGH_CONFOUNDING_RISK":
                        penalties.append(("high_confounding", HIGH_CONFOUND_PENALTY))
                    elif conf["assessment"] == "MODERATE_CONFOUNDING_RISK":
                        penalties.append(("moderate_confounding", MODERATE_CONFOUND_PENALTY))
                    elif conf["assessment"] == "NO_CONFOUNDERS_DETECTED":
                        bonuses.append(("no_confounders", NO_CONFOUND_BONUS))
                    break  # Primary edge only
        except Exception as e:
            enhancements.append({"type": "confounders", "error": str(e)[:ERROR_TRUNCATE]})

        # ── Apply adjustments ──
        adj = sum(p[1] for p in penalties) + sum(b[1] for b in bonuses)
        adj = max(TOTAL_ADJ_FLOOR, min(TOTAL_ADJ_CEILING, adj))

        old_conf = result.get("confidence", DEFAULT_CONFIDENCE)
        new_conf = max(0.0, min(1.0, old_conf + adj))
        
        result["deep_causal"] = {
            "status": "enhanced",
            "enhancements": enhancements,
            "penalties": penalties,
            "bonuses": bonuses,
            "adjustment": round(adj, 4),
        }
        result["confidence"] = round(new_conf, 4)
        result["version"] = self.VERSION
        
        try:
            store.write("ks34a_deep_causal", {
                "enhancements": len(enhancements),
                "adjustment": adj,
            })
        except (ValueError, Exception):
            pass  # Stage already written or store error
        
        return result
