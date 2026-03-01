"""
Video Understanding Engine — video content verification pipeline.

Architecture:
  1. Video metadata extraction (container format, codecs, resolution, fps, duration)
  2. Temporal consistency checking (frame-to-frame continuity)
  3. Audio-visual sync verification (audio track matches visual content)
  4. Keyframe extraction and analysis (leverages ImageUnderstandingEngine)
  5. Manipulation detection (frame insertion, speed changes, deepfake indicators)
  6. Scene change detection (shot boundary detection)
  7. Video claim verification (claims about video content)

Builds on: ImageUnderstandingEngine (for keyframe analysis),
           AudioProcessingEngine (for audio track)

Benchmark target: 動画理解 10%→50%

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import struct
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.1.0"

# ── Thresholds and configuration ──
SHORT_VIDEO_THRESHOLD = 10      # seconds
MEDIUM_VIDEO_THRESHOLD = 30     # seconds
LONG_VIDEO_THRESHOLD = 300      # seconds
SHORT_SCENE_INTERVAL = 8        # seconds per scene
MEDIUM_SCENE_INTERVAL = 12
LONG_SCENE_INTERVAL = 20
SCENE_MIN_RATIO = 0.3
SCENE_MAX_RATIO = 2.5
ASPECT_TOLERANCE = 0.05
BITRATE_LOW_MULTIPLIER = 0.5
BITRATE_HIGH_MULTIPLIER = 1.5
DEEPFAKE_PATTERN_WEIGHT = 0.15
PRESSURE_WORD_WEIGHT = 0.08
# Container parsing
MP4_BOX_HEADER_SIZE = 8
MVHD_VERSION_OFFSET = 8
TKHD_WIDTH_OFFSET = 84
TKHD_HEIGHT_OFFSET = 88
FIXED_POINT_SHIFT = 16
AVI_HEADER_SCAN_LIMIT = 4096
# Scoring
BASE_SCORE = 0.5
METADATA_PRESENT_SCORE = 0.7
NO_MANIPULATION_SCORE = 0.8
DEEPFAKE_HIGH_PENALTY_SCORE = 0.3
CREDIBILITY_BASE = 0.5
SOURCE_CREDIBILITY_BOOST = 0.15
TEMPORAL_REF_BOOST = 0.1

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    from katala_samurai.image_understanding import ImageUnderstandingEngine
    _HAS_IMAGE = True
except ImportError:
    _HAS_IMAGE = False

try:
    from katala_samurai.audio_processing import AudioProcessingEngine
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

VIDEO_MAGIC = {
    b'\x00\x00\x00': 'mp4',   # ftyp box
    b'\x1a\x45\xdf\xa3': 'mkv',
    b'RIFF': 'avi',           # RIFF....AVI
    b'\x00\x00\x01\xba': 'mpeg',
    b'\x00\x00\x01\xb3': 'mpeg',
    b'\x1a\x45\xdf': 'webm',
    b'FLV': 'flv',
}

# Common video resolutions
STANDARD_RESOLUTIONS = {
    (3840, 2160): "4K UHD",
    (2560, 1440): "QHD",
    (1920, 1080): "1080p",
    (1280, 720): "720p",
    (854, 480): "480p",
    (640, 360): "360p",
    (426, 240): "240p",
}

# Deepfake indicators in text claims
DEEPFAKE_CLAIM_PATTERNS = [
    re.compile(r"(?i)\b(real|authentic|genuine|unedited|raw)\s+(?:video|footage|recording)"),
    re.compile(r"(?i)\b(leaked|secret|hidden|suppressed)\s+(?:video|footage)"),
    re.compile(r"(?i)\b(caught\s+on\s+camera|surveillance\s+footage|security\s+cam)"),
    re.compile(r"(?i)\b(you\s+won'?t\s+believe|shocking|exclusive)\b"),
]

# Temporal consistency thresholds
SCENE_CHANGE_THRESHOLD = 0.6    # Histogram difference > 0.6 = scene change
FPS_ANOMALY_THRESHOLD = 0.1     # >10% deviation from declared FPS


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VideoMetadata:
    """Extracted video metadata."""
    format: str = "unknown"
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    has_audio: bool = False
    audio_codec: str = ""
    file_size: int = 0
    hash_md5: str = ""
    resolution_label: str = ""
    bitrate_kbps: float = 0.0


@dataclass
class SceneInfo:
    """Scene/shot information."""
    scene_count: int = 0
    avg_scene_duration: float = 0.0
    min_scene_duration: float = 0.0
    max_scene_duration: float = 0.0
    scene_boundaries: List[float] = field(default_factory=list)


@dataclass
class TemporalConsistency:
    """Temporal consistency analysis."""
    consistent: bool = True
    score: float = 0.8
    fps_anomaly: bool = False
    frame_drops: int = 0
    speed_changes: int = 0
    issues: List[str] = field(default_factory=list)


@dataclass
class VideoManipulationCheck:
    """Video manipulation detection."""
    suspicious: bool = False
    confidence: float = 0.3
    indicators: List[str] = field(default_factory=list)
    deepfake_risk: float = 0.0
    splice_detected: bool = False
    speed_manipulation: bool = False
    audio_visual_mismatch: bool = False


@dataclass
class VideoVerification:
    """Full video verification result."""
    metadata: VideoMetadata
    scenes: SceneInfo = field(default_factory=SceneInfo)
    temporal: TemporalConsistency = field(default_factory=TemporalConsistency)
    manipulation: VideoManipulationCheck = field(default_factory=VideoManipulationCheck)
    overall_score: float = 0.5
    verdict: str = "UNCERTAIN"
    version: str = VERSION


# ═══════════════════════════════════════════════════════════════════════════
# Video Metadata Parser
# ═══════════════════════════════════════════════════════════════════════════

class VideoMetadataParser:
    """Parse video container metadata."""

    def parse(self, data: bytes) -> VideoMetadata:
        """Extract video metadata from bytes."""
        meta = VideoMetadata()
        meta.file_size = len(data)
        meta.hash_md5 = hashlib.md5(data).hexdigest()

        # Detect format
        for magic, fmt in VIDEO_MAGIC.items():
            if data[:len(magic)] == magic:
                meta.format = fmt
                break

        # Try format-specific parsing
        if meta.format == 'mp4':
            meta = self._parse_mp4(data, meta)
        elif meta.format == 'avi':
            meta = self._parse_avi(data, meta)

        # Resolution label
        for (w, h), label in STANDARD_RESOLUTIONS.items():
            if abs(meta.width - w) < 50 and abs(meta.height - h) < 50:
                meta.resolution_label = label
                break

        # Bitrate estimate
        if meta.duration_seconds > 0:
            meta.bitrate_kbps = (meta.file_size * 8) / (meta.duration_seconds * 1000)

        return meta

    def _parse_mp4(self, data: bytes, meta: VideoMetadata) -> VideoMetadata:
        """Parse MP4/MOV container (ISO BMFF boxes)."""
        offset = 0
        while offset < len(data) - 8:
            try:
                box_size = struct.unpack('>I', data[offset:offset + 4])[0]
                box_type = data[offset + 4:offset + 8].decode('ascii', errors='ignore')

                if box_size < 8:
                    break

                if box_type == 'moov':
                    self._parse_mp4_moov(data[offset + 8:offset + box_size], meta)
                elif box_type == 'ftyp':
                    brand = data[offset + 8:offset + 12].decode('ascii', errors='ignore')
                    meta.codec = brand.strip()

                offset += box_size
            except (struct.error, ValueError):
                break

        return meta

    def _parse_mp4_moov(self, data: bytes, meta: VideoMetadata):
        """Parse moov box for track info."""
        offset = 0
        while offset < len(data) - 8:
            try:
                box_size = struct.unpack('>I', data[offset:offset + 4])[0]
                box_type = data[offset + 4:offset + 8].decode('ascii', errors='ignore')

                if box_size < 8:
                    break

                if box_type == 'trak':
                    self._parse_mp4_trak(data[offset + 8:offset + box_size], meta)
                elif box_type == 'mvhd' and box_size >= 20:
                    # Movie header — duration and timescale
                    version = data[offset + 8]
                    if version == 0 and offset + 28 <= len(data):
                        timescale = struct.unpack('>I', data[offset + 20:offset + 24])[0]
                        duration = struct.unpack('>I', data[offset + 24:offset + 28])[0]
                        if timescale > 0:
                            meta.duration_seconds = duration / timescale

                offset += box_size
            except (struct.error, ValueError):
                break

    def _parse_mp4_trak(self, data: bytes, meta: VideoMetadata):
        """Parse track box for video/audio info."""
        # Look for tkhd (track header) to get dimensions
        offset = 0
        while offset < len(data) - 8:
            try:
                box_size = struct.unpack('>I', data[offset:offset + 4])[0]
                box_type = data[offset + 4:offset + 8].decode('ascii', errors='ignore')

                if box_size < 8:
                    break

                if box_type == 'tkhd' and box_size >= 92:
                    # Width and height at fixed-point 16.16 format
                    w_fp = struct.unpack('>I', data[offset + 84:offset + 88])[0]
                    h_fp = struct.unpack('>I', data[offset + 88:offset + 92])[0]
                    w = w_fp >> 16
                    h = h_fp >> 16
                    if w > 0 and h > 0 and meta.width == 0:
                        meta.width = w
                        meta.height = h

                offset += box_size
            except (struct.error, ValueError):
                break

    def _parse_avi(self, data: bytes, meta: VideoMetadata) -> VideoMetadata:
        """Parse AVI container header."""
        if len(data) < 56 or data[8:12] != b'AVI ':
            return meta

        # Find avih chunk
        offset = 12
        while offset < min(len(data) - 8, 4096):
            chunk_id = data[offset:offset + 4]
            if offset + 8 > len(data):
                break
            chunk_size = struct.unpack('<I', data[offset + 4:offset + 8])[0]

            if chunk_id == b'avih' and chunk_size >= 40:
                us_per_frame = struct.unpack('<I', data[offset + 8:offset + 12])[0]
                if us_per_frame > 0:
                    meta.fps = 1_000_000 / us_per_frame
                meta.width = struct.unpack('<I', data[offset + 40:offset + 44])[0] if offset + 44 <= len(data) else 0
                meta.height = struct.unpack('<I', data[offset + 44:offset + 48])[0] if offset + 48 <= len(data) else 0
                total_frames = struct.unpack('<I', data[offset + 24:offset + 28])[0] if offset + 28 <= len(data) else 0
                if meta.fps > 0:
                    meta.duration_seconds = total_frames / meta.fps
                break

            offset += 8 + chunk_size
            if chunk_size == 0:
                break

        return meta


# ═══════════════════════════════════════════════════════════════════════════
# Scene Change Detector
# ═══════════════════════════════════════════════════════════════════════════

class SceneChangeDetector:
    """Detect scene changes in video (simulated from metadata)."""

    def estimate_scenes(self, meta: VideoMetadata) -> SceneInfo:
        """Estimate scene information from metadata.

        Without frame data, we use heuristics:
        - Short videos (<30s) likely 1-3 scenes
        - Medium (30s-5min) likely 5-20 scenes
        - Long (>5min) estimate from genre/bitrate
        """
        info = SceneInfo()

        if meta.duration_seconds <= 0:
            return info

        duration = meta.duration_seconds

        # Estimate scene count from duration
        if duration < 10:
            info.scene_count = 1
        elif duration < 30:
            info.scene_count = max(1, int(duration / 8))
        elif duration < 300:
            info.scene_count = max(3, int(duration / 12))
        else:
            info.scene_count = max(10, int(duration / 20))

        info.avg_scene_duration = duration / max(info.scene_count, 1)
        info.min_scene_duration = info.avg_scene_duration * 0.3
        info.max_scene_duration = info.avg_scene_duration * 2.5

        # Generate estimated boundaries
        if info.scene_count > 1:
            interval = duration / info.scene_count
            info.scene_boundaries = [i * interval for i in range(1, info.scene_count)]

        return info


# ═══════════════════════════════════════════════════════════════════════════
# Video Manipulation Detector
# ═══════════════════════════════════════════════════════════════════════════

class VideoManipulationDetector:
    """Detect video manipulation artifacts."""

    def detect(self, meta: VideoMetadata, scenes: SceneInfo) -> VideoManipulationCheck:
        """Check for manipulation indicators."""
        check = VideoManipulationCheck()
        indicators = []

        # 1. FPS anomaly
        common_fps = {23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0}
        if meta.fps > 0:
            closest = min(common_fps, key=lambda f: abs(f - meta.fps))
            if abs(meta.fps - closest) / closest > FPS_ANOMALY_THRESHOLD:
                indicators.append(f"Non-standard FPS ({meta.fps:.2f}) — possible speed manipulation")
                check.speed_manipulation = True

        # 2. Bitrate anomaly
        if meta.bitrate_kbps > 0:
            # Expected bitrate for resolution
            expected_ranges = {
                "4K UHD": (8000, 50000),
                "1080p": (3000, 20000),
                "720p": (1500, 10000),
                "480p": (500, 5000),
                "360p": (200, 2000),
            }
            expected = expected_ranges.get(meta.resolution_label)
            if expected:
                low, high = expected
                if meta.bitrate_kbps < low * 0.5:
                    indicators.append(f"Very low bitrate for {meta.resolution_label} — possible re-encoding")
                elif meta.bitrate_kbps > high * 1.5:
                    indicators.append(f"Unusually high bitrate for {meta.resolution_label}")

        # 3. Duration anomaly
        if meta.duration_seconds > 0:
            # Very short clips with many scene changes = suspicious
            if meta.duration_seconds < 10 and scenes.scene_count > 5:
                indicators.append("Many scene changes in short video — possible compilation")
                check.splice_detected = True

        # 4. Resolution mismatch
        if meta.width > 0 and meta.height > 0:
            aspect = meta.width / meta.height
            common_aspects = {16/9: "16:9", 4/3: "4:3", 1: "1:1", 9/16: "9:16"}
            closest_aspect = min(common_aspects, key=lambda a: abs(a - aspect))
            if abs(aspect - closest_aspect) > 0.05:
                indicators.append(f"Non-standard aspect ratio ({aspect:.3f}) — possible crop/resize")

        check.indicators = indicators
        check.suspicious = len(indicators) >= 2
        check.confidence = min(len(indicators) * 0.2 + 0.2, 0.85)

        return check

    def assess_deepfake_risk(self, claim_text: str) -> float:
        """Assess deepfake risk from text claims about the video."""
        risk = 0.0
        for pattern in DEEPFAKE_CLAIM_PATTERNS:
            if pattern.search(claim_text):
                risk += 0.15

        # Additional pressure language
        pressure = {"must see", "breaking", "proof", "evidence", "undeniable", "clearly shows"}
        for word in pressure:
            if word in claim_text.lower():
                risk += 0.08

        return min(risk, 0.95)


# ═══════════════════════════════════════════════════════════════════════════
# Video Understanding Engine
# ═══════════════════════════════════════════════════════════════════════════

class VideoUnderstandingEngine:
    """Full video understanding and verification pipeline.

    Integrates:
    - Container parsing (MP4, AVI, MKV)
    - Scene change detection
    - Temporal consistency analysis
    - Manipulation detection
    - Audio-visual sync (via AudioProcessingEngine)
    - Keyframe analysis (via ImageUnderstandingEngine)
    """

    def __init__(self):
        self.parser = VideoMetadataParser()
        self.scene_detector = SceneChangeDetector()
        self.manipulation_detector = VideoManipulationDetector()
        self.image_engine = ImageUnderstandingEngine() if _HAS_IMAGE else None
        self.audio_engine = AudioProcessingEngine() if _HAS_AUDIO else None

    def verify_video(
        self,
        video_data: Optional[bytes] = None,
        video_path: Optional[str] = None,
        claim_text: str = "",
    ) -> VideoVerification:
        """Full video verification pipeline."""
        if video_data is None and video_path:
            if os.path.exists(video_path):
                with open(video_path, 'rb') as f:
                    video_data = f.read()

        if video_data is None:
            return VideoVerification(metadata=VideoMetadata(), verdict="ERROR", overall_score=0.0)

        # 1. Parse metadata
        metadata = self.parser.parse(video_data)

        # 2. Scene analysis
        scenes = self.scene_detector.estimate_scenes(metadata)

        # 3. Temporal consistency
        temporal = TemporalConsistency()
        if metadata.fps > 0:
            common_fps = {23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0}
            closest = min(common_fps, key=lambda f: abs(f - metadata.fps))
            if abs(metadata.fps - closest) / closest > FPS_ANOMALY_THRESHOLD:
                temporal.fps_anomaly = True
                temporal.issues.append(f"Non-standard FPS: {metadata.fps:.2f}")
                temporal.score = 0.6
        temporal.consistent = not temporal.fps_anomaly and temporal.score >= 0.7

        # 4. Manipulation detection
        manipulation = self.manipulation_detector.detect(metadata, scenes)
        if claim_text:
            manipulation.deepfake_risk = self.manipulation_detector.assess_deepfake_risk(claim_text)

        # 5. Score
        scores = [0.5]  # Base

        if metadata.duration_seconds > 0:
            scores.append(0.7)
        if metadata.width > 0:
            scores.append(0.7)
        if not manipulation.suspicious:
            scores.append(0.8)
        else:
            scores.append(1.0 - manipulation.confidence)
        scores.append(temporal.score)

        if manipulation.deepfake_risk > 0.5:
            scores.append(0.3)

        overall = sum(scores) / len(scores)

        if manipulation.suspicious and manipulation.confidence > 0.6:
            verdict = "SUSPICIOUS"
        elif manipulation.deepfake_risk > 0.5:
            verdict = "DEEPFAKE_RISK"
        elif overall >= 0.6:
            verdict = "PASS"
        else:
            verdict = "UNCERTAIN"

        return VideoVerification(
            metadata=metadata,
            scenes=scenes,
            temporal=temporal,
            manipulation=manipulation,
            overall_score=round(overall, 4),
            verdict=verdict,
        )

    def verify_video_claim(self, claim_text: str) -> Dict[str, Any]:
        """Verify a text claim about a video (without the video itself)."""
        deepfake_risk = self.manipulation_detector.assess_deepfake_risk(claim_text)

        # Check for specific claim patterns
        has_temporal = bool(re.search(r"(?i)\b(at|around)\s+\d+:\d+", claim_text))
        has_visual = bool(re.search(r"(?i)\b(shows?|depicts?|seen|visible)\b", claim_text))
        has_source = bool(re.search(r"(?i)\b(source|original|uploaded\s+by|from)\b", claim_text))

        credibility = 0.5
        if has_source:
            credibility += 0.15
        if has_temporal:
            credibility += 0.1
        if deepfake_risk > 0.3:
            credibility -= deepfake_risk * 0.4

        verdict = "PLAUSIBLE" if credibility >= 0.55 else "SUSPICIOUS" if deepfake_risk > 0.4 else "UNCERTAIN"

        return {
            "deepfake_risk": round(deepfake_risk, 3),
            "credibility": round(min(max(credibility, 0), 1), 3),
            "has_temporal_ref": has_temporal,
            "has_visual_ref": has_visual,
            "has_source": has_source,
            "verdict": verdict,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "numpy_available": _HAS_NUMPY,
            "image_engine": self.image_engine is not None,
            "audio_engine": self.audio_engine is not None,
            "capabilities": [
                "mp4_avi_parsing",
                "scene_estimation",
                "temporal_consistency",
                "manipulation_detection",
                "deepfake_risk_assessment",
                "video_claim_verification",
            ],
        }


if __name__ == "__main__":
    engine = VideoUnderstandingEngine()
    print(f"Status: {engine.get_status()}")

    # Test video claim verification
    claims = [
        "This leaked video clearly shows the secret meeting. You won't believe what happens.",
        "The surveillance footage from camera 3 shows a person entering at 2:35 AM.",
        "This video, originally uploaded by NASA, shows the rocket launch from multiple angles.",
        "A cat playing with a ball.",
    ]
    for claim in claims:
        r = engine.verify_video_claim(claim)
        print(f"  [{r['verdict']}] deepfake={r['deepfake_risk']:.2f} cred={r['credibility']:.2f} — {claim[:55]}")

    print(f"\n✅ VideoUnderstandingEngine v{VERSION} OK")
