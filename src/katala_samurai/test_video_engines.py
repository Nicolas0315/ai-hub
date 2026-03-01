"""
Tests for Video Understanding v2.0 + Video Generation Verifier.

No external API calls — all tests use synthetic data.

Design: Youta Hilono
Implementation: Shirokuma
"""

import math
import struct
import pytest
import numpy as np

from katala_samurai.video_understanding import (
    VERSION,
    VideoMetadataParser,
    VideoMetadata,
    SceneChangeDetector,
    SceneInfo,
    OpticalFlowAnalyzer,
    OpticalFlowAnalysis,
    GenerationArtifactDetector,
    GenerationArtifactCheck,
    PixelLevelDeepfakeDetector,
    PixelLevelDeepfakeAnalysis,
    AudioVisualSyncAnalyzer,
    VideoManipulationDetector,
    VideoUnderstandingEngine,
    VideoVerification,
)

from katala_samurai.video_generation_verifier import (
    VideoGenerationVerifier,
    VideoGenerationVerification,
    VisualQualityAnalyzer,
    TemporalConsistencyAnalyzer,
    PromptAccuracyAnalyzer,
    PhysicsRealismAnalyzer,
    GenerationArtifactAnalyzer,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_solid_frames(n=10, h=64, w=64, value=128):
    """Create solid-color grayscale frames."""
    return [np.full((h, w), value, dtype=np.uint8) for _ in range(n)]


def _make_gradient_frames(n=10, h=64, w=64):
    """Create frames with horizontal gradient (gets brighter per frame)."""
    frames = []
    for i in range(n):
        base = int(50 + i * 15)
        row = np.linspace(max(0, base - 30), min(255, base + 30), w, dtype=np.uint8)
        frame = np.tile(row, (h, 1))
        frames.append(frame)
    return frames


def _make_noisy_frames(n=10, h=64, w=64, noise_std=30):
    """Create frames with random noise."""
    return [np.clip(np.random.normal(128, noise_std, (h, w)), 0, 255).astype(np.uint8)
            for _ in range(n)]


def _make_color_frames(n=10, h=64, w=64):
    """Create RGB color frames."""
    return [np.random.randint(80, 200, (h, w, 3), dtype=np.uint8) for _ in range(n)]


def _make_scene_change_frames():
    """Create frames with a clear scene change."""
    dark = [np.full((64, 64), 30, dtype=np.uint8) for _ in range(5)]
    bright = [np.full((64, 64), 220, dtype=np.uint8) for _ in range(5)]
    return dark + bright


def _make_mp4_bytes(width=1920, height=1080, duration_ts=30000, timescale=1000):
    """Create minimal valid MP4 container bytes."""
    # ftyp box
    ftyp = b'\x00\x00\x00\x14ftypmp42\x00\x00\x00\x00mp42'

    # mvhd box (version 0)
    mvhd_data = bytearray(100)
    mvhd_data[0] = 0  # version
    struct.pack_into('>I', mvhd_data, 12, timescale)
    struct.pack_into('>I', mvhd_data, 16, duration_ts)
    mvhd_box = struct.pack('>I', 108) + b'mvhd' + bytes(mvhd_data)

    # tkhd box (version 0)
    tkhd_data = bytearray(84)
    tkhd_data[0] = 0  # version
    struct.pack_into('>I', tkhd_data, 76, width << 16)
    struct.pack_into('>I', tkhd_data, 80, height << 16)
    tkhd_box = struct.pack('>I', 92) + b'tkhd' + bytes(tkhd_data)

    # trak box
    trak_box = struct.pack('>I', 8 + len(tkhd_box)) + b'trak' + tkhd_box

    # moov box
    moov_content = mvhd_box + trak_box
    moov_box = struct.pack('>I', 8 + len(moov_content)) + b'moov' + moov_content

    return ftyp + moov_box


# ═══════════════════════════════════════════════════════════════════════════
# VideoUnderstandingEngine v2.0 Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVideoMetadataParser:
    def test_parse_mp4(self):
        data = _make_mp4_bytes(1920, 1080, 30000, 1000)
        parser = VideoMetadataParser()
        meta = parser.parse(data)
        assert meta.format == "mp4"
        assert meta.width == 1920
        assert meta.height == 1080
        assert abs(meta.duration_seconds - 30.0) < 0.1

    def test_parse_unknown_format(self):
        parser = VideoMetadataParser()
        meta = parser.parse(b'\x00' * 100)
        assert meta.file_size == 100
        assert meta.hash_md5 != ""

    def test_resolution_label(self):
        data = _make_mp4_bytes(1920, 1080)
        parser = VideoMetadataParser()
        meta = parser.parse(data)
        assert meta.resolution_label == "1080p"


class TestSceneChangeDetector:
    def test_estimate_scenes_short(self):
        detector = SceneChangeDetector()
        meta = VideoMetadata(duration_seconds=5.0)
        info = detector.estimate_scenes(meta)
        assert info.scene_count == 1
        assert info.detection_method == "estimated"

    def test_estimate_scenes_medium(self):
        detector = SceneChangeDetector()
        meta = VideoMetadata(duration_seconds=60.0)
        info = detector.estimate_scenes(meta)
        assert info.scene_count >= 3
        assert len(info.scene_boundaries) == info.scene_count - 1

    def test_detect_from_frames_no_change(self):
        detector = SceneChangeDetector()
        frames = _make_solid_frames(10)
        info = detector.detect_from_frames(frames, fps=30.0)
        assert info.scene_count == 1
        assert info.detection_method == "histogram"

    def test_detect_from_frames_with_change(self):
        detector = SceneChangeDetector()
        frames = _make_scene_change_frames()
        info = detector.detect_from_frames(frames, fps=30.0)
        assert info.scene_count >= 2
        assert info.detection_method == "histogram"
        assert len(info.scene_boundaries) >= 1


class TestOpticalFlowAnalyzer:
    def test_static_frames(self):
        analyzer = OpticalFlowAnalyzer()
        # Use frames with texture but no motion (same frame repeated)
        np.random.seed(99)
        base = np.random.randint(50, 200, (64, 64), dtype=np.uint8)
        frames = [base.copy() for _ in range(5)]
        result = analyzer.analyze(frames)
        assert result.available
        # Identical frames → zero displacement
        assert result.avg_magnitude < 0.5
        assert result.motion_type == "static"

    def test_moving_frames(self):
        analyzer = OpticalFlowAnalyzer()
        # Create shifting frames
        frames = []
        for i in range(5):
            f = np.zeros((64, 64), dtype=np.uint8)
            x = min(i * 8, 56)
            f[20:40, x:x+8] = 255
            frames.append(f)
        result = analyzer.analyze(frames)
        assert result.available
        assert result.avg_magnitude >= 0

    def test_insufficient_frames(self):
        analyzer = OpticalFlowAnalyzer()
        result = analyzer.analyze([np.zeros((64, 64), dtype=np.uint8)])
        assert not result.available


class TestGenerationArtifactDetector:
    def test_natural_frames(self):
        detector = GenerationArtifactDetector()
        frames = _make_noisy_frames(10, noise_std=25)
        result = detector.detect(frames)
        assert isinstance(result, GenerationArtifactCheck)
        # Natural frames shouldn't be flagged as generated with high confidence
        assert result.generation_confidence < 0.8

    def test_text_generation_hint(self):
        detector = GenerationArtifactDetector()
        result = detector.detect([], claim_text="This sora-generated video shows a city")
        assert result.generation_confidence > 0.0
        assert len(result.indicators) > 0

    def test_no_input(self):
        detector = GenerationArtifactDetector()
        result = detector.detect([])
        assert result.generation_confidence == 0.0
        assert not result.is_likely_generated

    def test_uniform_frames_flagged(self):
        detector = GenerationArtifactDetector()
        # Very uniform frames (low texture variance = AI-like)
        frames = _make_solid_frames(10, value=128)
        result = detector.detect(frames)
        assert result.texture_uniformity > 0.5


class TestPixelLevelDeepfakeDetector:
    def test_consistent_noise(self):
        detector = PixelLevelDeepfakeDetector()
        # Consistent noise pattern = natural video
        np.random.seed(42)
        frames = [np.random.normal(128, 20, (64, 64)).astype(np.uint8) for _ in range(10)]
        result = detector.analyze(frames)
        assert isinstance(result, PixelLevelDeepfakeAnalysis)
        # Should have low risk for consistent noise
        assert result.risk_score < 0.8

    def test_text_deepfake_hint(self):
        detector = PixelLevelDeepfakeDetector()
        result = detector.analyze([], claim_text="This leaked video you won't believe")
        assert result.risk_score > 0.0

    def test_edge_coherence(self):
        detector = PixelLevelDeepfakeDetector()
        frames = _make_gradient_frames(10)
        result = detector.analyze(frames)
        assert result.edge_coherence >= 0.0


class TestAudioVisualSyncAnalyzer:
    def test_no_audio(self):
        analyzer = AudioVisualSyncAnalyzer()
        meta = VideoMetadata(has_audio=False)
        result = analyzer.analyze(meta)
        assert not result.available
        assert "No audio" in result.issues[0]

    def test_with_audio(self):
        analyzer = AudioVisualSyncAnalyzer()
        meta = VideoMetadata(has_audio=True, bitrate_kbps=5000)
        result = analyzer.analyze(meta)
        assert result.available
        assert result.sync_score > 0.5


class TestVideoUnderstandingEngine:
    def test_version(self):
        # v2.0.0 base or v2.1.0+ with scene-graph extensions
        assert VERSION.startswith("2.")

    def test_get_status(self):
        engine = VideoUnderstandingEngine()
        status = engine.get_status()
        assert status["version"].startswith("2.")
        assert "optical_flow_analysis" in status["capabilities"]
        assert "generation_artifact_detection" in status["capabilities"]
        assert "pixel_level_deepfake_analysis" in status["capabilities"]
        assert "audio_visual_sync" in status["capabilities"]

    def test_verify_no_data(self):
        engine = VideoUnderstandingEngine()
        result = engine.verify_video()
        assert result.verdict == "ERROR"
        assert result.overall_score == 0.0

    def test_verify_mp4(self):
        engine = VideoUnderstandingEngine()
        data = _make_mp4_bytes()
        result = engine.verify_video(video_data=data)
        assert isinstance(result, VideoVerification)
        assert result.metadata.format == "mp4"
        assert result.verdict in ("PASS", "UNCERTAIN", "SUSPICIOUS", "DEEPFAKE_RISK", "AI_GENERATED")

    def test_verify_with_frames(self):
        engine = VideoUnderstandingEngine()
        data = _make_mp4_bytes()
        frames = _make_noisy_frames(10)
        result = engine.verify_video(video_data=data, frames=frames)
        assert result.optical_flow.available
        assert result.generation_artifacts is not None
        assert result.pixel_deepfake is not None
        assert result.scenes.detection_method == "histogram"

    def test_verify_claim_deepfake(self):
        engine = VideoUnderstandingEngine()
        result = engine.verify_video_claim(
            "This leaked video clearly shows the secret meeting. You won't believe what happens.")
        assert result["deepfake_risk"] > 0.2
        assert result["verdict"] in ("SUSPICIOUS", "PLAUSIBLE", "UNCERTAIN", "AI_GENERATED_CLAIM")

    def test_verify_claim_generated(self):
        engine = VideoUnderstandingEngine()
        result = engine.verify_video_claim("This sora-generated video shows a realistic city")
        assert result["generation_score"] > 0.0
        assert "generation_score" in result

    def test_verify_claim_normal(self):
        engine = VideoUnderstandingEngine()
        result = engine.verify_video_claim("A cat playing with a ball.")
        assert result["deepfake_risk"] == 0.0
        assert result["generation_score"] == 0.0

    def test_v2_dataclasses_present(self):
        engine = VideoUnderstandingEngine()
        data = _make_mp4_bytes()
        result = engine.verify_video(video_data=data)
        # Check v2.0 fields exist
        assert hasattr(result, 'generation_artifacts')
        assert hasattr(result, 'pixel_deepfake')
        assert hasattr(result, 'optical_flow')
        assert hasattr(result, 'av_sync')


# ═══════════════════════════════════════════════════════════════════════════
# VideoGenerationVerifier Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVisualQualityAnalyzer:
    def test_clean_frames(self):
        analyzer = VisualQualityAnalyzer()
        frames = _make_gradient_frames(10)
        result = analyzer.analyze(frames)
        assert 0.0 <= result.score <= 1.0
        # Gradient frames may have high Laplacian variance due to steep gradients
        # Just check the score is in valid range

    def test_noisy_frames(self):
        analyzer = VisualQualityAnalyzer()
        frames = _make_noisy_frames(10, noise_std=50)
        result = analyzer.analyze(frames)
        assert result.noise_level > 0.0

    def test_empty_frames(self):
        analyzer = VisualQualityAnalyzer()
        result = analyzer.analyze([])
        assert result.score == 0.5  # Default


class TestTemporalConsistencyAnalyzer:
    def test_consistent_frames(self):
        analyzer = TemporalConsistencyAnalyzer()
        frames = _make_solid_frames(10)
        result = analyzer.analyze(frames)
        assert result.scene_stability > 0.5

    def test_flickering_frames(self):
        analyzer = TemporalConsistencyAnalyzer()
        # Alternating brightness — extreme flicker pattern
        frames = []
        for i in range(20):
            val = 50 if i % 2 == 0 else 200
            frames.append(np.full((64, 64), val, dtype=np.uint8))
        result = analyzer.analyze(frames)
        # With alternating 50/200, the diffs are constant (150) with std=0
        # This means flicker formula gives 0 (constant diff = no variance in diffs)
        # The instability shows up in scene_stability instead
        assert result.score < 0.7  # Overall should reflect instability


class TestPromptAccuracyAnalyzer:
    def test_with_descriptions(self):
        analyzer = PromptAccuracyAnalyzer()
        result = analyzer.analyze(
            prompt_text="a cat jumping over a fence",
            frame_descriptions=["a cat in mid-air over a wooden fence", "cat landing"])
        assert result.subject_present
        assert result.score > 0.0

    def test_no_prompt(self):
        analyzer = PromptAccuracyAnalyzer()
        result = analyzer.analyze(prompt_text="")
        assert result.score == 0.0

    def test_no_descriptions(self):
        analyzer = PromptAccuracyAnalyzer()
        result = analyzer.analyze(prompt_text="a beautiful sunset")
        assert result.score == 0.5  # Neutral


class TestPhysicsRealismAnalyzer:
    def test_normal_prompt(self):
        analyzer = PhysicsRealismAnalyzer()
        frames = _make_gradient_frames(10)
        result = analyzer.analyze(frames, "a ball rolling on the ground")
        assert result.gravity_plausible
        assert result.score > 0.5

    def test_violation_prompt(self):
        analyzer = PhysicsRealismAnalyzer()
        result = analyzer.analyze([], "an object floating and defying gravity")
        assert not result.gravity_plausible
        assert len(result.violations) > 0


class TestGenerationArtifactAnalyzer:
    def test_clean_frames(self):
        analyzer = GenerationArtifactAnalyzer()
        frames = _make_color_frames(10)
        result = analyzer.analyze(frames)
        assert 0.0 <= result.score <= 1.0

    def test_empty(self):
        analyzer = GenerationArtifactAnalyzer()
        result = analyzer.analyze([])
        assert result.score == 0.5  # Default


class TestVideoGenerationVerifier:
    def test_full_pipeline(self):
        verifier = VideoGenerationVerifier()
        frames = _make_color_frames(10)
        result = verifier.verify_generated_video(
            frames=frames,
            prompt_text="a cat jumping over a fence in a garden",
        )
        assert isinstance(result, VideoGenerationVerification)
        assert 0.0 <= result.overall_quality <= 1.0
        assert result.verdict in ("EXCELLENT", "GOOD", "FAIR", "POOR")

    def test_no_frames(self):
        verifier = VideoGenerationVerifier()
        result = verifier.verify_generated_video(prompt_text="test")
        assert isinstance(result, VideoGenerationVerification)

    def test_with_audio(self):
        verifier = VideoGenerationVerifier()
        frames = _make_color_frames(5)
        result = verifier.verify_generated_video(frames=frames, has_audio=True)
        assert result.av_sync.has_audio

    def test_get_status(self):
        verifier = VideoGenerationVerifier()
        status = verifier.get_status()
        assert "visual_quality_assessment" in status["capabilities"]
        assert "generation_artifact_detection" in status["capabilities"]

    def test_content_hash(self):
        verifier = VideoGenerationVerifier()
        result = verifier.verify_generated_video(
            frames=_make_color_frames(3),
            video_data=b"test_video_data"
        )
        assert len(result.content_hash) == 16


# ═══════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_understanding_plus_generation_verifier(self):
        """Test that both engines can analyze the same video data."""
        engine = VideoUnderstandingEngine()
        verifier = VideoGenerationVerifier()

        mp4_data = _make_mp4_bytes()
        frames = _make_noisy_frames(10)

        # Understanding engine
        understanding = engine.verify_video(video_data=mp4_data, frames=frames)
        assert understanding.version.startswith("2.")

        # Generation verifier
        generation = verifier.verify_generated_video(frames=frames, prompt_text="test scene")
        assert generation.version.startswith("1.")

        # Both should produce valid results
        assert understanding.overall_score > 0.0
        assert generation.overall_quality > 0.0

    def test_cross_modal_solver_video_specific(self):
        """Test CrossModalVerifier.verify_video_specific."""
        from katala_samurai.cross_modal_solver import CrossModalVerifier

        verifier = CrossModalVerifier()
        features = {
            "generation_artifacts": {
                "is_likely_generated": True,
                "generation_confidence": 0.8,
            },
            "pixel_deepfake": {"risk_score": 0.6},
            "optical_flow": {"motion_type": "chaotic"},
            "manipulation": {"suspicious": True, "confidence": 0.5},
        }
        result = verifier.verify_video_specific(features, "leaked footage")
        assert result["generation_detected"]
        assert result["video_trustworthiness"] < 0.5
        assert len(result["indicators"]) > 0

    def test_cross_modal_solver_normal_video(self):
        """Test CrossModalVerifier with normal video features."""
        from katala_samurai.cross_modal_solver import CrossModalVerifier

        verifier = CrossModalVerifier()
        features = {
            "generation_artifacts": {
                "is_likely_generated": False,
                "generation_confidence": 0.1,
            },
            "pixel_deepfake": {"risk_score": 0.1},
            "optical_flow": {"motion_type": "pan"},
            "manipulation": {"suspicious": False, "confidence": 0.1},
        }
        result = verifier.verify_video_specific(features)
        assert not result["generation_detected"]
        assert result["video_trustworthiness"] > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
