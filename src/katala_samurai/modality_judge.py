"""
Modality Judge Layer — 判断層

Youta設計: _parse()層と⓪入力層の間に位置し、両者と相補的に関連付ける。

役割:
  1. どのモダリティが有効か判定
  2. モダリティ間の整合性チェック (クロスモーダル矛盾検出)
  3. 統合テキスト表現の生成 (重み付け合成)
  4. ソルバー重み調整ヒント生成
  5. _parse()への追加特徴注入

Architecture:
  ⓪ MultimodalInputLayer
    ↓
  [THIS] ModalityJudge (判断層)
    ├─ 有効モダリティ判定
    ├─ クロスモーダル矛盾検出
    ├─ ソルバー重みヒント生成
    └─ _parse()追加特徴注入
    ↓
  _parse() 35+α特徴抽出

相補的関連付け:
  - 判断層 ↔ _parse(): 画像に数値 → S32(データ支持)重み↑
  - 判断層 ↔ S29: EXIFが改ざん → S29信頼度↓
  - 判断層 → ソルバー: 音声入力 → 音響分析関連重み↑
  - _parse() → 判断層: テキスト特徴 → モダリティ信頼度調整

Design: Youta Hilono (architecture) + Shirokuma (implementation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"

try:
    from katala_samurai.multimodal_input import (
        MultimodalOutput, ModalityResult, Modality
    )
except ImportError:
    from multimodal_input import MultimodalOutput, ModalityResult, Modality


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

# Modality reliability priors
MODALITY_RELIABILITY = {
    "text": 0.85,       # Text is generally reliable (what we're good at)
    "image": 0.70,      # Images can be manipulated
    "audio": 0.75,      # Audio is moderately reliable
    "video": 0.65,      # Video most easily manipulated
}

# Solver weight adjustment magnitudes
WEIGHT_BOOST = 1.3      # Boost relevant solver weight by 30%
WEIGHT_REDUCE = 0.7     # Reduce irrelevant solver weight by 30%

# Cross-modal contradiction thresholds
TEXT_IMAGE_CONTRADICTION_THRESHOLD = 0.2
TEXT_AUDIO_CONTRADICTION_THRESHOLD = 0.3
AUDIO_VIDEO_MISMATCH_THRESHOLD = 0.4


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ModalityJudgment:
    """Judgment about a single modality's usefulness."""
    modality: str
    effective: bool = True
    reliability: float = 0.5
    reason: str = ""


@dataclass
class CrossModalCheck:
    """Result of cross-modal consistency check."""
    pair: Tuple[str, str] = ("", "")
    consistent: bool = True
    alignment_score: float = 0.5
    contradiction_type: str = ""     # "" | "content" | "metadata" | "temporal"
    details: str = ""


@dataclass
class JudgmentResult:
    """Full output from the judgment layer."""
    # Modality judgments
    modality_judgments: Dict[str, ModalityJudgment] = field(default_factory=dict)

    # Cross-modal checks
    cross_modal_checks: List[CrossModalCheck] = field(default_factory=list)
    has_contradiction: bool = False

    # Unified text (possibly reweighted)
    unified_text: str = ""

    # Solver weight hints: solver_name → weight_multiplier
    solver_weight_hints: Dict[str, float] = field(default_factory=dict)

    # Additional features for _parse()
    parse_extra_features: Dict[str, Any] = field(default_factory=dict)

    # Overall confidence
    overall_confidence: float = 0.5

    version: str = VERSION


# ═══════════════════════════════════════════════════════════════════════════
# Modality Judge
# ═══════════════════════════════════════════════════════════════════════════

class ModalityJudge:
    """Judgment layer between multimodal input and _parse().

    Decides:
    - Which modalities are effective for this verification task
    - Whether modalities are consistent with each other
    - How to adjust solver weights based on available modalities
    - What extra features to inject into _parse()
    """

    def judge(self, mm_output: MultimodalOutput) -> JudgmentResult:
        """Run judgment on multimodal input layer output."""
        result = JudgmentResult()

        # 1. Judge each modality's effectiveness
        for name, mr in mm_output.modality_results.items():
            judgment = self._judge_modality(name, mr, mm_output)
            result.modality_judgments[name] = judgment

        # 2. Cross-modal consistency checks
        result.cross_modal_checks = self._check_cross_modal(mm_output)
        result.has_contradiction = any(not c.consistent for c in result.cross_modal_checks)

        # 3. Generate solver weight hints
        result.solver_weight_hints = self._compute_solver_hints(
            mm_output, result.modality_judgments, result.has_contradiction
        )

        # 4. Generate extra features for _parse()
        result.parse_extra_features = self._generate_parse_features(
            mm_output, result.modality_judgments, result.cross_modal_checks
        )

        # 5. Build unified text with confidence weighting
        result.unified_text = self._build_weighted_text(
            mm_output, result.modality_judgments
        )

        # 6. Overall confidence
        result.overall_confidence = self._compute_overall_confidence(
            result.modality_judgments, result.has_contradiction
        )

        return result

    # ───────────────────────────────────────────────────────
    # 1. Modality effectiveness judgment
    # ───────────────────────────────────────────────────────

    def _judge_modality(
        self,
        name: str,
        mr: ModalityResult,
        mm_output: MultimodalOutput,
    ) -> ModalityJudgment:
        """Judge whether a modality is effective for verification."""
        base_reliability = MODALITY_RELIABILITY.get(name, 0.5)

        # Adjust based on modality-specific features
        reliability = base_reliability * mr.confidence

        # Penalty for warnings
        warning_penalty = len(mr.warnings) * 0.1
        reliability = max(0.1, reliability - warning_penalty)

        # Image-specific: manipulation detected → reliability drops
        if name == "image":
            manip = mr.features.get("manipulation", {})
            if manip.get("suspicious"):
                reliability *= 0.5
                return ModalityJudgment(
                    modality=name, effective=True,
                    reliability=reliability,
                    reason="Image manipulation suspected — reduced reliability"
                )

        # Audio-specific: no transcript → limited use
        if name == "audio":
            if not mr.features.get("transcript"):
                reliability *= 0.6
                return ModalityJudgment(
                    modality=name, effective=True,
                    reliability=reliability,
                    reason="No transcript available — spectral features only"
                )

        # Video-specific: deepfake risk + generation artifacts (v2.0)
        if name == "video":
            manip = mr.features.get("manipulation", {})
            deepfake = manip.get("deepfake_risk", 0)
            gen_artifacts = mr.features.get("generation_artifacts", {})
            is_generated = gen_artifacts.get("is_likely_generated", False)
            gen_confidence = gen_artifacts.get("generation_confidence", 0.0)
            has_rich_metadata = (
                mr.features.get("metadata", {}).get("duration", 0) > 0
                and mr.features.get("metadata", {}).get("width", 0) > 0
                and mr.features.get("metadata", {}).get("fps", 0) > 0
            )

            # AI-generated video → lower reliability
            if is_generated and gen_confidence > 0.5:
                reliability *= max(0.3, 1.0 - gen_confidence * 0.6)
                return ModalityJudgment(
                    modality=name, effective=True,
                    reliability=round(reliability, 3),
                    reason=f"AI-generated video (confidence={gen_confidence:.2f}) — reduced reliability"
                )

            # Deepfake risk
            if deepfake > 0.5:
                reliability *= 0.4
                return ModalityJudgment(
                    modality=name, effective=True,
                    reliability=round(reliability, 3),
                    reason=f"Deepfake risk {deepfake:.2f} — heavily discounted"
                )

            # Rich metadata → reliability boost
            if has_rich_metadata:
                reliability = min(reliability * 1.15, 0.85)
                return ModalityJudgment(
                    modality=name, effective=True,
                    reliability=round(reliability, 3),
                    reason="Rich metadata available — reliability boosted"
                )

        effective = reliability > 0.2
        return ModalityJudgment(
            modality=name, effective=effective,
            reliability=round(reliability, 3),
            reason="Normal" if effective else "Too unreliable"
        )

    # ───────────────────────────────────────────────────────
    # 2. Cross-modal consistency
    # ───────────────────────────────────────────────────────

    def _check_cross_modal(self, mm_output: MultimodalOutput) -> List[CrossModalCheck]:
        """Check consistency between modality pairs."""
        checks = []
        cross = mm_output.cross_modal_features

        # Text ↔ Image
        if "text" in mm_output.modality_results and "image" in mm_output.modality_results:
            alignment = cross.get("text_image_alignment")
            contradiction = cross.get("text_image_contradiction", False)
            checks.append(CrossModalCheck(
                pair=("text", "image"),
                consistent=not contradiction,
                alignment_score=alignment if alignment is not None else 0.5,
                contradiction_type="content" if contradiction else "",
                details="CLIP similarity below threshold" if contradiction else "Aligned",
            ))

        # Text ↔ Audio
        if "text" in mm_output.modality_results and "audio" in mm_output.modality_results:
            alignment = cross.get("text_audio_alignment")
            contradiction = cross.get("text_audio_contradiction", False)
            checks.append(CrossModalCheck(
                pair=("text", "audio"),
                consistent=not contradiction,
                alignment_score=alignment if alignment is not None else 0.5,
                contradiction_type="content" if contradiction else "",
                details="Transcript mismatch" if contradiction else "Aligned",
            ))

        # Image ↔ Video (if both present, check metadata consistency)
        if "image" in mm_output.modality_results and "video" in mm_output.modality_results:
            img_features = mm_output.modality_results["image"].features
            vid_features = mm_output.modality_results["video"].features

            img_manip = img_features.get("manipulation", {}).get("suspicious", False)
            vid_manip = vid_features.get("manipulation", {}).get("suspicious", False)

            # If one is suspicious but not the other → potential mismatch
            consistent = not (img_manip != vid_manip)
            checks.append(CrossModalCheck(
                pair=("image", "video"),
                consistent=consistent,
                alignment_score=0.8 if consistent else 0.3,
                contradiction_type="metadata" if not consistent else "",
                details="Manipulation status mismatch" if not consistent else "Consistent",
            ))

        # Audio ↔ Video (audio track should match video claims)
        if "audio" in mm_output.modality_results and "video" in mm_output.modality_results:
            audio_features = mm_output.modality_results["audio"].features
            vid_features = mm_output.modality_results["video"].features

            audio_dur = audio_features.get("metadata", {}).get("duration", 0)
            vid_dur = vid_features.get("metadata", {}).get("duration", 0)

            if audio_dur > 0 and vid_dur > 0:
                dur_ratio = min(audio_dur, vid_dur) / max(audio_dur, vid_dur)
                consistent = dur_ratio > AUDIO_VIDEO_MISMATCH_THRESHOLD
                checks.append(CrossModalCheck(
                    pair=("audio", "video"),
                    consistent=consistent,
                    alignment_score=round(dur_ratio, 3),
                    contradiction_type="temporal" if not consistent else "",
                    details=f"Duration ratio {dur_ratio:.2f}" + (
                        " — significant mismatch" if not consistent else ""),
                ))

        return checks

    # ───────────────────────────────────────────────────────
    # 3. Solver weight hints
    # ───────────────────────────────────────────────────────

    def _compute_solver_hints(
        self,
        mm_output: MultimodalOutput,
        judgments: Dict[str, ModalityJudgment],
        has_contradiction: bool,
    ) -> Dict[str, float]:
        """Generate solver weight adjustment hints.

        These hints tell the solver layer to boost/reduce specific solvers
        based on available modalities.
        """
        hints = {}

        # If image present with data → boost S32 (data support)
        if "image" in judgments:
            img_features = mm_output.modality_results.get("image", ModalityResult(Modality.IMAGE))
            if img_features.features.get("metadata", {}).get("has_exif"):
                hints["S32_data_support"] = WEIGHT_BOOST  # EXIF = structured data
            if img_features.features.get("manipulation", {}).get("suspicious"):
                hints["S29_fact_check"] = WEIGHT_REDUCE   # Manipulated image → S29 less reliable

        # If audio with transcript → boost S31 (reliability signals)
        if "audio" in judgments:
            audio_features = mm_output.modality_results.get("audio", ModalityResult(Modality.AUDIO))
            if audio_features.features.get("transcript"):
                hints["S31_reliability"] = WEIGHT_BOOST   # Transcript adds reliability data
                hints["S30_contradiction"] = WEIGHT_BOOST  # Can check text vs transcript

        # If video present → boost manipulation-related solvers
        if "video" in judgments:
            vid_features = mm_output.modality_results.get("video", ModalityResult(Modality.VIDEO))
            deepfake = vid_features.features.get("manipulation", {}).get("deepfake_risk", 0)
            gen_artifacts = vid_features.features.get("generation_artifacts", {})
            is_generated = gen_artifacts.get("is_likely_generated", False)

            if deepfake > 0.3:
                hints["S29_fact_check"] = WEIGHT_BOOST     # Need strong fact checking
                hints["S33_fact_coherence"] = WEIGHT_BOOST  # Check coherence

            # v2.0: AI-generated video → boost reliability analysis
            if is_generated:
                hints["S31_reliability"] = WEIGHT_REDUCE   # Generated content = lower reliability
                hints["S30_contradiction"] = WEIGHT_BOOST  # Check for contradictions
                hints["overall_skepticism"] = hints.get("overall_skepticism", 1.0) * 1.15

        # Cross-modal contradiction → boost contradiction detector
        if has_contradiction:
            hints["S30_contradiction"] = WEIGHT_BOOST * 1.2  # Extra boost
            hints["overall_skepticism"] = 1.2                 # General skepticism boost

        # Multimodal input → boost S28 LLM (can reason about multiple sources)
        if len(mm_output.modalities_present) > 1:
            hints["S28_llm_consensus"] = WEIGHT_BOOST

        return hints

    # ───────────────────────────────────────────────────────
    # 4. Extra features for _parse()
    # ───────────────────────────────────────────────────────

    def _generate_parse_features(
        self,
        mm_output: MultimodalOutput,
        judgments: Dict[str, ModalityJudgment],
        cross_checks: List[CrossModalCheck],
    ) -> Dict[str, Any]:
        """Generate additional features that _parse() can use.

        These extend the standard 35 text features with multimodal
        information, enabling _parse() to extract richer propositions.
        """
        features = {
            # Modality presence flags
            "mm_modality_count": len(mm_output.modalities_present),
            "mm_has_image": "image" in mm_output.modalities_present,
            "mm_has_audio": "audio" in mm_output.modalities_present,
            "mm_has_video": "video" in mm_output.modalities_present,
            "mm_is_multimodal": len(mm_output.modalities_present) > 1,
        }

        # Image features for _parse()
        if "image" in mm_output.modality_results:
            img = mm_output.modality_results["image"]
            features["mm_image_manipulated"] = img.features.get(
                "manipulation", {}).get("suspicious", False)
            features["mm_image_has_exif"] = img.features.get(
                "metadata", {}).get("has_exif", False)
            clip_sim = img.features.get("clip_similarity")
            if clip_sim is not None:
                features["mm_clip_similarity"] = clip_sim

        # Audio features for _parse()
        if "audio" in mm_output.modality_results:
            audio = mm_output.modality_results["audio"]
            features["mm_has_transcript"] = bool(audio.features.get("transcript"))
            features["mm_audio_language"] = audio.features.get("language", "unknown")
            match = audio.features.get("transcript_match")
            if match is not None:
                features["mm_transcript_match"] = match

        # Video features for _parse()
        if "video" in mm_output.modality_results:
            vid = mm_output.modality_results["video"]
            features["mm_video_duration"] = vid.features.get(
                "metadata", {}).get("duration", 0)
            features["mm_deepfake_risk"] = vid.features.get(
                "manipulation", {}).get("deepfake_risk", 0)
            features["mm_scene_count"] = vid.features.get(
                "scenes", {}).get("count", 0)
            # v2.0: generation artifact features
            gen = vid.features.get("generation_artifacts", {})
            features["mm_video_is_generated"] = gen.get("is_likely_generated", False)
            features["mm_video_generation_confidence"] = gen.get("generation_confidence", 0.0)
            features["mm_video_flicker"] = gen.get("flicker_score", 0.0)
            # v2.0: optical flow
            flow = vid.features.get("optical_flow", {})
            features["mm_video_motion_type"] = flow.get("motion_type", "unknown")
            features["mm_video_motion_consistency"] = flow.get("motion_consistency", 0.0)

        # Cross-modal features
        features["mm_has_contradiction"] = any(
            not c.consistent for c in cross_checks)
        features["mm_contradiction_count"] = sum(
            1 for c in cross_checks if not c.consistent)

        # Reliability summary
        reliabilities = [j.reliability for j in judgments.values() if j.effective]
        if reliabilities:
            features["mm_avg_reliability"] = round(
                sum(reliabilities) / len(reliabilities), 3)
            features["mm_min_reliability"] = round(min(reliabilities), 3)

        return features

    # ───────────────────────────────────────────────────────
    # 5. Weighted unified text
    # ───────────────────────────────────────────────────────

    def _build_weighted_text(
        self,
        mm_output: MultimodalOutput,
        judgments: Dict[str, ModalityJudgment],
    ) -> str:
        """Build unified text with modality reliability annotations."""
        parts = []
        for name in ["text", "image", "audio", "video"]:
            mr = mm_output.modality_results.get(name)
            j = judgments.get(name)
            if mr and mr.text_representation and j:
                if j.effective:
                    reliability_tag = f"[reliability={j.reliability:.2f}]"
                    parts.append(f"{reliability_tag} {mr.text_representation}")
                else:
                    parts.append(f"[UNRELIABLE] {mr.text_representation}")
        return " ".join(parts)

    # ───────────────────────────────────────────────────────
    # 6. Overall confidence
    # ───────────────────────────────────────────────────────

    def _compute_overall_confidence(
        self,
        judgments: Dict[str, ModalityJudgment],
        has_contradiction: bool,
    ) -> float:
        """Compute overall confidence from modality judgments."""
        if not judgments:
            return 0.5

        reliabilities = [j.reliability for j in judgments.values()]
        avg = sum(reliabilities) / len(reliabilities)

        # Contradiction penalty
        if has_contradiction:
            avg *= 0.7

        # Bonus for multimodal agreement
        if len(judgments) > 1 and not has_contradiction:
            avg = min(avg * 1.1, 0.95)

        return round(avg, 3)

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "modality_reliability_priors": MODALITY_RELIABILITY,
            "weight_boost": WEIGHT_BOOST,
            "weight_reduce": WEIGHT_REDUCE,
        }


if __name__ == "__main__":
    from multimodal_input import MultimodalInputLayer, MultimodalInput

    layer = MultimodalInputLayer()
    judge = ModalityJudge()

    # Test text-only
    inp = MultimodalInput(text="Water boils at 100 degrees Celsius at sea level.")
    mm_out = layer.process(inp)
    result = judge.judge(mm_out)
    print(f"Text-only: confidence={result.overall_confidence}")
    print(f"  Judgments: {[(k, v.reliability) for k, v in result.modality_judgments.items()]}")
    print(f"  Solver hints: {result.solver_weight_hints}")
    print(f"  Parse extras: {list(result.parse_extra_features.keys())}")

    print(f"\n✅ ModalityJudge v{VERSION} OK")
