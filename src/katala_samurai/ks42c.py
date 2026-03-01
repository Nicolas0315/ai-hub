"""
KS42c — Katala Samurai 42c: Semantic Parse + Rust Acceleration.

Extends KS42b with:
  1. LLM-based semantic proposition extraction (semantic_parse.py)
     - Replaces boolean pattern-matching _parse() with genuine meaning extraction
     - 3-tier: Ollama (local) → Gemini (API) → Rust heuristic fallback
     - Solvers receive atomic propositions + logical relations + entities

  2. Full Rust acceleration (43 functions in ks_accel)
     - Semantic cache: fingerprint (2.3μs), ngram Jaccard (2.5μs)
     - Solver orthogonality: gram_schmidt, cosine matrix
     - Temporal decay: 0.11μs/call, 14-domain half-life model
     - Adversarial: text_structural_diff (1.3μs), number extraction
     - Cross-domain: concept bridge similarity (Rayon batch)
     - Heuristic parse: batch (300 texts = 0.8ms)

MRO: KS42c → KS42b → KS42a → KS41b → KS41a → KS40b → ... → KS31e

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import sys as _sys
import os as _os
import time
from typing import Any, Dict, Optional

_dir = _os.path.dirname(_os.path.abspath(__file__))
_src = _os.path.dirname(_dir)
for _p in [_dir, _src]:
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

try:
    from .ks42b import KS42b
    from .ks29 import Claim
    from .stage_store import StageStore
except ImportError:
    from ks42b import KS42b
    from ks29 import Claim
    from stage_store import StageStore

VERSION = "KS42c-v2"

# ── Rust availability check ──
_HAS_RUST = False
_RUST_FUNCTION_COUNT = 0
try:
    import ks_accel
    _HAS_RUST = True
    _RUST_FUNCTION_COUNT = len([x for x in dir(ks_accel) if not x.startswith('_')])
except ImportError:
    pass

# ── Semantic parse availability ──
_HAS_SEMANTIC = False
try:
    from katala_samurai.semantic_parse import semantic_parse, SemanticPropositions
    _HAS_SEMANTIC = True
except ImportError:
    try:
        from semantic_parse import semantic_parse, SemanticPropositions
        _HAS_SEMANTIC = True
    except ImportError:
        pass

# ── New engines for remaining 3-axis gap (v2) ──
_HAS_EPISODIC = False
try:
    from katala_samurai.episodic_memory import EpisodicMemoryEngine
    _HAS_EPISODIC = True
except ImportError:
    try:
        from episodic_memory import EpisodicMemoryEngine
        _HAS_EPISODIC = True
    except ImportError:
        pass

_HAS_EXPERT = False
try:
    from katala_samurai.expert_reasoning import ExpertReasoningEngine
    _HAS_EXPERT = True
except ImportError:
    try:
        from expert_reasoning import ExpertReasoningEngine
        _HAS_EXPERT = True
    except ImportError:
        pass

_HAS_CROSS_DOMAIN = False
try:
    from katala_samurai.cross_domain_transfer import CrossDomainTransferEngine
    _HAS_CROSS_DOMAIN = True
except ImportError:
    try:
        from cross_domain_transfer import CrossDomainTransferEngine
        _HAS_CROSS_DOMAIN = True
    except ImportError:
        pass


class KS42c(KS42b):
    """KS42b + Semantic Parse + Rust Acceleration.

    Key improvements over KS42b:
    - Claim._parse() now extracts MEANING via LLM, not surface patterns
    - 13 new Rust functions (total 43) accelerate hot paths
    - Claim.semantic field carries full proposition/relation/entity data
    - Rust bridges auto-fallback to Python if ks_accel unavailable

    Usage:
        ks = KS42c()
        result = ks.verify(claim)
        # result now includes semantic richness metrics
    """

    VERSION = VERSION

    # Acceleration thresholds
    RUST_ACCELERATION_EXPECTED = 43  # Expected Rust function count
    SEMANTIC_CONFIDENCE_THRESHOLD = 0.3  # Min LLM confidence to trust

    def __init__(self, **kwargs):
        """Initialize KS42c.

        Args:
            **kwargs: Passed to KS42b.__init__().
        """
        super().__init__(**kwargs)
        self._rust_available = _HAS_RUST
        self._semantic_available = _HAS_SEMANTIC
        self._rust_function_count = _RUST_FUNCTION_COUNT

        # v2: New engines for remaining 3-axis gap
        self._episodic = EpisodicMemoryEngine() if _HAS_EPISODIC else None
        self._expert = ExpertReasoningEngine() if _HAS_EXPERT else None
        self._cross_domain = CrossDomainTransferEngine() if _HAS_CROSS_DOMAIN else None

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        """Verify claim with semantic enrichment and Rust acceleration.

        Extends KS42b.verify() with:
        1. Semantic proposition data from LLM extraction
        2. Acceleration metrics (Rust function availability)
        3. Semantic confidence gating

        Args:
            claim: Claim object or text string.
            store: StageStore for intermediate results.
            skip_s28: Skip S28 solver (default True).
            **kwargs: HTLF and other params.

        Returns:
            dict with KS42b results + 'semantic_enrichment' + 'acceleration'.
        """
        if store is None:
            store = StageStore()

        start = time.time()
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        base_time = time.time() - start

        if not isinstance(result, dict):
            return result

        # Semantic enrichment
        semantic_info = self._extract_semantic_info(claim)
        result["semantic_enrichment"] = semantic_info

        # Acceleration report
        result["acceleration"] = {
            "rust_available": self._rust_available,
            "rust_functions": self._rust_function_count,
            "rust_expected": self.RUST_ACCELERATION_EXPECTED,
            "semantic_source": semantic_info.get("source", "none"),
            "semantic_propositions": semantic_info.get("prop_count", 0),
        }

        # v2: Expert reasoning assessment (PhD専門推論 +3%)
        if self._expert:
            claim_text = claim.text if hasattr(claim, 'text') else str(claim)
            evidence = claim.evidence if hasattr(claim, 'evidence') else []
            expert_result = self._expert.verify(claim_text, evidence=evidence)
            result["expert_reasoning"] = expert_result

            # Boost final score if expert reasoning finds strong argument structure
            if expert_result["overall_score"] >= 0.60:
                current_score = result.get("final_score", 0)
                if isinstance(current_score, (int, float)):
                    # Expert reasoning boost: up to +5% for strong arguments
                    boost = (expert_result["overall_score"] - 0.5) * 0.10
                    result["final_score"] = round(min(current_score + boost, 1.0), 4)

        # v2: Cross-domain transfer assessment (ドメイン横断 +1%)
        if self._cross_domain:
            claim_text = claim.text if hasattr(claim, 'text') else str(claim)
            cross_result = self._cross_domain.score(claim_text)
            result["cross_domain"] = cross_result

            # Boost if genuine cross-domain content detected
            if cross_result.get("cross_domain") and cross_result["overall_score"] >= 0.50:
                current_score = result.get("final_score", 0)
                if isinstance(current_score, (int, float)):
                    boost = (cross_result["overall_score"] - 0.4) * 0.05
                    result["final_score"] = round(min(current_score + boost, 1.0), 4)

        # v2: Record episode for episodic memory (長期Agent +3%)
        if self._episodic:
            claim_text = claim.text if hasattr(claim, 'text') else str(claim)
            verdict = result.get("verdict", "UNVERIFIED")
            score = result.get("final_score", 0.5)
            domain = result.get("expert_reasoning", {}).get("domain", "general")

            self._episodic.record_episode(
                context={
                    "claim_text_hash": claim_text[:50],
                    "domain": domain,
                    "has_evidence": bool(getattr(claim, 'evidence', [])),
                },
                action=f"verify_{verdict.lower()}",
                action_type="verify",
                outcome="success" if verdict == "VERIFIED" else "failure",
                outcome_score=score if isinstance(score, float) else 0.5,
                domain=domain,
                strategy_used="ks42c_full",
            )
            result["episodic_memory"] = {
                "total_episodes": len(self._episodic.episodes),
                "total_schemas": len(self._episodic.schemas),
            }

        result["version"] = self.VERSION
        return result

    def _extract_semantic_info(self, claim) -> Dict[str, Any]:
        """Extract semantic proposition data from claim.

        Returns dict with proposition count, relation count, domain,
        entities, and source (ollama/gemini/heuristic/none).
        """
        # Check if claim already has semantic data (from _parse)
        if hasattr(claim, 'semantic') and claim.semantic is not None:
            sem = claim.semantic
            return {
                "source": sem.source,
                "prop_count": sem.prop_count,
                "relation_count": sem.relation_count,
                "entities": sem.entities[:5],  # Top 5
                "domain": sem.domain,
                "confidence": sem.confidence,
                "extraction_time_ms": sem.extraction_time_ms,
                "propositions": [
                    {"id": p.get("id", "?"), "type": p.get("type", "?")}
                    for p in sem.propositions[:5]
                ],
                "relations": [
                    {"from": r.get("from", "?"), "to": r.get("to", "?"),
                     "type": r.get("type", "?")}
                    for r in sem.relations[:5]
                ],
            }

        # Try extracting if semantic_parse available
        if self._semantic_available:
            try:
                claim_text = claim.text if hasattr(claim, 'text') else str(claim)
                sem = semantic_parse(claim_text)
                return {
                    "source": sem.source,
                    "prop_count": sem.prop_count,
                    "relation_count": sem.relation_count,
                    "entities": sem.entities[:5],
                    "domain": sem.domain,
                    "confidence": sem.confidence,
                    "extraction_time_ms": sem.extraction_time_ms,
                }
            except Exception:
                pass

        return {"source": "none", "prop_count": 0, "confidence": 0.0}

    def rust_status(self) -> Dict[str, Any]:
        """Report Rust acceleration status.

        Returns:
            dict with availability, function count, and per-module status.
        """
        base = super().rust_status() if hasattr(super(), 'rust_status') else {}
        base.update({
            "version": self.VERSION,
            "rust_available": self._rust_available,
            "rust_function_count": self._rust_function_count,
            "rust_expected": self.RUST_ACCELERATION_EXPECTED,
            "semantic_parse_available": self._semantic_available,
            "modules_accelerated": [
                "semantic_cache (fingerprint, jaccard)",
                "temporal_context (decay)",
                "adversarial_boost (structural_diff, numbers)",
                "semantic_parse (heuristic_extract)",
                "solver_orthogonality (cosine_matrix)",
                "parse_bridge (parse_propositions, batch)",
            ] if self._rust_available else [],
        })
        return base

    def get_status(self) -> Dict[str, Any]:
        """Extended status including semantic and Rust info."""
        base = super().get_status() if hasattr(super(), 'get_status') else {}
        base["version"] = self.VERSION
        base["rust"] = self.rust_status()
        base["semantic_parse"] = {
            "available": self._semantic_available,
            "tiers": ["ollama (local)", "gemini (api)", "heuristic (rust/python)"],
        }
        # v2: New engines
        base["episodic_memory"] = {
            "available": self._episodic is not None,
            "episodes": len(self._episodic.episodes) if self._episodic else 0,
            "schemas": len(self._episodic.schemas) if self._episodic else 0,
        }
        base["expert_reasoning"] = {"available": self._expert is not None}
        base["cross_domain_transfer"] = {
            "available": self._cross_domain is not None,
            "known_bridges": len(self._cross_domain.bridges) if self._cross_domain else 0,
        }
        return base
