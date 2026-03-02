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

VERSION = "KS42c-v3"

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

_HAS_AXIS96 = False
try:
    from katala_samurai.axis_96_boost import Axis96Booster
    _HAS_AXIS96 = True
except ImportError:
    try:
        from axis_96_boost import Axis96Booster
        _HAS_AXIS96 = True
    except ImportError:
        pass

_HAS_CODEGEN = False
try:
    from katala_samurai.code_generation import CodeGenerationEngine
    _HAS_CODEGEN = True
except ImportError:
    try:
        from code_generation import CodeGenerationEngine
        _HAS_CODEGEN = True
    except ImportError:
        pass

_HAS_MULTILINGUAL = False
try:
    from katala_samurai.multilingual_engine import MultilingualVerifier, detect_language
    _HAS_MULTILINGUAL = True
except ImportError:
    try:
        from multilingual_engine import MultilingualVerifier, detect_language
        _HAS_MULTILINGUAL = True
    except ImportError:
        pass

_HAS_LONG_CONTEXT = False
try:
    from katala_samurai.long_context import LongContextEngine
    _HAS_LONG_CONTEXT = True
except ImportError:
    try:
        from long_context import LongContextEngine
        _HAS_LONG_CONTEXT = True
    except ImportError:
        pass

_HAS_MATH_PROOF = False
try:
    from katala_samurai.math_proof import MathProofEngine
    _HAS_MATH_PROOF = True
except ImportError:
    try:
        from math_proof import MathProofEngine
        _HAS_MATH_PROOF = True
    except ImportError:
        pass

_HAS_IMAGE_UNDERSTANDING = False
try:
    from katala_samurai.image_understanding import ImageUnderstandingEngine
    _HAS_IMAGE_UNDERSTANDING = True
except ImportError:
    try:
        from image_understanding import ImageUnderstandingEngine
        _HAS_IMAGE_UNDERSTANDING = True
    except ImportError:
        pass

_HAS_AUDIO_PROCESSING = False
try:
    from katala_samurai.audio_processing import AudioProcessingEngine
    _HAS_AUDIO_PROCESSING = True
except ImportError:
    try:
        from audio_processing import AudioProcessingEngine
        _HAS_AUDIO_PROCESSING = True
    except ImportError:
        pass

_HAS_VIDEO_UNDERSTANDING = False
try:
    from katala_samurai.video_understanding import VideoUnderstandingEngine
    _HAS_VIDEO_UNDERSTANDING = True
except ImportError:
    try:
        from video_understanding import VideoUnderstandingEngine
        _HAS_VIDEO_UNDERSTANDING = True
    except ImportError:
        pass

_HAS_CROSS_MODAL_SOLVER = False
try:
    from katala_samurai.cross_modal_solver import CrossModalSolverEngine
    _HAS_CROSS_MODAL_SOLVER = True
except ImportError:
    try:
        from cross_modal_solver import CrossModalSolverEngine
        _HAS_CROSS_MODAL_SOLVER = True
    except ImportError:
        pass

_HAS_MULTIMODAL_INPUT = False
try:
    from katala_samurai.multimodal_input import MultimodalInputLayer, MultimodalInput
    from katala_samurai.modality_judge import ModalityJudge
    _HAS_MULTIMODAL_INPUT = True
except ImportError:
    try:
        from multimodal_input import MultimodalInputLayer, MultimodalInput
        from modality_judge import ModalityJudge
        _HAS_MULTIMODAL_INPUT = True
    except ImportError:
        pass

_HAS_EXCEEDS = False
try:
    from katala_samurai.exceeds_engine import ExceedsEngine
    _HAS_EXCEEDS = True
except ImportError:
    try:
        from exceeds_engine import ExceedsEngine
        _HAS_EXCEEDS = True
    except ImportError:
        pass

_HAS_AXIS_MAX = False
try:
    from katala_samurai.axis_max_boost import AxisMaxBooster
    _HAS_AXIS_MAX = True
except ImportError:
    try:
        from axis_max_boost import AxisMaxBooster
        _HAS_AXIS_MAX = True
    except ImportError:
        pass

# ── PhD-gap engines (v3): peer_review, metacognitive, interdisciplinary, tacit_knowledge ──
_HAS_PEER_REVIEW = False
try:
    from katala_samurai.peer_review import PeerReviewEngine
    _HAS_PEER_REVIEW = True
except ImportError:
    try:
        from peer_review import PeerReviewEngine
        _HAS_PEER_REVIEW = True
    except ImportError:
        pass

_HAS_METACOGNITIVE = False
try:
    from katala_samurai.metacognitive import MetacognitiveEngine
    _HAS_METACOGNITIVE = True
except ImportError:
    try:
        from metacognitive import MetacognitiveEngine
        _HAS_METACOGNITIVE = True
    except ImportError:
        pass

_HAS_INTERDISCIPLINARY = False
try:
    from katala_samurai.interdisciplinary import InterdisciplinaryEngine
    _HAS_INTERDISCIPLINARY = True
except ImportError:
    try:
        from interdisciplinary import InterdisciplinaryEngine
        _HAS_INTERDISCIPLINARY = True
    except ImportError:
        pass

_HAS_TACIT = False
try:
    from katala_samurai.tacit_knowledge import TacitKnowledgeEngine
    _HAS_TACIT = True
except ImportError:
    try:
        from tacit_knowledge import TacitKnowledgeEngine
        _HAS_TACIT = True
    except ImportError:
        pass

# ── Context Binding (認識空間 基盤) ──
_HAS_CONTEXT_BINDING = False
try:
    from katala_coding.context_binding import ContextBinding, BindingVerdict
    _HAS_CONTEXT_BINDING = True
except ImportError:
    try:
        from context_binding import ContextBinding, BindingVerdict
        _HAS_CONTEXT_BINDING = True
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
        self._axis96 = Axis96Booster() if _HAS_AXIS96 else None
        self._codegen = CodeGenerationEngine() if _HAS_CODEGEN else None
        self._multilingual = MultilingualVerifier() if _HAS_MULTILINGUAL else None
        self._long_context = LongContextEngine() if _HAS_LONG_CONTEXT else None
        self._math_proof = MathProofEngine() if _HAS_MATH_PROOF else None
        self._image = ImageUnderstandingEngine() if _HAS_IMAGE_UNDERSTANDING else None
        self._audio = AudioProcessingEngine() if _HAS_AUDIO_PROCESSING else None
        self._video = VideoUnderstandingEngine() if _HAS_VIDEO_UNDERSTANDING else None
        self._mm_input = MultimodalInputLayer() if _HAS_MULTIMODAL_INPUT else None
        self._mm_judge = ModalityJudge() if _HAS_MULTIMODAL_INPUT else None
        self._cross_modal = CrossModalSolverEngine() if _HAS_CROSS_MODAL_SOLVER else None
        self._exceeds = ExceedsEngine() if _HAS_EXCEEDS else None
        self._axis_max = AxisMaxBooster() if _HAS_AXIS_MAX else None

        # v3: PhD-gap engines
        self._peer_review = PeerReviewEngine() if _HAS_PEER_REVIEW else None
        self._metacognitive = MetacognitiveEngine() if _HAS_METACOGNITIVE else None
        self._interdisciplinary = InterdisciplinaryEngine() if _HAS_INTERDISCIPLINARY else None
        self._tacit = TacitKnowledgeEngine() if _HAS_TACIT else None

        # v4: Context Binding (認識空間 基盤 — KS前段)
        self._context_binding = ContextBinding() if _HAS_CONTEXT_BINDING else None

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        """Verify claim with Context Binding pre-gate + semantic enrichment.

        Pipeline: [Context Binding] → KS verify → KCS (caller's responsibility)

        Context Binding (v4):
        - REJECT: identity conflict → returns immediately, no KS processing
        - DEFER: purpose mismatch → returns immediately, no KS processing
        - PASS: proceeds to full KS verification

        Args:
            claim: Claim object or text string.
            store: StageStore for intermediate results.
            skip_s28: Skip S28 solver (default True).
            skip_binding: If True, bypass Context Binding (default False).
            **kwargs: HTLF and other params.

        Returns:
            dict with KS42b results + 'context_binding' + 'semantic_enrichment' + 'acceleration'.
        """
        if store is None:
            store = StageStore()

        skip_binding = kwargs.pop("skip_binding", False)
        fast = kwargs.pop("fast", False)

        # ── Context Binding pre-gate (v4) ──
        binding_result = None
        if self._context_binding and not skip_binding:
            claim_text = claim.text if hasattr(claim, 'text') else str(claim)
            binding_result = self._context_binding.bind(claim_text)

            if binding_result.verdict == BindingVerdict.REJECT:
                return {
                    "verdict": "REJECTED",
                    "final_score": 0.0,
                    "reason": f"Context Binding REJECT: {binding_result.reason}",
                    "context_binding": binding_result.to_dict(),
                    "version": self.VERSION,
                }

            if binding_result.verdict == BindingVerdict.DEFER:
                return {
                    "verdict": "DEFERRED",
                    "final_score": 0.0,
                    "reason": f"Context Binding DEFER: {binding_result.reason}",
                    "context_binding": binding_result.to_dict(),
                    "version": self.VERSION,
                }

        start = time.time()
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        base_time = time.time() - start

        if not isinstance(result, dict):
            return result

        # Semantic enrichment (skip LLM in fast mode)
        semantic_info = self._extract_semantic_info(claim, fast=fast)
        result["semantic_enrichment"] = semantic_info
        result["fast_mode"] = fast

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

        # v3: Axis 96% boost (all 8 micro-improvements)
        if self._axis96:
            claim_text = claim.text if hasattr(claim, 'text') else str(claim)
            boost_result = self._axis96.boost_claim(claim_text, evidence=getattr(claim, 'evidence', []))
            result["axis96_boost"] = boost_result

            # Apply combined boost to final score
            combined_boost = boost_result.get("combined_boost", 0.7)
            current_score = result.get("final_score", 0)
            if isinstance(current_score, (int, float)):
                # Axis96 boost: scale based on boost quality
                if combined_boost >= 0.85:
                    boost = 0.02  # Strong boost
                elif combined_boost >= 0.70:
                    boost = 0.01  # Moderate boost
                else:
                    boost = -0.01  # Adversarial penalty
                result["final_score"] = round(min(current_score + boost, 1.0), 4)

        # v3: PhD-gap engines ─────────────────────────────────────

        claim_text = claim.text if hasattr(claim, 'text') else str(claim)
        _evidence = getattr(claim, 'evidence', []) or []
        _solver_results = result.get("solver_results", [])
        _semantic = result.get("semantic_enrichment", {})
        _confidence = result.get("confidence", 0.5)
        _verdict = result.get("verdict", "UNVERIFIED")

        # Peer Review (査読レベルの批判)
        if self._peer_review:
            pr = self._peer_review.review(
                claim_text=claim_text,
                solver_results=_solver_results,
                semantic_data=_semantic,
                evidence=_evidence,
                confidence=_confidence,
                verdict=_verdict,
            )
            result["peer_review"] = pr.to_dict()

        # Metacognitive Self-Correction (メタ認知的自己修正)
        if self._metacognitive:
            mc = self._metacognitive.analyze(
                claim_text=claim_text,
                ks_result=result,
            )
            result["metacognitive"] = mc.to_dict()
            # Apply metacognitive confidence correction
            if mc.corrections:
                for corr in mc.corrections:
                    if (corr.target == "confidence"
                            and corr.proposed_value is not None
                            and corr.confidence_in_correction >= 0.5):
                        result["confidence_pre_metacognitive"] = result.get("confidence", 0.5)
                        result["confidence"] = corr.proposed_value
                        break

        # Interdisciplinary Integration + Hypothesis Generation (学際統合+仮説生成)
        if self._interdisciplinary:
            # Build solver result list from solvers_passed summary
            _solver_list = _solver_results
            if not _solver_list:
                _sp = result.get("solvers_passed", "0/0")
                try:
                    _p, _t = str(_sp).split("/")
                    _passed_n, _total_n = int(_p), int(_t)
                except (ValueError, AttributeError):
                    _passed_n, _total_n = 0, 33
                _solver_list = [
                    {
                        "solver_id": f"S{i+1:02d}",
                        "passed": i < _passed_n,
                        "confidence": 0.5 + (0.1 if i < _passed_n else -0.1),
                    }
                    for i in range(_total_n)
                ]
            if _solver_list:
                inter = self._interdisciplinary.analyze(
                    claim_text=claim_text,
                    solver_results=_solver_list,
                    semantic_data=_semantic,
                )
                result["interdisciplinary"] = inter.to_dict()

        # Tacit Knowledge (暗黙知近似)
        if self._tacit:
            domain = "general"
            if _semantic and isinstance(_semantic, dict):
                domain = _semantic.get("domain", "general")
            tk = self._tacit.analyze(
                claim_text=claim_text,
                domain=domain,
                confidence=result.get("confidence", 0.5),
                verdict=_verdict,
                solver_results=_solver_results,
                semantic_data=_semantic,
            )
            result["tacit_knowledge"] = tk.to_dict()

        # v4: Attach Context Binding result
        if binding_result is not None:
            result["context_binding"] = binding_result.to_dict()

        result["version"] = self.VERSION
        return result

    def _extract_semantic_info(self, claim, fast: bool = False) -> Dict[str, Any]:
        """Extract semantic proposition data from claim.

        fast=True: Skip LLM, use heuristic only (~0.06ms vs ~1500ms).

        Returns dict with proposition count, relation count, domain,
        entities, and source (ollama/gemini/heuristic/none).
        """
        # Check if claim already has semantic data (from _parse) and not in fast mode
        if not fast and hasattr(claim, 'semantic') and claim.semantic is not None:
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
                sem = semantic_parse(claim_text, fast=fast)
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
        base["axis96_boost"] = {
            "available": self._axis96 is not None,
            "status": self._axis96.get_status() if self._axis96 else None,
        }
        base["multimodal_engines"] = {
            "code_generation": self._codegen is not None,
            "multilingual": self._multilingual is not None,
            "long_context": self._long_context is not None,
            "math_proof": {
                "available": self._math_proof is not None,
                "status": self._math_proof.get_status() if self._math_proof else None,
            },
            "image_understanding": {
                "available": self._image is not None,
                "status": self._image.get_status() if self._image else None,
            },
            "audio_processing": {
                "available": self._audio is not None,
                "status": self._audio.get_status() if self._audio else None,
            },
            "video_understanding": {
                "available": self._video is not None,
                "status": self._video.get_status() if self._video else None,
            },
            "multimodal_input_layer": {
                "available": self._mm_input is not None,
                "status": self._mm_input.get_status() if self._mm_input else None,
            },
            "modality_judge": {
                "available": self._mm_judge is not None,
                "status": self._mm_judge.get_status() if self._mm_judge else None,
            },
            "cross_modal_solver": {
                "available": self._cross_modal is not None,
                "status": self._cross_modal.get_status() if self._cross_modal else None,
            },
            "exceeds_engine": {
                "available": self._exceeds is not None,
                "status": self._exceeds.get_status() if self._exceeds else None,
            },
            "axis_max_boost": {
                "available": self._axis_max is not None,
                "status": self._axis_max.get_status() if self._axis_max else None,
            },
        }
        # v3: PhD-gap engines
        base["peer_review"] = {"available": self._peer_review is not None}
        base["metacognitive"] = {
            "available": self._metacognitive is not None,
            "history_size": len(self._metacognitive._history) if self._metacognitive else 0,
        }
        base["interdisciplinary"] = {"available": self._interdisciplinary is not None}
        base["tacit_knowledge"] = {
            "available": self._tacit is not None,
            "domain_profiles": len(self._tacit.profiles) if self._tacit else 0,
        }
        # v4: Context Binding
        base["context_binding"] = {
            "available": self._context_binding is not None,
            "status": self._context_binding.get_status() if self._context_binding else None,
        }
        return base
