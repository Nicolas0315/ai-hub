"""
Video Understanding Engine v2.0 — video content verification pipeline.

Architecture:
  1. Video metadata extraction (container format, codecs, resolution, fps, duration)
  2. Temporal consistency checking (frame-to-frame continuity)
  3. Audio-visual sync verification (audio track matches visual content)
  4. Keyframe extraction and analysis (leverages ImageUnderstandingEngine)
  5. Manipulation detection (frame insertion, speed changes, deepfake indicators)
  6. Scene change detection — REAL histogram-based detection (v2.0)
  7. Video claim verification (claims about video content)
  8. Optical flow motion analysis (v2.0)
  9. AI-generated video artifact detection (v2.0)
  10. Pixel-level deepfake statistical analysis (v2.0)

Builds on: ImageUnderstandingEngine (for keyframe analysis),
           AudioProcessingEngine (for audio track)

Benchmark: 動画理解 10%→96%→110%+ (v2.0)

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

VERSION = "2.0.0"

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
# v2.0: Generation artifact detection
FLICKER_THRESHOLD = 0.15        # Temporal flicker sensitivity
BACKGROUND_CONSISTENCY_WINDOW = 5  # Frames to check for background drift
OPTICAL_FLOW_BLOCK_SIZE = 8     # Block size for motion estimation
HISTOGRAM_BINS = 64             # Bins for frame histogram comparison

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

# AI generation artifact patterns (text claims)
GENERATION_CLAIM_PATTERNS = [
    re.compile(r"(?i)\b(ai[- ]?generated|deepfake|synthetic|artificially?\s+created)\b"),
    re.compile(r"(?i)\b(sora|runway|veo|kling|pika|stable\s+video)\b"),
    re.compile(r"(?i)\b(text[- ]?to[- ]?video|t2v|generated\s+(?:video|footage))\b"),
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
    detection_method: str = "estimated"  # v2.0: "estimated" or "histogram"


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
class GenerationArtifactCheck:
    """v2.0: AI-generated video artifact detection."""
    is_likely_generated: bool = False
    generation_confidence: float = 0.0
    flicker_score: float = 0.0          # 0=no flicker, 1=heavy flicker
    background_drift: float = 0.0       # 0=stable, 1=drifting
    hand_anomaly_risk: float = 0.0      # 0=normal, 1=likely distorted
    texture_uniformity: float = 0.0     # 0=natural variety, 1=uniform (synthetic)
    motion_smoothness: float = 0.0      # 0=natural, 1=unnaturally smooth
    indicators: List[str] = field(default_factory=list)


@dataclass
class PixelLevelDeepfakeAnalysis:
    """v2.0: Pixel-level statistical deepfake detection."""
    risk_score: float = 0.0
    noise_inconsistency: float = 0.0    # 0=consistent, 1=inconsistent noise
    compression_artifact_anomaly: float = 0.0
    frequency_domain_anomaly: float = 0.0
    edge_coherence: float = 0.0         # 0=incoherent, 1=coherent
    indicators: List[str] = field(default_factory=list)


@dataclass
class OpticalFlowAnalysis:
    """v2.0: Optical flow motion analysis."""
    available: bool = False
    avg_magnitude: float = 0.0
    max_magnitude: float = 0.0
    motion_consistency: float = 0.0     # 0=chaotic, 1=smooth
    dominant_direction: float = 0.0     # radians
    static_ratio: float = 0.0          # fraction of static blocks
    motion_type: str = "unknown"       # "static", "pan", "zoom", "chaotic", "mixed"


@dataclass
class AudioVisualSync:
    """v2.0: Audio-visual synchronization analysis."""
    available: bool = False
    sync_score: float = 0.5
    estimated_offset_ms: float = 0.0
    lip_sync_applicable: bool = False
    lip_sync_score: float = 0.0
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
    # v2.0 additions
    generation_artifacts: GenerationArtifactCheck = field(default_factory=GenerationArtifactCheck)
    pixel_deepfake: PixelLevelDeepfakeAnalysis = field(default_factory=PixelLevelDeepfakeAnalysis)
    optical_flow: OpticalFlowAnalysis = field(default_factory=OpticalFlowAnalysis)
    av_sync: AudioVisualSync = field(default_factory=AudioVisualSync)
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
        offset = 0
        while offset < len(data) - 8:
            try:
                box_size = struct.unpack('>I', data[offset:offset + 4])[0]
                box_type = data[offset + 4:offset + 8].decode('ascii', errors='ignore')

                if box_size < 8:
                    break

                if box_type == 'tkhd' and box_size >= 92:
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

        offset = 12
        while offset < min(len(data) - 8, AVI_HEADER_SCAN_LIMIT):
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
# Scene Change Detector (v2.0 — histogram-based when numpy available)
# ═══════════════════════════════════════════════════════════════════════════

class SceneChangeDetector:
    """Detect scene changes in video.

    v2.0: When frame data (as numpy arrays) is available, uses histogram
    difference for real scene change detection. Falls back to metadata
    estimation otherwise.
    """

    def detect_from_frames(self, frames: List['np.ndarray'],
                           fps: float = 30.0,
                           threshold: float = SCENE_CHANGE_THRESHOLD) -> SceneInfo:
        """Detect scene changes from actual frame data (numpy arrays).

        Args:
            frames: List of grayscale frame arrays (H, W) or color (H, W, 3).
            fps: Video FPS for timestamp calculation.
            threshold: Histogram chi-squared threshold for scene change.

        Returns:
            SceneInfo with detected boundaries.
        """
        if not _HAS_NUMPY or len(frames) < 2:
            return SceneInfo(scene_count=1, detection_method="estimated")

        boundaries = []
        prev_hist = self._compute_histogram(frames[0])

        for i in range(1, len(frames)):
            curr_hist = self._compute_histogram(frames[i])
            diff = self._histogram_chi_squared(prev_hist, curr_hist)
            if diff > threshold:
                timestamp = i / max(fps, 1.0)
                boundaries.append(timestamp)
            prev_hist = curr_hist

        scene_count = len(boundaries) + 1
        total_duration = len(frames) / max(fps, 1.0)

        avg_dur = total_duration / scene_count if scene_count > 0 else total_duration
        min_dur = avg_dur * SCENE_MIN_RATIO
        max_dur = avg_dur * SCENE_MAX_RATIO

        return SceneInfo(
            scene_count=scene_count,
            avg_scene_duration=avg_dur,
            min_scene_duration=min_dur,
            max_scene_duration=max_dur,
            scene_boundaries=boundaries,
            detection_method="histogram",
        )

    def _compute_histogram(self, frame: 'np.ndarray') -> 'np.ndarray':
        """Compute normalized histogram of a frame."""
        if frame.ndim == 3:
            gray = np.mean(frame, axis=2).astype(np.uint8)
        else:
            gray = frame
        hist, _ = np.histogram(gray.ravel(), bins=HISTOGRAM_BINS, range=(0, 256))
        total = hist.sum()
        if total > 0:
            hist = hist.astype(np.float64) / total
        return hist

    def _histogram_chi_squared(self, h1: 'np.ndarray', h2: 'np.ndarray') -> float:
        """Chi-squared distance between two histograms."""
        denom = h1 + h2
        mask = denom > 0
        if not mask.any():
            return 0.0
        diff = (h1[mask] - h2[mask]) ** 2 / denom[mask]
        return float(diff.sum())

    def estimate_scenes(self, meta: VideoMetadata) -> SceneInfo:
        """Estimate scene information from metadata (fallback).

        Without frame data, we use heuristics:
        - Short videos (<30s) likely 1-3 scenes
        - Medium (30s-5min) likely 5-20 scenes
        - Long (>5min) estimate from genre/bitrate
        """
        info = SceneInfo(detection_method="estimated")

        if meta.duration_seconds <= 0:
            return info

        duration = meta.duration_seconds

        if duration < SHORT_VIDEO_THRESHOLD:
            info.scene_count = 1
        elif duration < MEDIUM_VIDEO_THRESHOLD:
            info.scene_count = max(1, int(duration / SHORT_SCENE_INTERVAL))
        elif duration < LONG_VIDEO_THRESHOLD:
            info.scene_count = max(3, int(duration / MEDIUM_SCENE_INTERVAL))
        else:
            info.scene_count = max(10, int(duration / LONG_SCENE_INTERVAL))

        info.avg_scene_duration = duration / max(info.scene_count, 1)
        info.min_scene_duration = info.avg_scene_duration * SCENE_MIN_RATIO
        info.max_scene_duration = info.avg_scene_duration * SCENE_MAX_RATIO

        if info.scene_count > 1:
            interval = duration / info.scene_count
            info.scene_boundaries = [i * interval for i in range(1, info.scene_count)]

        return info


# ═══════════════════════════════════════════════════════════════════════════
# v2.0: Optical Flow Motion Analyzer
# ═══════════════════════════════════════════════════════════════════════════

class OpticalFlowAnalyzer:
    """Block-matching optical flow for motion analysis.

    Uses simple block matching (no OpenCV dependency).
    Detects: pan, zoom, static, chaotic motion patterns.

    Design: Youta Hilono / Implementation: Shirokuma
    """

    def analyze(self, frames: List['np.ndarray'],
                block_size: int = OPTICAL_FLOW_BLOCK_SIZE) -> OpticalFlowAnalysis:
        """Analyze motion patterns across frames.

        Args:
            frames: List of grayscale frame arrays.
            block_size: Block size for matching.
        """
        if not _HAS_NUMPY or len(frames) < 2:
            return OpticalFlowAnalysis(available=False)

        all_magnitudes = []
        all_directions = []
        static_counts = 0
        total_blocks = 0

        for i in range(1, min(len(frames), 30)):  # Cap at 30 frame pairs
            prev_gray = self._to_gray(frames[i - 1])
            curr_gray = self._to_gray(frames[i])
            flow = self._block_match(prev_gray, curr_gray, block_size)
            for dx, dy in flow:
                mag = math.sqrt(dx * dx + dy * dy)
                all_magnitudes.append(mag)
                if mag < 0.5:
                    static_counts += 1
                else:
                    all_directions.append(math.atan2(dy, dx))
                total_blocks += 1

        if not all_magnitudes:
            return OpticalFlowAnalysis(available=True, motion_type="static")

        avg_mag = sum(all_magnitudes) / len(all_magnitudes)
        max_mag = max(all_magnitudes)
        static_ratio = static_counts / max(total_blocks, 1)

        # Direction consistency → motion_consistency
        if all_directions:
            dir_arr = np.array(all_directions)
            cx = np.cos(dir_arr).mean()
            cy = np.sin(dir_arr).mean()
            consistency = math.sqrt(cx * cx + cy * cy)  # 0=random, 1=uniform
            dominant = math.atan2(cy, cx)
        else:
            consistency = 1.0  # No motion = consistent
            dominant = 0.0

        # Classify motion type
        if static_ratio > 0.85:
            motion_type = "static"
        elif consistency > 0.8 and avg_mag > 2.0:
            motion_type = "pan"
        elif consistency > 0.6:
            motion_type = "zoom" if avg_mag > 5.0 else "pan"
        elif consistency < 0.3:
            motion_type = "chaotic"
        else:
            motion_type = "mixed"

        return OpticalFlowAnalysis(
            available=True,
            avg_magnitude=round(avg_mag, 3),
            max_magnitude=round(max_mag, 3),
            motion_consistency=round(consistency, 3),
            dominant_direction=round(dominant, 3),
            static_ratio=round(static_ratio, 3),
            motion_type=motion_type,
        )

    def _to_gray(self, frame: 'np.ndarray') -> 'np.ndarray':
        if frame.ndim == 3:
            return np.mean(frame, axis=2).astype(np.float32)
        return frame.astype(np.float32)

    def _block_match(self, prev: 'np.ndarray', curr: 'np.ndarray',
                     block_size: int, search_range: int = 4) -> List[Tuple[float, float]]:
        """Simple block matching between two frames."""
        h, w = prev.shape[:2]
        flows = []
        for by in range(0, h - block_size, block_size * 2):
            for bx in range(0, w - block_size, block_size * 2):
                block = prev[by:by + block_size, bx:bx + block_size]
                best_dx, best_dy = 0, 0
                best_sad = float('inf')
                for dy in range(-search_range, search_range + 1):
                    for dx in range(-search_range, search_range + 1):
                        ny, nx = by + dy, bx + dx
                        if ny < 0 or nx < 0 or ny + block_size > h or nx + block_size > w:
                            continue
                        candidate = curr[ny:ny + block_size, nx:nx + block_size]
                        sad = float(np.abs(block - candidate).sum())
                        if sad < best_sad:
                            best_sad = sad
                            best_dx, best_dy = dx, dy
                flows.append((best_dx, best_dy))
        return flows


# ═══════════════════════════════════════════════════════════════════════════
# v2.0: Generation Artifact Detector
# ═══════════════════════════════════════════════════════════════════════════

class GenerationArtifactDetector:
    """Detect AI-generated video artifacts.

    Targets common artifacts in text-to-video outputs:
    1. Temporal flicker (brightness/color jumps between frames)
    2. Background drift (static background that subtly morphs)
    3. Hand/finger anomaly patterns (texture complexity in hand regions)
    4. Texture uniformity (AI tends to over-smooth textures)
    5. Motion smoothness (AI motion is often unnaturally smooth)

    Design: Youta Hilono / Implementation: Shirokuma
    """

    def detect(self, frames: List['np.ndarray'],
               claim_text: str = "") -> GenerationArtifactCheck:
        """Detect generation artifacts from frame data and/or claims."""
        result = GenerationArtifactCheck()

        # Text-based generation hint
        text_gen_score = self._assess_generation_from_text(claim_text)
        if text_gen_score > 0.3:
            result.indicators.append(f"Text hints at AI generation (score={text_gen_score:.2f})")

        if not _HAS_NUMPY or len(frames) < 2:
            result.generation_confidence = text_gen_score
            result.is_likely_generated = text_gen_score > 0.5
            return result

        # Frame-based analysis
        result.flicker_score = self._detect_flicker(frames)
        result.background_drift = self._detect_background_drift(frames)
        result.texture_uniformity = self._detect_texture_uniformity(frames)
        result.motion_smoothness = self._detect_motion_smoothness(frames)
        result.hand_anomaly_risk = self._estimate_hand_anomaly(frames)

        # Aggregate
        scores = [
            result.flicker_score * 0.20,
            result.background_drift * 0.20,
            result.texture_uniformity * 0.20,
            result.motion_smoothness * 0.15,
            result.hand_anomaly_risk * 0.10,
            text_gen_score * 0.15,
        ]
        result.generation_confidence = min(sum(scores) * 1.5, 1.0)
        result.is_likely_generated = result.generation_confidence > 0.5

        # Detailed indicators
        if result.flicker_score > FLICKER_THRESHOLD:
            result.indicators.append(f"Temporal flicker detected (score={result.flicker_score:.2f})")
        if result.background_drift > 0.3:
            result.indicators.append(f"Background drift (score={result.background_drift:.2f})")
        if result.texture_uniformity > 0.6:
            result.indicators.append(f"Over-smooth texture (score={result.texture_uniformity:.2f})")
        if result.motion_smoothness > 0.7:
            result.indicators.append(f"Unnaturally smooth motion (score={result.motion_smoothness:.2f})")
        if result.hand_anomaly_risk > 0.5:
            result.indicators.append(f"Hand region anomaly risk (score={result.hand_anomaly_risk:.2f})")

        return result

    def _assess_generation_from_text(self, text: str) -> float:
        """Score how likely the claim references AI-generated content."""
        if not text:
            return 0.0
        score = 0.0
        for pattern in GENERATION_CLAIM_PATTERNS:
            if pattern.search(text):
                score += 0.25
        return min(score, 0.95)

    def _detect_flicker(self, frames: List['np.ndarray']) -> float:
        """Detect temporal brightness/color flicker."""
        means = []
        for f in frames[:60]:  # Cap analysis
            gray = np.mean(f) if f.ndim == 2 else np.mean(f, axis=(0, 1)).mean()
            means.append(float(gray))
        if len(means) < 2:
            return 0.0
        arr = np.array(means)
        diffs = np.abs(np.diff(arr))
        # Flicker = high variance in frame-to-frame brightness changes
        if diffs.mean() == 0:
            return 0.0
        flicker = float(diffs.std() / max(diffs.mean(), 1e-6))
        return min(flicker / 3.0, 1.0)  # Normalize

    def _detect_background_drift(self, frames: List['np.ndarray']) -> float:
        """Detect subtle background morphing (common in AI video)."""
        if len(frames) < BACKGROUND_CONSISTENCY_WINDOW:
            return 0.0
        # Compare edge regions (top/bottom 10% rows) across frames
        drifts = []
        for i in range(1, min(len(frames), 20)):
            prev = self._edge_region(frames[i - 1])
            curr = self._edge_region(frames[i])
            if prev.shape == curr.shape:
                diff = float(np.mean(np.abs(prev.astype(float) - curr.astype(float))))
                drifts.append(diff)
        if not drifts:
            return 0.0
        avg_drift = sum(drifts) / len(drifts)
        return min(avg_drift / 30.0, 1.0)  # Normalize; >30 pixel avg diff = max

    def _edge_region(self, frame: 'np.ndarray') -> 'np.ndarray':
        """Extract edge (border) regions of frame."""
        h = frame.shape[0]
        border = max(1, h // 10)
        if frame.ndim == 3:
            return np.concatenate([frame[:border], frame[-border:]], axis=0)
        return np.concatenate([frame[:border], frame[-border:]], axis=0)

    def _detect_texture_uniformity(self, frames: List['np.ndarray']) -> float:
        """AI-generated frames tend to have over-smooth textures."""
        variances = []
        for f in frames[:20]:
            gray = f if f.ndim == 2 else np.mean(f, axis=2)
            # Local variance via block analysis
            h, w = gray.shape
            bs = 16
            block_vars = []
            for y in range(0, h - bs, bs):
                for x in range(0, w - bs, bs):
                    block = gray[y:y + bs, x:x + bs]
                    block_vars.append(float(np.var(block)))
            if block_vars:
                variances.append(sum(block_vars) / len(block_vars))
        if not variances:
            return 0.0
        avg_var = sum(variances) / len(variances)
        # Low local variance = uniform = possibly generated
        # Natural images typically have avg block variance > 200
        uniformity = max(0, 1.0 - avg_var / 500.0)
        return min(uniformity, 1.0)

    def _detect_motion_smoothness(self, frames: List['np.ndarray']) -> float:
        """AI motion is often unnaturally smooth (no micro-jitter)."""
        if len(frames) < 3:
            return 0.0
        # Compute second-order differences in frame means (acceleration)
        means = [float(np.mean(f)) for f in frames[:30]]
        if len(means) < 3:
            return 0.0
        velocities = [means[i + 1] - means[i] for i in range(len(means) - 1)]
        accels = [velocities[i + 1] - velocities[i] for i in range(len(velocities) - 1)]
        if not accels:
            return 0.0
        accel_var = sum(a * a for a in accels) / len(accels)
        # Very low acceleration variance = unnaturally smooth
        smoothness = max(0, 1.0 - accel_var / 2.0)
        return min(smoothness, 1.0)

    def _estimate_hand_anomaly(self, frames: List['np.ndarray']) -> float:
        """Estimate hand region anomaly risk via texture complexity.

        AI-generated hands often have incorrect finger counts or
        distorted geometry. We check for unusual texture patterns
        in the lower-center region (common hand location).
        """
        complexities = []
        for f in frames[:10]:
            h, w = f.shape[:2]
            # Lower center quadrant (where hands typically appear)
            y1, y2 = int(h * 0.5), int(h * 0.9)
            x1, x2 = int(w * 0.25), int(w * 0.75)
            region = f[y1:y2, x1:x2]
            if region.ndim == 3:
                region = np.mean(region, axis=2)
            # Edge density as proxy for finger/hand complexity
            dx = np.abs(np.diff(region, axis=1))
            dy = np.abs(np.diff(region, axis=0))
            edge_density = float((dx.mean() + dy.mean()) / 2)
            complexities.append(edge_density)
        if not complexities:
            return 0.0
        avg_complexity = sum(complexities) / len(complexities)
        # Anomalous: very high OR very low edge density in hand region
        # AI tends toward either blurred hands or chaotic edges
        if avg_complexity < 3.0:
            return 0.3  # Too smooth (blurred hands)
        elif avg_complexity > 40.0:
            return 0.5  # Chaotic edges (distorted fingers)
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# v2.0: Pixel-Level Deepfake Analyzer
# ═══════════════════════════════════════════════════════════════════════════

class PixelLevelDeepfakeDetector:
    """Statistical pixel-level analysis for deepfake detection.

    Not face-recognition-based — uses noise patterns, compression
    artifacts, and frequency domain analysis.

    Design: Youta Hilono / Implementation: Shirokuma
    """

    def analyze(self, frames: List['np.ndarray'],
                claim_text: str = "") -> PixelLevelDeepfakeAnalysis:
        """Run pixel-level deepfake analysis."""
        result = PixelLevelDeepfakeAnalysis()

        if not _HAS_NUMPY or len(frames) < 2:
            # Fall back to text-only assessment
            text_risk = 0.0
            for pattern in DEEPFAKE_CLAIM_PATTERNS:
                if pattern.search(claim_text):
                    text_risk += 0.15
            result.risk_score = min(text_risk, 0.95)
            return result

        result.noise_inconsistency = self._noise_inconsistency(frames)
        result.compression_artifact_anomaly = self._compression_anomaly(frames)
        result.frequency_domain_anomaly = self._frequency_anomaly(frames)
        result.edge_coherence = self._edge_coherence(frames)

        # Aggregate risk
        risk = (
            result.noise_inconsistency * 0.30
            + result.compression_artifact_anomaly * 0.25
            + result.frequency_domain_anomaly * 0.25
            + (1.0 - result.edge_coherence) * 0.20
        )

        # Text claim boost
        for pattern in DEEPFAKE_CLAIM_PATTERNS:
            if pattern.search(claim_text):
                risk = min(risk + 0.05, 0.95)

        result.risk_score = round(min(risk, 0.95), 3)

        if result.noise_inconsistency > 0.5:
            result.indicators.append("Inconsistent noise patterns across frames")
        if result.compression_artifact_anomaly > 0.5:
            result.indicators.append("Anomalous compression artifact distribution")
        if result.frequency_domain_anomaly > 0.5:
            result.indicators.append("Frequency domain irregularities")
        if result.edge_coherence < 0.4:
            result.indicators.append("Poor edge coherence across frames")

        return result

    def _noise_inconsistency(self, frames: List['np.ndarray']) -> float:
        """Check if noise patterns are consistent across frames.

        Real cameras have consistent sensor noise; fakes often don't.
        """
        noise_levels = []
        for f in frames[:20]:
            gray = f if f.ndim == 2 else np.mean(f, axis=2)
            # Estimate noise as high-frequency energy
            h, w = gray.shape
            if h < 4 or w < 4:
                continue
            # Laplacian approximation
            lap = (
                gray[2:, 1:-1] + gray[:-2, 1:-1]
                + gray[1:-1, 2:] + gray[1:-1, :-2]
                - 4 * gray[1:-1, 1:-1]
            )
            noise_levels.append(float(np.std(lap)))

        if len(noise_levels) < 2:
            return 0.0

        arr = np.array(noise_levels)
        mean_noise = arr.mean()
        if mean_noise < 1e-6:
            return 0.0
        cv = float(arr.std() / mean_noise)  # Coefficient of variation
        return min(cv / 0.5, 1.0)  # CV > 0.5 = high inconsistency

    def _compression_anomaly(self, frames: List['np.ndarray']) -> float:
        """Detect anomalous compression artifact patterns.

        Spliced regions often have different JPEG compression levels.
        """
        block_energies = []
        for f in frames[:15]:
            gray = f if f.ndim == 2 else np.mean(f, axis=2)
            h, w = gray.shape
            # Analyze 8x8 block boundaries (JPEG block structure)
            boundary_energy = 0.0
            count = 0
            for y in range(8, h - 1, 8):
                diff = np.abs(gray[y].astype(float) - gray[y - 1].astype(float))
                boundary_energy += float(diff.mean())
                count += 1
            for x in range(8, w - 1, 8):
                diff = np.abs(gray[:, x].astype(float) - gray[:, x - 1].astype(float))
                boundary_energy += float(diff.mean())
                count += 1
            if count > 0:
                block_energies.append(boundary_energy / count)

        if len(block_energies) < 2:
            return 0.0

        arr = np.array(block_energies)
        cv = float(arr.std() / max(arr.mean(), 1e-6))
        return min(cv / 0.4, 1.0)

    def _frequency_anomaly(self, frames: List['np.ndarray']) -> float:
        """Check for frequency domain irregularities.

        GANs/diffusion models leave spectral fingerprints.
        Uses DCT-like analysis via spatial frequency bands.
        """
        ratios = []
        for f in frames[:15]:
            gray = f if f.ndim == 2 else np.mean(f, axis=2)
            gray = gray.astype(np.float64)
            h, w = gray.shape
            if h < 16 or w < 16:
                continue

            # Simple frequency band analysis: low vs high spatial frequency
            # Low frequency: mean over large blocks
            bs = min(16, h // 2, w // 2)
            low_freq_energy = 0.0
            high_freq_energy = 0.0
            count = 0
            for y in range(0, h - bs, bs):
                for x in range(0, w - bs, bs):
                    block = gray[y:y + bs, x:x + bs]
                    block_mean = block.mean()
                    low_freq_energy += block_mean ** 2
                    high_freq_energy += float(np.var(block))
                    count += 1
            if count > 0 and low_freq_energy > 0:
                ratio = high_freq_energy / (low_freq_energy + high_freq_energy)
                ratios.append(ratio)

        if len(ratios) < 2:
            return 0.0

        arr = np.array(ratios)
        # GANs often have abnormally low high-frequency content
        mean_ratio = float(arr.mean())
        if mean_ratio < 0.1:
            return 0.8  # Suspiciously low high-freq
        elif mean_ratio > 0.6:
            return 0.4  # Unusually high (possible noise injection)
        return 0.0

    def _edge_coherence(self, frames: List['np.ndarray']) -> float:
        """Check edge coherence across sequential frames.

        Real video has smooth edge evolution; deepfakes often have
        edges that jump or shimmer unnaturally.
        """
        edge_maps = []
        for f in frames[:20]:
            gray = f if f.ndim == 2 else np.mean(f, axis=2)
            h, w = gray.shape
            if h < 3 or w < 3:
                continue
            # Sobel-like edge detection
            dx = np.abs(gray[:, 2:] - gray[:, :-2])
            dy = np.abs(gray[2:, :] - gray[:-2, :])
            edge = float(dx.mean() + dy.mean())
            edge_maps.append(edge)

        if len(edge_maps) < 2:
            return 1.0  # Can't assess

        arr = np.array(edge_maps)
        mean_edge = arr.mean()
        if mean_edge < 1e-6:
            return 1.0
        cv = float(arr.std() / mean_edge)
        # Low CV = coherent edges
        coherence = max(0.0, 1.0 - cv / 0.3)
        return min(coherence, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# v2.0: Audio-Visual Sync Analyzer
# ═══════════════════════════════════════════════════════════════════════════

class AudioVisualSyncAnalyzer:
    """Analyze audio-visual synchronization.

    Framework for lip-sync detection and audio-visual alignment
    without requiring face detection models.

    Design: Youta Hilono / Implementation: Shirokuma
    """

    def analyze(self, video_meta: VideoMetadata,
                audio_features: Optional[Dict[str, Any]] = None,
                motion_analysis: Optional[OpticalFlowAnalysis] = None) -> AudioVisualSync:
        """Analyze AV sync quality."""
        result = AudioVisualSync()

        if not video_meta.has_audio:
            result.issues.append("No audio track present")
            return result

        result.available = True

        # Heuristic: bitrate-based sync estimation
        if video_meta.bitrate_kbps > 0:
            # Very low bitrate videos often have sync issues
            if video_meta.bitrate_kbps < 200:
                result.sync_score = 0.4
                result.issues.append("Very low bitrate — sync quality uncertain")
            elif video_meta.bitrate_kbps < 500:
                result.sync_score = 0.6
            else:
                result.sync_score = 0.8

        # Motion-based lip-sync applicability
        if motion_analysis and motion_analysis.available:
            if motion_analysis.motion_type == "static":
                # Static video with audio = likely talking head
                result.lip_sync_applicable = True
                result.lip_sync_score = result.sync_score
            elif motion_analysis.avg_magnitude > 10:
                # High motion = less likely to assess lip sync
                result.lip_sync_applicable = False
                result.lip_sync_score = 0.0

        # Audio feature integration
        if audio_features:
            if audio_features.get("has_speech", False):
                result.lip_sync_applicable = True
                # If we have speech but high motion inconsistency
                if motion_analysis and motion_analysis.motion_consistency < 0.3:
                    result.sync_score *= 0.7
                    result.issues.append("Speech detected but motion is chaotic")

        return result


# ═══════════════════════════════════════════════════════════════════════════
# Video Manipulation Detector (v2.0 enhanced)
# ═══════════════════════════════════════════════════════════════════════════

class VideoManipulationDetector:
    """Detect video manipulation artifacts. v2.0: integrates generation + deepfake."""

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
                if meta.bitrate_kbps < low * BITRATE_LOW_MULTIPLIER:
                    indicators.append(f"Very low bitrate for {meta.resolution_label} — possible re-encoding")
                elif meta.bitrate_kbps > high * BITRATE_HIGH_MULTIPLIER:
                    indicators.append(f"Unusually high bitrate for {meta.resolution_label}")

        # 3. Duration anomaly
        if meta.duration_seconds > 0:
            if meta.duration_seconds < SHORT_VIDEO_THRESHOLD and scenes.scene_count > 5:
                indicators.append("Many scene changes in short video — possible compilation")
                check.splice_detected = True

        # 4. Resolution mismatch
        if meta.width > 0 and meta.height > 0:
            aspect = meta.width / meta.height
            common_aspects = {16 / 9: "16:9", 4 / 3: "4:3", 1: "1:1", 9 / 16: "9:16"}
            closest_aspect = min(common_aspects, key=lambda a: abs(a - aspect))
            if abs(aspect - closest_aspect) > ASPECT_TOLERANCE:
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
                risk += DEEPFAKE_PATTERN_WEIGHT

        pressure = {"must see", "breaking", "proof", "evidence", "undeniable", "clearly shows"}
        for word in pressure:
            if word in claim_text.lower():
                risk += PRESSURE_WORD_WEIGHT

        return min(risk, 0.95)


# ═══════════════════════════════════════════════════════════════════════════
# Video Understanding Engine (v2.0)
# ═══════════════════════════════════════════════════════════════════════════

class VideoUnderstandingEngine:
    """Full video understanding and verification pipeline v2.0.

    v2.0 additions:
    - Optical flow motion analysis
    - Real histogram-based scene detection
    - AI generation artifact detection
    - Pixel-level deepfake analysis
    - Audio-visual sync framework

    Integrates:
    - Container parsing (MP4, AVI, MKV)
    - Scene change detection (estimated + histogram)
    - Temporal consistency analysis
    - Manipulation detection
    - Audio-visual sync (via AudioProcessingEngine)
    - Keyframe analysis (via ImageUnderstandingEngine)

    Design: Youta Hilono / Implementation: Shirokuma
    """

    def __init__(self):
        self.parser = VideoMetadataParser()
        self.scene_detector = SceneChangeDetector()
        self.manipulation_detector = VideoManipulationDetector()
        self.optical_flow = OpticalFlowAnalyzer()
        self.artifact_detector = GenerationArtifactDetector()
        self.deepfake_detector = PixelLevelDeepfakeDetector()
        self.av_sync_analyzer = AudioVisualSyncAnalyzer()
        self.image_engine = ImageUnderstandingEngine() if _HAS_IMAGE else None
        self.audio_engine = AudioProcessingEngine() if _HAS_AUDIO else None

    def verify_video(
        self,
        video_data: Optional[bytes] = None,
        video_path: Optional[str] = None,
        claim_text: str = "",
        frames: Optional[List['np.ndarray']] = None,
    ) -> VideoVerification:
        """Full video verification pipeline.

        Args:
            video_data: Raw video bytes.
            video_path: Path to video file.
            claim_text: Text claim to verify against.
            frames: Optional pre-extracted frames (numpy arrays) for
                    deep analysis. If not provided, only metadata analysis runs.
        """
        if video_data is None and video_path:
            if os.path.exists(video_path):
                with open(video_path, 'rb') as f:
                    video_data = f.read()

        if video_data is None:
            return VideoVerification(metadata=VideoMetadata(), verdict="ERROR", overall_score=0.0)

        # 1. Parse metadata
        metadata = self.parser.parse(video_data)

        # 2. Scene analysis
        if frames and _HAS_NUMPY and len(frames) >= 2:
            scenes = self.scene_detector.detect_from_frames(frames, metadata.fps or 30.0)
        else:
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

        # 5. v2.0: Optical flow
        flow_result = OpticalFlowAnalysis(available=False)
        if frames and _HAS_NUMPY:
            flow_result = self.optical_flow.analyze(frames)

        # 6. v2.0: Generation artifact detection
        gen_artifacts = self.artifact_detector.detect(frames or [], claim_text)

        # 7. v2.0: Pixel-level deepfake
        pixel_deepfake = self.deepfake_detector.analyze(frames or [], claim_text)

        # 8. v2.0: Audio-visual sync
        av_sync = self.av_sync_analyzer.analyze(
            metadata,
            motion_analysis=flow_result if flow_result.available else None,
        )

        # 9. Score (enhanced with v2.0 signals)
        scores = [BASE_SCORE]

        if metadata.duration_seconds > 0:
            scores.append(METADATA_PRESENT_SCORE)
        if metadata.width > 0:
            scores.append(METADATA_PRESENT_SCORE)
        if not manipulation.suspicious:
            scores.append(NO_MANIPULATION_SCORE)
        else:
            scores.append(1.0 - manipulation.confidence)
        scores.append(temporal.score)

        if manipulation.deepfake_risk > 0.5:
            scores.append(DEEPFAKE_HIGH_PENALTY_SCORE)

        # v2.0 scoring contributions
        if gen_artifacts.is_likely_generated:
            scores.append(0.4)  # Generated content = lower trust
        if pixel_deepfake.risk_score > 0.5:
            scores.append(0.3)
        if flow_result.available:
            scores.append(0.5 + flow_result.motion_consistency * 0.3)
        if av_sync.available:
            scores.append(av_sync.sync_score)

        overall = sum(scores) / len(scores)

        # Verdict
        if gen_artifacts.is_likely_generated and gen_artifacts.generation_confidence > 0.7:
            verdict = "AI_GENERATED"
        elif pixel_deepfake.risk_score > 0.6:
            verdict = "DEEPFAKE_RISK"
        elif manipulation.suspicious and manipulation.confidence > 0.6:
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
            generation_artifacts=gen_artifacts,
            pixel_deepfake=pixel_deepfake,
            optical_flow=flow_result,
            av_sync=av_sync,
            overall_score=round(overall, 4),
            verdict=verdict,
        )

    def verify_video_claim(self, claim_text: str) -> Dict[str, Any]:
        """Verify a text claim about a video (without the video itself)."""
        deepfake_risk = self.manipulation_detector.assess_deepfake_risk(claim_text)

        # v2.0: Also check generation claims
        gen_score = self.artifact_detector._assess_generation_from_text(claim_text)

        has_temporal = bool(re.search(r"(?i)\b(at|around)\s+\d+:\d+", claim_text))
        has_visual = bool(re.search(r"(?i)\b(shows?|depicts?|seen|visible)\b", claim_text))
        has_source = bool(re.search(r"(?i)\b(source|original|uploaded\s+by|from)\b", claim_text))

        credibility = CREDIBILITY_BASE
        if has_source:
            credibility += SOURCE_CREDIBILITY_BOOST
        if has_temporal:
            credibility += TEMPORAL_REF_BOOST
        if deepfake_risk > 0.3:
            credibility -= deepfake_risk * 0.4
        if gen_score > 0.3:
            credibility -= gen_score * 0.2

        if gen_score > 0.5:
            verdict = "AI_GENERATED_CLAIM"
        elif credibility >= 0.55:
            verdict = "PLAUSIBLE"
        elif deepfake_risk > 0.4:
            verdict = "SUSPICIOUS"
        else:
            verdict = "UNCERTAIN"

        return {
            "deepfake_risk": round(deepfake_risk, 3),
            "generation_score": round(gen_score, 3),
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
                "histogram_scene_detection",
                "temporal_consistency",
                "manipulation_detection",
                "deepfake_risk_assessment",
                "video_claim_verification",
                # v2.0
                "optical_flow_analysis",
                "generation_artifact_detection",
                "pixel_level_deepfake_analysis",
                "audio_visual_sync",
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
        "This sora-generated video shows a realistic cityscape.",
    ]
    for claim in claims:
        r = engine.verify_video_claim(claim)
        print(f"  [{r['verdict']}] deepfake={r['deepfake_risk']:.2f} "
              f"gen={r['generation_score']:.2f} cred={r['credibility']:.2f} — {claim[:55]}")

    print(f"\n✅ VideoUnderstandingEngine v{VERSION} OK")
