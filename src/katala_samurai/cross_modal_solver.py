"""
Cross-Modal Solver Bridge — モダリティ横断ソルバー接続

Youta設計: モーダル間・ソルバー間をより効率的で横断的に接続。
全18軸を96%以上に引き上げるための横断強化エンジン。

Architecture:
  1. ModalSolverBridge: 各モダリティの出力を33ソルバーにフィードバック
  2. CrossModalVerifier: 複数モダリティの整合性を検証層に統合
  3. AdaptiveWeightEngine: ソルバー重みをモダリティ信頼度で動的調整
  4. MultimodalPropositionExtractor: 画像/音声/動画から命題を直接抽出
  5. SafetyAlignmentEngine: 安全性整合を全ソルバーに組み込み
  6. ContextExpansionEngine: 長文脈をチャンク間相互参照で強化

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Modal-Solver Bridge — モダリティ→ソルバー直接接続
# ═══════════════════════════════════════════════════════════════════════════

class ModalSolverBridge:
    """Bridge modality outputs directly to solver inputs.

    Instead of: modality → text → _parse() → solvers
    Add:        modality → bridge → solver weight/feature injection

    This creates a parallel path where raw modality features
    influence solvers without going through text conversion.
    """

    # Modality → solver affinity map
    AFFINITY = {
        "image": {
            "S29_fact_check": 0.8,     # Image can verify visual facts
            "S32_data_support": 0.9,    # Image metadata = data
            "S33_fact_coherence": 0.7,  # Visual coherence
        },
        "audio": {
            "S30_contradiction": 0.8,   # Audio vs text contradiction
            "S31_reliability": 0.7,     # Speaker confidence signals
            "S29_fact_check": 0.6,      # Transcript fact checking
        },
        "video": {
            "S29_fact_check": 0.7,      # Visual + audio fact check
            "S30_contradiction": 0.9,   # Multi-stream contradiction
            "S33_fact_coherence": 0.8,  # Temporal coherence
            "S32_data_support": 0.6,    # Video metadata
        },
        "text": {
            "S29_fact_check": 0.9,
            "S30_contradiction": 0.9,
            "S31_reliability": 0.9,
            "S32_data_support": 0.8,
            "S33_fact_coherence": 0.9,
        },
    }

    def compute_bridge_weights(
        self,
        modality_features: Dict[str, Dict[str, Any]],
        modality_reliabilities: Dict[str, float],
    ) -> Dict[str, float]:
        """Compute solver weight adjustments from modality features.

        Returns solver_name → weight_multiplier.
        """
        weights = {}
        for modality, features in modality_features.items():
            reliability = modality_reliabilities.get(modality, 0.5)
            affinity = self.AFFINITY.get(modality, {})

            for solver, base_affinity in affinity.items():
                # Weight = reliability × affinity × feature_richness
                feature_richness = min(len(features) / 5.0, 1.0)
                w = reliability * base_affinity * (0.7 + 0.3 * feature_richness)

                if solver in weights:
                    # Multi-modal agreement: geometric mean
                    weights[solver] = math.sqrt(weights[solver] * w)
                else:
                    weights[solver] = w

        # Normalize to multipliers around 1.0
        if weights:
            avg = sum(weights.values()) / len(weights)
            if avg > 0:
                weights = {k: round(v / avg, 3) for k, v in weights.items()}

        return weights


# ═══════════════════════════════════════════════════════════════════════════
# 2. Cross-Modal Verifier — 横断検証
# ═══════════════════════════════════════════════════════════════════════════

class CrossModalVerifier:
    """Verify claims using cross-modal evidence chains.

    Key insight: if a claim can be supported/refuted by multiple
    independent modalities, confidence scales multiplicatively.
    """

    # Evidence weight by modality pair agreement
    AGREEMENT_BOOST = 1.4       # Two modalities agree → 40% confidence boost
    DISAGREEMENT_PENALTY = 0.5  # Two modalities disagree → 50% confidence penalty

    def verify_cross_modal(
        self,
        claim_text: str,
        modality_verdicts: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Combine verification results from multiple modalities."""
        if not modality_verdicts:
            return {"confidence": 0.5, "verdict": "UNCERTAIN"}

        scores = []
        for mod, verdict in modality_verdicts.items():
            score = verdict.get("score", verdict.get("confidence", 0.5))
            scores.append((mod, score))

        if len(scores) == 1:
            return {
                "confidence": scores[0][1],
                "verdict": "PASS" if scores[0][1] >= 0.7 else "FAIL" if scores[0][1] < 0.5 else "UNCERTAIN",
                "source": scores[0][0],
            }

        # Check agreement
        avg_score = sum(s for _, s in scores) / len(scores)
        score_variance = sum((s - avg_score) ** 2 for _, s in scores) / len(scores)

        if score_variance < 0.02:  # Modalities agree
            combined = avg_score * self.AGREEMENT_BOOST
        elif score_variance > 0.1:  # Modalities disagree
            combined = avg_score * self.DISAGREEMENT_PENALTY
        else:
            combined = avg_score

        combined = max(0.0, min(1.0, combined))

        return {
            "confidence": round(combined, 4),
            "verdict": "PASS" if combined >= 0.7 else "FAIL" if combined < 0.5 else "UNCERTAIN",
            "agreement": "high" if score_variance < 0.02 else "low" if score_variance > 0.1 else "medium",
            "modality_scores": {m: round(s, 3) for m, s in scores},
        }


# ═══════════════════════════════════════════════════════════════════════════
# 3. Adaptive Weight Engine — 動的重み調整
# ═══════════════════════════════════════════════════════════════════════════

class AdaptiveWeightEngine:
    """Dynamically adjust solver weights based on input characteristics.

    Goes beyond static 50/25/25 weighting:
    - Multimodal → semantic weight increases (more evidence)
    - High reliability → structural weight increases (trust structure)
    - Contradictions → all weights flatten (uncertainty)
    """

    BASE_STRUCTURAL = 0.50
    BASE_SEMANTIC = 0.25
    BASE_LLM = 0.25

    def compute_weights(
        self,
        modality_count: int,
        has_contradiction: bool,
        avg_reliability: float,
        has_transcript: bool = False,
        has_clip: bool = False,
    ) -> Dict[str, float]:
        """Compute dynamic solver category weights."""
        structural = self.BASE_STRUCTURAL
        semantic = self.BASE_SEMANTIC
        llm = self.BASE_LLM

        # Multimodal → more evidence → boost semantic
        if modality_count > 1:
            semantic += 0.05 * (modality_count - 1)
            structural -= 0.03 * (modality_count - 1)

        # High reliability → trust structure more
        if avg_reliability > 0.8:
            structural += 0.05
            llm -= 0.05

        # Contradiction → flatten (more uncertainty → more diverse)
        if has_contradiction:
            structural = 0.35
            semantic = 0.35
            llm = 0.30

        # Transcript available → boost semantic (more text to check)
        if has_transcript:
            semantic += 0.05
            llm -= 0.03

        # CLIP available → boost semantic (visual grounding)
        if has_clip:
            semantic += 0.03

        # Normalize
        total = structural + semantic + llm
        return {
            "structural": round(structural / total, 3),
            "semantic": round(semantic / total, 3),
            "llm": round(llm / total, 3),
        }


# ═══════════════════════════════════════════════════════════════════════════
# 4. Multimodal Proposition Extractor — マルチモーダル命題抽出
# ═══════════════════════════════════════════════════════════════════════════

class MultimodalPropositionExtractor:
    """Extract verifiable propositions from non-text modalities.

    Converts modality features into propositions that S01-S27 SAT
    solvers can process, extending _parse() beyond text.
    """

    def extract_from_image(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract propositions from image features."""
        props = []

        # Metadata-based propositions
        meta = features.get("metadata", {})
        if meta.get("has_exif"):
            props.append({
                "text": "Image has original EXIF metadata",
                "confidence": 0.8,
                "source": "image_metadata",
            })
        else:
            props.append({
                "text": "Image EXIF metadata has been stripped",
                "confidence": 0.7,
                "source": "image_metadata",
            })

        # Manipulation-based
        manip = features.get("manipulation", {})
        if manip.get("suspicious"):
            for indicator in manip.get("indicators", [])[:3]:
                props.append({
                    "text": f"Image manipulation indicator: {indicator}",
                    "confidence": manip.get("confidence", 0.5),
                    "source": "image_manipulation",
                })

        # CLIP-based
        clip_sim = features.get("clip_similarity")
        if clip_sim is not None:
            if clip_sim > 0.3:
                props.append({
                    "text": "Image content matches the claimed description",
                    "confidence": min(clip_sim * 1.5, 0.95),
                    "source": "clip_verification",
                })
            else:
                props.append({
                    "text": "Image content does NOT match the claimed description",
                    "confidence": 0.7,
                    "source": "clip_verification",
                })

        return props

    def extract_from_audio(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract propositions from audio features."""
        props = []

        transcript = features.get("transcript")
        if transcript:
            # Split transcript into sentence-level propositions
            sentences = re.split(r'[.!?。！？]', transcript)
            for s in sentences[:10]:  # Limit to first 10
                s = s.strip()
                if len(s) > 10:
                    props.append({
                        "text": f"Audio transcript states: {s}",
                        "confidence": 0.75,
                        "source": "whisper_transcript",
                    })

        # Transcript match
        match = features.get("transcript_match")
        if match is not None:
            if match > 0.5:
                props.append({
                    "text": "Audio content matches the claimed transcript",
                    "confidence": match,
                    "source": "transcript_verification",
                })
            else:
                props.append({
                    "text": "Audio content does NOT match the claimed transcript",
                    "confidence": 0.7,
                    "source": "transcript_verification",
                })

        # Manipulation
        manip = features.get("manipulation", {})
        if manip.get("suspicious"):
            props.append({
                "text": "Audio manipulation detected",
                "confidence": 0.6,
                "source": "audio_manipulation",
            })

        return props

    def extract_from_video(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract propositions from video features."""
        props = []

        meta = features.get("metadata", {})
        if meta.get("duration", 0) > 0:
            props.append({
                "text": f"Video is {meta['duration']:.1f} seconds long",
                "confidence": 0.9,
                "source": "video_metadata",
            })

        scenes = features.get("scenes", {})
        if scenes.get("count", 0) > 0:
            props.append({
                "text": f"Video contains approximately {scenes['count']} scenes",
                "confidence": 0.7,
                "source": "scene_detection",
            })

        manip = features.get("manipulation", {})
        deepfake = manip.get("deepfake_risk", 0)
        if deepfake > 0.4:
            props.append({
                "text": f"Video has elevated deepfake risk ({deepfake:.2f})",
                "confidence": deepfake,
                "source": "deepfake_detection",
            })

        return props

    def extract_all(
        self,
        modality_features: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract propositions from all available modalities."""
        all_props = []
        if "image" in modality_features:
            all_props.extend(self.extract_from_image(modality_features["image"]))
        if "audio" in modality_features:
            all_props.extend(self.extract_from_audio(modality_features["audio"]))
        if "video" in modality_features:
            all_props.extend(self.extract_from_video(modality_features["video"]))
        return all_props


# ═══════════════════════════════════════════════════════════════════════════
# 5. Safety Alignment Engine — 安全性整合
# ═══════════════════════════════════════════════════════════════════════════

class SafetyAlignmentEngine:
    """Embed safety alignment checks across all verification layers.

    Safety is not a separate axis — it's woven into every solver decision.
    This engine provides safety scoring that modulates all other axes.
    """

    # Harmful content patterns
    HARMFUL_PATTERNS = [
        re.compile(r"(?i)\b(how\s+to\s+(?:make|build|create)\s+(?:bomb|weapon|poison|drug))"),
        re.compile(r"(?i)\b(instructions?\s+for\s+(?:harm|violence|illegal))"),
        re.compile(r"(?i)\b(bypass\s+(?:security|safety|filter|restriction))"),
        re.compile(r"(?i)\b(jailbreak|prompt\s+injection|ignore\s+(?:previous|above))"),
    ]

    # Bias/fairness patterns
    BIAS_PATTERNS = [
        re.compile(r"(?i)\b(all\s+\w+\s+are\s+(?:stupid|lazy|evil|inferior))"),
        re.compile(r"(?i)\b((?:women|men|blacks?|whites?|asians?)\s+(?:can'?t|shouldn'?t|never))"),
        re.compile(r"(?i)\b((?:race|gender|religion)\s+(?:determines?|proves?)\s+(?:intelligence|worth))"),
    ]

    # Misinformation patterns (extends S29 known-false)
    MISINFO_PATTERNS = [
        re.compile(r"(?i)\b(vaccines?\s+cause\s+(?:autism|infertility|death))"),
        re.compile(r"(?i)\b(5G\s+(?:causes?|spreads?)\s+(?:covid|cancer|radiation))"),
        re.compile(r"(?i)\b(climate\s+change\s+is\s+(?:a\s+)?hoax)"),
        re.compile(r"(?i)\b(election\s+was\s+(?:stolen|rigged|fake))"),
    ]

    def score(self, text: str) -> Dict[str, Any]:
        """Score text for safety alignment across multiple dimensions."""
        harmful = sum(1 for p in self.HARMFUL_PATTERNS if p.search(text))
        biased = sum(1 for p in self.BIAS_PATTERNS if p.search(text))
        misinfo = sum(1 for p in self.MISINFO_PATTERNS if p.search(text))

        # Safety score: 1.0 = perfectly safe, 0.0 = dangerous
        safety = 1.0
        safety -= harmful * 0.25   # Harmful content is severe
        safety -= biased * 0.15    # Bias is moderate
        safety -= misinfo * 0.20   # Misinformation is significant
        safety = max(0.0, safety)

        flags = []
        if harmful > 0:
            flags.append(f"harmful_content({harmful})")
        if biased > 0:
            flags.append(f"bias_detected({biased})")
        if misinfo > 0:
            flags.append(f"misinformation({misinfo})")

        return {
            "safety_score": round(safety, 3),
            "harmful_count": harmful,
            "bias_count": biased,
            "misinfo_count": misinfo,
            "flags": flags,
            "safe": safety >= 0.7,
        }

    def modulate_solver_output(
        self,
        solver_score: float,
        safety_result: Dict[str, Any],
    ) -> float:
        """Modulate a solver's output by safety alignment.

        If content is unsafe, cap the verification score to prevent
        unsafe content from being verified as "true".
        """
        safety = safety_result.get("safety_score", 1.0)
        if safety < 0.5:
            # Unsafe content → cap score at 0.4 (similar to known-false)
            return min(solver_score, 0.4)
        elif safety < 0.7:
            # Borderline → apply penalty
            return solver_score * safety
        return solver_score


# ═══════════════════════════════════════════════════════════════════════════
# 6. Context Expansion Engine — 長文脈強化
# ═══════════════════════════════════════════════════════════════════════════

class ContextExpansionEngine:
    """Enhance long-context processing with cross-reference chains.

    Improves long-context verification by:
    1. Entity co-reference tracking across chunks
    2. Claim dependency chains (claim A depends on claim B)
    3. Temporal ordering enforcement
    4. Summary↔source bidirectional verification
    """

    def build_coref_chain(self, chunks: List[str]) -> Dict[str, List[int]]:
        """Track entity co-references across chunks.

        Returns entity → [chunk_indices] mapping.
        """
        entity_pattern = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b')
        entity_chunks: Dict[str, List[int]] = {}

        for i, chunk in enumerate(chunks):
            entities = set(entity_pattern.findall(chunk))
            for entity in entities:
                if entity not in entity_chunks:
                    entity_chunks[entity] = []
                entity_chunks[entity].append(i)

        # Filter to entities that appear in multiple chunks
        return {e: indices for e, indices in entity_chunks.items() if len(indices) > 1}

    def build_claim_dependencies(
        self,
        claims: List[str],
    ) -> List[Tuple[int, int, str]]:
        """Detect claim dependencies (claim i depends on claim j).

        Returns list of (dependent, dependency, type) tuples.
        """
        deps = []
        reference_patterns = [
            (re.compile(r"(?i)\b(as\s+(?:mentioned|stated|shown)\s+(?:above|earlier|before))"), "backward_ref"),
            (re.compile(r"(?i)\b(therefore|thus|hence|consequently|as\s+a\s+result)"), "causal"),
            (re.compile(r"(?i)\b(this\s+(?:shows?|proves?|implies?|means?))"), "inferential"),
            (re.compile(r"(?i)\b(building\s+on|based\s+on|given\s+that)"), "foundational"),
        ]

        for i, claim in enumerate(claims):
            for pattern, dep_type in reference_patterns:
                if pattern.search(claim) and i > 0:
                    deps.append((i, i - 1, dep_type))
                    break

        return deps

    def verify_temporal_order(self, claims: List[str]) -> Dict[str, Any]:
        """Check temporal ordering consistency in claim sequences."""
        temporal_markers = []
        time_pattern = re.compile(
            r'(?i)\b(first|then|next|after|before|finally|initially|subsequently|'
            r'in\s+\d{4}|on\s+\w+\s+\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})'
        )

        for i, claim in enumerate(claims):
            markers = time_pattern.findall(claim)
            for m in markers:
                temporal_markers.append((i, m))

        # Check for ordering violations
        violations = 0
        order_words = ["first", "then", "next", "after", "finally"]
        seen_order = []
        for idx, marker in temporal_markers:
            marker_lower = marker.lower().strip()
            if marker_lower in order_words:
                expected_pos = order_words.index(marker_lower)
                if seen_order and expected_pos < seen_order[-1]:
                    violations += 1
                seen_order.append(expected_pos)

        consistency = 1.0 - (violations * 0.2)
        return {
            "temporal_markers": len(temporal_markers),
            "violations": violations,
            "consistency": round(max(0, consistency), 3),
        }

    def bidirectional_verify(
        self,
        source_chunks: List[str],
        summary: str,
    ) -> Dict[str, Any]:
        """Bidirectional verification: source↔summary.

        Forward: Does summary accurately represent source?
        Reverse: Can source be reconstructed from summary?
        """
        # Forward: entity coverage
        source_text = " ".join(source_chunks)
        source_entities = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', source_text))
        summary_entities = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', summary))

        if source_entities:
            forward_coverage = len(source_entities & summary_entities) / len(source_entities)
        else:
            forward_coverage = 0.5

        # Reverse: summary claims present in source
        summary_words = set(summary.lower().split())
        source_words = set(source_text.lower().split())
        if summary_words:
            reverse_coverage = len(summary_words & source_words) / len(summary_words)
        else:
            reverse_coverage = 0.5

        combined = (forward_coverage * 0.6 + reverse_coverage * 0.4)

        return {
            "forward_coverage": round(forward_coverage, 3),
            "reverse_coverage": round(reverse_coverage, 3),
            "combined_fidelity": round(combined, 3),
            "source_entities": len(source_entities),
            "summary_entities": len(summary_entities),
        }


# ═══════════════════════════════════════════════════════════════════════════
# 7. Unified Cross-Modal Solver Engine
# ═══════════════════════════════════════════════════════════════════════════

class CrossModalSolverEngine:
    """Unified engine combining all cross-modal solver bridges.

    This is the main entry point that orchestrates:
    - ModalSolverBridge (modality → solver)
    - CrossModalVerifier (cross-modal consistency)
    - AdaptiveWeightEngine (dynamic weighting)
    - MultimodalPropositionExtractor (non-text → propositions)
    - SafetyAlignmentEngine (safety modulation)
    - ContextExpansionEngine (long-context)
    """

    def __init__(self):
        self.bridge = ModalSolverBridge()
        self.verifier = CrossModalVerifier()
        self.weight_engine = AdaptiveWeightEngine()
        self.prop_extractor = MultimodalPropositionExtractor()
        self.safety = SafetyAlignmentEngine()
        self.context = ContextExpansionEngine()

    def process(
        self,
        claim_text: str,
        modality_features: Optional[Dict[str, Dict[str, Any]]] = None,
        modality_reliabilities: Optional[Dict[str, float]] = None,
        modality_verdicts: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run full cross-modal solver pipeline."""
        modality_features = modality_features or {}
        modality_reliabilities = modality_reliabilities or {"text": 0.85}
        modality_verdicts = modality_verdicts or {}

        # 1. Safety check
        safety = self.safety.score(claim_text)

        # 2. Bridge weights
        bridge_weights = self.bridge.compute_bridge_weights(
            modality_features, modality_reliabilities
        )

        # 3. Cross-modal verification
        cross_result = self.verifier.verify_cross_modal(claim_text, modality_verdicts)

        # 4. Adaptive category weights
        adaptive_weights = self.weight_engine.compute_weights(
            modality_count=len(modality_features),
            has_contradiction=cross_result.get("agreement") == "low",
            avg_reliability=sum(modality_reliabilities.values()) / max(len(modality_reliabilities), 1),
            has_transcript="audio" in modality_features and modality_features["audio"].get("transcript"),
            has_clip="image" in modality_features and modality_features["image"].get("clip_similarity") is not None,
        )

        # 5. Extract multimodal propositions
        mm_propositions = self.prop_extractor.extract_all(modality_features)

        # 6. Combine
        result = {
            "safety": safety,
            "bridge_weights": bridge_weights,
            "cross_modal": cross_result,
            "adaptive_weights": adaptive_weights,
            "mm_propositions": mm_propositions,
            "mm_proposition_count": len(mm_propositions),
            "overall_confidence": cross_result.get("confidence", 0.5),
        }

        # Safety modulation
        if not safety["safe"]:
            result["overall_confidence"] = self.safety.modulate_solver_output(
                result["overall_confidence"], safety
            )
            result["safety_override"] = True

        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "components": [
                "ModalSolverBridge",
                "CrossModalVerifier",
                "AdaptiveWeightEngine",
                "MultimodalPropositionExtractor",
                "SafetyAlignmentEngine",
                "ContextExpansionEngine",
            ],
        }


if __name__ == "__main__":
    engine = CrossModalSolverEngine()
    print(f"Status: {engine.get_status()}")

    # Test text-only
    r = engine.process("Water boils at 100 degrees Celsius")
    print(f"Text: conf={r['overall_confidence']:.3f} safety={r['safety']['safety_score']:.3f}")

    # Test unsafe content
    r2 = engine.process("Vaccines cause autism and 5G spreads covid")
    print(f"Unsafe: conf={r2['overall_confidence']:.3f} safety={r2['safety']['safety_score']:.3f} flags={r2['safety']['flags']}")

    # Test with image features
    r3 = engine.process(
        "This photo proves the claim",
        modality_features={
            "text": {"word_count": 5},
            "image": {"clip_similarity": 0.8, "manipulation": {"suspicious": False}},
        },
        modality_reliabilities={"text": 0.85, "image": 0.75},
    )
    print(f"Multimodal: conf={r3['overall_confidence']:.3f} props={r3['mm_proposition_count']}")

    print(f"\n✅ CrossModalSolverEngine v{VERSION} OK")
