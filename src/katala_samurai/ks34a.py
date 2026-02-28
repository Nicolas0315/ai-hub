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


class KS34a(KS33c):
    """KS33c + Deep Causal Reasoning."""
    
    VERSION = "KS34a"
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
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
                penalties.append(("temporal_violations", -0.15))
            elif temporal["temporal_verdict"] == "MINOR_VIOLATIONS":
                penalties.append(("temporal_minor", -0.05))
            else:
                bonuses.append(("temporal_consistent", 0.05))
            
            reverse = detect_reverse_causation(G)
            if reverse:
                enhancements.append({"type": "reverse_causation", "count": len(reverse)})
                penalties.append(("reverse_causation", -0.1 * min(len(reverse), 3)))
        except Exception as e:
            enhancements.append({"type": "temporal", "error": str(e)[:80]})
        
        # ── 2) Multi-Step Intervention ──
        try:
            structure = check_dag_structure(G)
            roots = structure.get("roots", [])[:2]
            leaves = structure.get("leaves", [])[:2]
            
            for root in roots:
                for leaf in leaves:
                    if root != leaf:
                        chains = enumerate_intervention_chains(G, root, leaf, max_chain_length=2)
                        if chains:
                            persists = sum(1 for c in chains if c.get("effect_persists"))
                            robustness = persists / max(len(chains), 1)
                            enhancements.append({
                                "type": "multi_step", "chains": len(chains),
                                "persists": persists, "robustness": round(robustness, 3),
                            })
                            if robustness >= 0.8:
                                bonuses.append(("robust_multi_step", 0.08))
                            elif robustness <= 0.2:
                                penalties.append(("fragile_causation", -0.08))
        except Exception as e:
            enhancements.append({"type": "multi_step", "error": str(e)[:80]})
        
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
                        penalties.append(("high_confounding", -0.15))
                    elif conf["assessment"] == "MODERATE_CONFOUNDING_RISK":
                        penalties.append(("moderate_confounding", -0.08))
                    elif conf["assessment"] == "NO_CONFOUNDERS_DETECTED":
                        bonuses.append(("no_confounders", 0.05))
                    break  # Primary edge only
        except Exception as e:
            enhancements.append({"type": "confounders", "error": str(e)[:80]})
        
        # ── Apply adjustments ──
        adj = sum(p[1] for p in penalties) + sum(b[1] for b in bonuses)
        adj = max(-0.3, min(0.2, adj))
        
        old_conf = result.get("confidence", 0.5)
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
