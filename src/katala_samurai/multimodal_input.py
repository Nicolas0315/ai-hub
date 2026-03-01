"""
Multimodal Input Layer — ⓪層: 入力→_parse()の前段

Youta設計: 入力の後、_parse()の前に4モダリティ処理層を追加。
テキスト/画像/音声/動画を統一テキスト表現に変換し、
後段の_parse()→33ソルバーに渡す。

Architecture:
  入力 (テキスト / 画像 / 音声 / 動画 / 複合)
    ↓
  ⓪ マルチモーダル入力層 [THIS MODULE]
    ├─ ① TextProcessor (現行テキストをそのまま通す + 正規化)
    ├─ ② ImageProcessor (CLIP → キャプション + メタデータ)
    ├─ ③ AudioProcessor (Whisper → トランスクリプト + スペクトル特徴)
    └─ ④ VideoProcessor (②+③ → シーン記述 + 音声テキスト)
    ↓
  ModalityJudge (判断層) → 統合テキスト表現
    ↓
  _parse() 35特徴抽出
    ↓
  33ソルバー投票

Design: Youta Hilono (architecture) + Shirokuma (implementation)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════
# Modality types
# ═══════════════════════════════════════════════════════════════════════════

class Modality(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class ModalityResult:
    """Result from a single modality processor."""
    modality: Modality
    available: bool = True
    text_representation: str = ""       # Unified text output
    confidence: float = 0.5
    features: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class MultimodalInput:
    """Unified multimodal input container."""
    text: Optional[str] = None
    image_data: Optional[bytes] = None
    image_path: Optional[str] = None
    audio_data: Optional[bytes] = None
    audio_path: Optional[str] = None
    video_data: Optional[bytes] = None
    video_path: Optional[str] = None
    claim: str = ""  # The claim to verify (may overlap with text)


@dataclass
class MultimodalOutput:
    """Output from the multimodal input layer."""
    unified_text: str = ""              # Combined text for _parse()
    modalities_present: List[str] = field(default_factory=list)
    modality_results: Dict[str, ModalityResult] = field(default_factory=dict)
    cross_modal_features: Dict[str, Any] = field(default_factory=dict)
    solver_weight_hints: Dict[str, float] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# ① Text Processor
# ═══════════════════════════════════════════════════════════════════════════

class TextProcessor:
    """Process text input — normalize and extract surface features."""

    def process(self, text: str) -> ModalityResult:
        if not text or not text.strip():
            return ModalityResult(modality=Modality.TEXT, available=False)

        normalized = self._normalize(text)
        features = self._extract_features(normalized)

        return ModalityResult(
            modality=Modality.TEXT,
            available=True,
            text_representation=normalized,
            confidence=0.9,
            features=features,
        )

    def _normalize(self, text: str) -> str:
        """Basic text normalization."""
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_features(self, text: str) -> Dict[str, Any]:
        """Pre-parse text features for the judgment layer."""
        words = text.split()
        has_numbers = bool(re.search(r'\d+\.?\d*', text))
        has_urls = bool(re.search(r'https?://', text))
        has_quotes = bool(re.search(r'["\u201c\u201d\u300c\u300d]', text))

        # Language hint
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or
                        '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        is_cjk = cjk_count > len(text) * 0.2

        return {
            "word_count": len(words),
            "char_count": len(text),
            "has_numbers": has_numbers,
            "has_urls": has_urls,
            "has_quotes": has_quotes,
            "is_cjk": is_cjk,
            "sentence_count": max(1, text.count('.') + text.count('。') + text.count('!') + text.count('?')),
        }


# ═══════════════════════════════════════════════════════════════════════════
# ② Image Processor
# ═══════════════════════════════════════════════════════════════════════════

class ImageProcessor:
    """Process image input → text representation via CLIP + metadata."""

    def __init__(self):
        self._engine = None
        try:
            from katala_samurai.image_understanding import ImageUnderstandingEngine
            self._engine = ImageUnderstandingEngine()
        except ImportError:
            pass

    def process(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        claim_text: str = "",
    ) -> ModalityResult:
        if image_data is None and image_path:
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_data = f.read()

        if image_data is None:
            return ModalityResult(modality=Modality.IMAGE, available=False)

        features = {}
        text_parts = []
        warnings = []
        confidence = 0.5

        if self._engine:
            # Full image verification
            verification = self._engine.verify_image(image_data, claim_text=claim_text)
            features["metadata"] = {
                "format": verification.metadata.format,
                "width": verification.metadata.width,
                "height": verification.metadata.height,
                "has_exif": verification.metadata.has_exif,
            }
            features["manipulation"] = {
                "suspicious": verification.manipulation.suspicious,
                "confidence": verification.manipulation.confidence,
                "indicators": verification.manipulation.indicators,
            }
            features["colors"] = {
                "dominant": verification.colors.dominant_color,
                "entropy": verification.colors.entropy,
            }

            # Build text representation
            text_parts.append(f"[IMAGE: {verification.metadata.format} "
                            f"{verification.metadata.width}x{verification.metadata.height}]")

            if verification.manipulation.suspicious:
                text_parts.append(f"[MANIPULATION WARNING: {', '.join(verification.manipulation.indicators[:3])}]")
                warnings.append("Image manipulation suspected")

            if not verification.metadata.has_exif:
                text_parts.append("[NO EXIF: metadata stripped]")
                warnings.append("EXIF metadata missing")

            # CLIP caption verification if claim provided
            if claim_text:
                clip_result = self._engine.clip_verify_caption(
                    image_data, claim_text,
                    negative_captions=["a random unrelated image", "nothing meaningful"]
                )
                if clip_result.get("available"):
                    sim = clip_result.get("caption_similarity", 0)
                    features["clip_similarity"] = sim
                    text_parts.append(f"[CLIP: claim-image similarity={sim:.3f}]")
                    confidence = max(0.3, min(0.95, sim * 1.5 + 0.2))

            confidence = max(confidence, 0.6 if not verification.manipulation.suspicious else 0.3)
        else:
            text_parts.append(f"[IMAGE: {len(image_data)} bytes, no analysis engine]")
            features["raw_size"] = len(image_data)

        return ModalityResult(
            modality=Modality.IMAGE,
            available=True,
            text_representation=" ".join(text_parts),
            confidence=confidence,
            features=features,
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════
# ③ Audio Processor
# ═══════════════════════════════════════════════════════════════════════════

class AudioProcessor:
    """Process audio input → text representation via Whisper + spectral."""

    def __init__(self):
        self._engine = None
        try:
            from katala_samurai.audio_processing import AudioProcessingEngine
            self._engine = AudioProcessingEngine()
        except ImportError:
            pass

    def process(
        self,
        audio_data: Optional[bytes] = None,
        audio_path: Optional[str] = None,
        claim_text: str = "",
    ) -> ModalityResult:
        if audio_data is None and audio_path is None:
            return ModalityResult(modality=Modality.AUDIO, available=False)

        features = {}
        text_parts = []
        warnings = []
        confidence = 0.5

        if self._engine:
            # Parse audio metadata
            if audio_data:
                verification = self._engine.verify_audio(audio_data, claim_text=claim_text)
                features["metadata"] = {
                    "format": verification.metadata.format,
                    "duration": verification.metadata.duration_seconds,
                    "sample_rate": verification.metadata.sample_rate,
                }
                features["manipulation"] = {
                    "suspicious": verification.manipulation.suspicious,
                    "indicators": verification.manipulation.indicators,
                }
                text_parts.append(f"[AUDIO: {verification.metadata.format} "
                                f"{verification.metadata.duration_seconds:.1f}s]")

                if verification.manipulation.suspicious:
                    text_parts.append(f"[SPLICE WARNING: {', '.join(verification.manipulation.indicators[:2])}]")
                    warnings.append("Audio manipulation suspected")

            # Whisper transcription
            if audio_path:
                transcript = self._engine.transcribe(audio_path)
                if transcript.get("available") and "text" in transcript:
                    features["transcript"] = transcript["text"]
                    features["language"] = transcript.get("language", "unknown")
                    features["segment_count"] = transcript.get("segment_count", 0)
                    text_parts.append(f"[TRANSCRIPT ({transcript.get('language', '?')}): "
                                    f"{transcript['text'][:200]}]")
                    confidence = 0.8

                    # Cross-check transcript against claim
                    if claim_text:
                        verify = self._engine.verify_with_transcript(audio_path, claim_text)
                        features["transcript_match"] = verify.get("similarity", 0)
                        if verify.get("similarity", 0) < 0.3:
                            warnings.append("Transcript does not match claim")
                            text_parts.append("[MISMATCH: transcript differs from claim]")
        else:
            if audio_data:
                text_parts.append(f"[AUDIO: {len(audio_data)} bytes, no analysis engine]")
            elif audio_path:
                text_parts.append(f"[AUDIO: {audio_path}, no analysis engine]")

        return ModalityResult(
            modality=Modality.AUDIO,
            available=True,
            text_representation=" ".join(text_parts),
            confidence=confidence,
            features=features,
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════
# ④ Video Processor
# ═══════════════════════════════════════════════════════════════════════════

class VideoProcessor:
    """Process video input → text representation via Image+Audio engines.

    v2.0: Integrates generation artifact detection with [GENERATED]/[NATURAL] tags.

    Design: Youta Hilono / Implementation: Shirokuma
    """

    def __init__(self):
        self._engine = None
        try:
            from katala_samurai.video_understanding import VideoUnderstandingEngine
            self._engine = VideoUnderstandingEngine()
        except ImportError:
            pass

    def process(
        self,
        video_data: Optional[bytes] = None,
        video_path: Optional[str] = None,
        claim_text: str = "",
    ) -> ModalityResult:
        if video_data is None and video_path:
            if os.path.exists(video_path):
                with open(video_path, 'rb') as f:
                    video_data = f.read()

        if video_data is None:
            return ModalityResult(modality=Modality.VIDEO, available=False)

        features = {}
        text_parts = []
        warnings = []
        confidence = 0.5

        if self._engine:
            verification = self._engine.verify_video(video_data=video_data, claim_text=claim_text)
            features["metadata"] = {
                "format": verification.metadata.format,
                "duration": verification.metadata.duration_seconds,
                "width": verification.metadata.width,
                "height": verification.metadata.height,
                "fps": verification.metadata.fps,
            }
            features["scenes"] = {
                "count": verification.scenes.scene_count,
                "avg_duration": verification.scenes.avg_scene_duration,
                "detection_method": verification.scenes.detection_method,
            }
            features["manipulation"] = {
                "suspicious": verification.manipulation.suspicious,
                "deepfake_risk": verification.manipulation.deepfake_risk,
                "indicators": verification.manipulation.indicators,
            }

            # v2.0: Generation artifact features
            gen = verification.generation_artifacts
            features["generation_artifacts"] = {
                "is_likely_generated": gen.is_likely_generated,
                "generation_confidence": gen.generation_confidence,
                "flicker_score": gen.flicker_score,
                "background_drift": gen.background_drift,
                "hand_anomaly_risk": gen.hand_anomaly_risk,
                "texture_uniformity": gen.texture_uniformity,
                "motion_smoothness": gen.motion_smoothness,
            }

            # v2.0: Pixel deepfake features
            features["pixel_deepfake"] = {
                "risk_score": verification.pixel_deepfake.risk_score,
                "noise_inconsistency": verification.pixel_deepfake.noise_inconsistency,
            }

            # v2.0: Optical flow features
            if verification.optical_flow.available:
                features["optical_flow"] = {
                    "avg_magnitude": verification.optical_flow.avg_magnitude,
                    "motion_type": verification.optical_flow.motion_type,
                    "motion_consistency": verification.optical_flow.motion_consistency,
                }

            text_parts.append(f"[VIDEO: {verification.metadata.format} "
                            f"{verification.metadata.width}x{verification.metadata.height} "
                            f"{verification.metadata.duration_seconds:.1f}s "
                            f"{verification.metadata.fps:.1f}fps]")

            # v2.0: [GENERATED] / [NATURAL] tag
            if gen.is_likely_generated:
                text_parts.append(f"[GENERATED: confidence={gen.generation_confidence:.2f}]")
                warnings.append("AI-generated video detected")
            else:
                text_parts.append("[NATURAL]")

            if verification.manipulation.suspicious:
                text_parts.append(f"[VIDEO MANIPULATION: {', '.join(verification.manipulation.indicators[:2])}]")
                warnings.append("Video manipulation suspected")

            if verification.manipulation.deepfake_risk > 0.4:
                text_parts.append(f"[DEEPFAKE RISK: {verification.manipulation.deepfake_risk:.2f}]")
                warnings.append("Deepfake risk elevated")

            if verification.pixel_deepfake.risk_score > 0.5:
                text_parts.append(f"[PIXEL DEEPFAKE: {verification.pixel_deepfake.risk_score:.2f}]")
                warnings.append("Pixel-level deepfake indicators")

            text_parts.append(f"[SCENES: {verification.scenes.scene_count} "
                            f"({verification.scenes.detection_method})]")
            confidence = verification.overall_score
        else:
            text_parts.append(f"[VIDEO: {len(video_data)} bytes, no analysis engine]")

        return ModalityResult(
            modality=Modality.VIDEO,
            available=True,
            text_representation=" ".join(text_parts),
            confidence=confidence,
            features=features,
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Multimodal Input Layer (main class)
# ═══════════════════════════════════════════════════════════════════════════

class MultimodalInputLayer:
    """⓪ Layer: Process all input modalities into unified representation.

    Sits between raw input and _parse(), converting heterogeneous
    inputs (text/image/audio/video) into a unified text representation
    that _parse() can consume.
    """

    def __init__(self):
        self.text_proc = TextProcessor()
        self.image_proc = ImageProcessor()
        self.audio_proc = AudioProcessor()
        self.video_proc = VideoProcessor()

    def process(self, inp: MultimodalInput) -> MultimodalOutput:
        """Process all available modalities and produce unified output."""
        output = MultimodalOutput()
        claim = inp.claim or inp.text or ""

        # ① Text
        if inp.text:
            result = self.text_proc.process(inp.text)
            output.modality_results["text"] = result
            output.modalities_present.append("text")

        # ② Image
        if inp.image_data or inp.image_path:
            result = self.image_proc.process(
                image_data=inp.image_data,
                image_path=inp.image_path,
                claim_text=claim,
            )
            if result.available:
                output.modality_results["image"] = result
                output.modalities_present.append("image")

        # ③ Audio
        if inp.audio_data or inp.audio_path:
            result = self.audio_proc.process(
                audio_data=inp.audio_data,
                audio_path=inp.audio_path,
                claim_text=claim,
            )
            if result.available:
                output.modality_results["audio"] = result
                output.modalities_present.append("audio")

        # ④ Video
        if inp.video_data or inp.video_path:
            result = self.video_proc.process(
                video_data=inp.video_data,
                video_path=inp.video_path,
                claim_text=claim,
            )
            if result.available:
                output.modality_results["video"] = result
                output.modalities_present.append("video")

        # Build unified text
        text_parts = []
        for modality_name in ["text", "image", "audio", "video"]:
            mr = output.modality_results.get(modality_name)
            if mr and mr.text_representation:
                text_parts.append(mr.text_representation)

        output.unified_text = " ".join(text_parts)

        # Cross-modal features
        output.cross_modal_features = self._extract_cross_modal(output)

        return output

    def _extract_cross_modal(self, output: MultimodalOutput) -> Dict[str, Any]:
        """Extract features from cross-modal interactions."""
        features = {
            "modality_count": len(output.modalities_present),
            "is_multimodal": len(output.modalities_present) > 1,
        }

        # Collect all warnings across modalities
        all_warnings = []
        for mr in output.modality_results.values():
            all_warnings.extend(mr.warnings)
        features["total_warnings"] = len(all_warnings)
        features["warnings"] = all_warnings

        # Cross-modal consistency
        if "image" in output.modality_results and "text" in output.modality_results:
            img = output.modality_results["image"]
            clip_sim = img.features.get("clip_similarity", None)
            if clip_sim is not None:
                features["text_image_alignment"] = clip_sim
                if clip_sim < 0.2:
                    features["text_image_contradiction"] = True

        if "audio" in output.modality_results:
            audio = output.modality_results["audio"]
            transcript_match = audio.features.get("transcript_match", None)
            if transcript_match is not None:
                features["text_audio_alignment"] = transcript_match
                if transcript_match < 0.3:
                    features["text_audio_contradiction"] = True

        return features

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "processors": {
                "text": True,
                "image": self.image_proc._engine is not None,
                "audio": self.audio_proc._engine is not None,
                "video": self.video_proc._engine is not None,
            },
        }


if __name__ == "__main__":
    layer = MultimodalInputLayer()
    print(f"Status: {layer.get_status()}")

    # Test text-only
    inp = MultimodalInput(text="Water boils at 100 degrees Celsius at sea level.")
    out = layer.process(inp)
    print(f"Text-only: modalities={out.modalities_present} unified_len={len(out.unified_text)}")

    # Test claim with no media
    inp2 = MultimodalInput(claim="This photo proves the Earth is flat")
    out2 = layer.process(inp2)
    print(f"Claim-only: modalities={out2.modalities_present}")

    print(f"\n✅ MultimodalInputLayer v{VERSION} OK")
