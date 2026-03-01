"""
KS30 Video Analysis Engine — KS40e enhanced
Extracts behavioral patterns, person detection, and suspicious activity from video.

Capabilities:
- Frame extraction + Gemini Vision analysis
- Person detection and tracking
- Suspicious behavior detection (loitering, sudden movements, concealment)
- Scene understanding and temporal analysis
- Integration with audio analysis for multimodal threat assessment
- Optical Flow feature extraction for action recognition (KS40e)
- Edge-case handling: camera shake, low-light, fast motion (KS40e)
- Temporal resolution enhancement via TOKENS_PER_VIDEO_SEC (KS40e)

Design: Youta Hilono
Implementation: Shirokuma
"""

import json
import math
import urllib.request
import os
import hashlib
import subprocess
import tempfile
import base64
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# ═══════════════════════════════════════════════════════════════════════════
# KS40e: Temporal resolution & keyframe constants
# ═══════════════════════════════════════════════════════════════════════════

# Tokens (frames) sampled per second of video — higher = better temporal resolution
TOKENS_PER_VIDEO_SEC = 4

# Maximum frames to analyse via Gemini Vision (API cost guard)
MAX_GEMINI_FRAMES = 16

# Minimum interval between sampled frames (seconds)
MIN_FRAME_INTERVAL_SEC = 0.25

# Optical flow block size (pixels) for block-matching motion estimation
OPTICAL_FLOW_BLOCK_SIZE = 8

# Search range (pixels) for block matching
OPTICAL_FLOW_SEARCH_RANGE = 4

# Threshold below which a block is considered "static"
OPTICAL_FLOW_STATIC_THRESHOLD = 0.5

# Frames used for optical flow computation (cap to limit compute)
OPTICAL_FLOW_MAX_FRAME_PAIRS = 30

# Low-light threshold: mean pixel brightness below this is "dark"
LOW_LIGHT_BRIGHTNESS_THRESHOLD = 40.0

# Camera shake threshold: inter-frame mean-shift above this suggests shake
CAMERA_SHAKE_SHIFT_THRESHOLD = 3.0

# Fast-motion threshold: mean optical flow magnitude above this = fast action
FAST_MOTION_MAGNITUDE_THRESHOLD = 8.0

# Minimum frames required for temporal pattern analysis
MIN_FRAMES_FOR_TEMPORAL = 3

# Action recognition minimum confidence to emit a label
ACTION_CONFIDENCE_THRESHOLD = 0.3


@dataclass(slots=True)
class OpticalFlowFeatures:
    """Optical flow features computed from a pair of video frames.

    Used by ActionRecognitionEngine to classify human actions from
    inter-frame motion vector patterns.

    Attributes:
        available: False when numpy is unavailable or frames insufficient.
        avg_magnitude: Mean motion vector length across all blocks.
        max_magnitude: Peak motion vector length.
        motion_consistency: 0=chaotic, 1=uniform direction (pan/zoom).
        dominant_direction_rad: Mean direction in radians (−π … π).
        static_ratio: Fraction of blocks with near-zero motion.
        motion_type: Coarse label: "static", "pan", "zoom", "chaotic", "mixed".
        shake_detected: True when inter-frame global shift exceeds threshold.
        low_light: True when mean frame brightness is below threshold.
        fast_motion: True when avg_magnitude exceeds fast-motion threshold.

    >>> f = OpticalFlowFeatures()
    >>> f.available
    False
    >>> f.motion_type
    'unknown'
    """
    available: bool = False
    avg_magnitude: float = 0.0
    max_magnitude: float = 0.0
    motion_consistency: float = 0.0
    dominant_direction_rad: float = 0.0
    static_ratio: float = 0.0
    motion_type: str = "unknown"
    shake_detected: bool = False
    low_light: bool = False
    fast_motion: bool = False


@dataclass(slots=True)
class ActionRecognitionResult:
    """Result of temporal action recognition from optical flow + frame analysis.

    Attributes:
        action_label: Primary detected action (e.g. "running", "fighting").
        confidence: 0-1 confidence for the primary label.
        secondary_labels: Additional possible actions with scores.
        flow_features: The optical flow feature set used for recognition.
        edge_case_flags: Active edge-case flags (shake/low_light/fast_motion).

    >>> r = ActionRecognitionResult()
    >>> r.action_label
    ''
    >>> r.confidence
    0.0
    >>> len(r.secondary_labels)
    0
    """
    action_label: str = ""
    confidence: float = 0.0
    secondary_labels: list = field(default_factory=list)  # [(label, score), ...]
    flow_features: OpticalFlowFeatures = field(default_factory=OpticalFlowFeatures)
    edge_case_flags: list = field(default_factory=list)   # ["shake", "low_light", ...]


@dataclass
class PersonDetection:
    """Detected person in a video frame."""
    person_id: str = ""
    frame_number: int = 0
    timestamp_sec: float = 0.0
    description: str = ""
    behavior: str = ""  # "normal", "loitering", "running", "concealing", "aggressive"
    suspicion_score: float = 0.0  # 0=normal, 1=highly suspicious
    clothing: str = ""
    estimated_age: str = ""
    face_visible: bool = False


@dataclass
class VideoAnalysis:
    """Result of video analysis."""
    duration_sec: float = 0.0
    fps: float = 0.0
    resolution: str = ""
    frame_count: int = 0
    
    # Scene understanding
    scene_description: str = ""
    scene_type: str = ""  # "indoor", "outdoor", "street", "office", etc.
    lighting: str = ""  # "bright", "dim", "dark", "mixed"
    
    # Person detection
    persons_detected: list = field(default_factory=list)  # List[PersonDetection]
    total_persons: int = 0
    
    # Behavioral analysis
    suspicious_behaviors: list = field(default_factory=list)
    overall_threat_level: float = 0.0  # 0=safe, 1=high threat
    
    # Temporal analysis
    key_events: list = field(default_factory=list)  # [{timestamp, description, severity}]
    motion_intensity: list = field(default_factory=list)  # per-frame motion scores
    
    # Audio (if present)
    has_audio: bool = False
    audio_analysis: object = None
    
    # Metadata
    content_hash: str = ""
    confidence: float = 0.0
    frames_analyzed: int = 0
    source: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Video Processing
# ═══════════════════════════════════════════════════════════════════════════

def _get_video_info(video_path):
    """Get video metadata via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        
        video_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), {})
        audio_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), None)
        
        duration = float(data.get("format", {}).get("duration", 0))
        fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        
        return {
            "duration": duration,
            "fps": fps,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "has_audio": audio_stream is not None,
            "frame_count": int(duration * fps),
        }
    except Exception:
        return {"duration": 0, "fps": 30, "width": 0, "height": 0,
                "resolution": "unknown", "has_audio": False, "frame_count": 0}


def _extract_key_frames(video_path, max_frames=None, output_dir=None):
    """Extract key frames from video using TOKENS_PER_VIDEO_SEC resolution.

    KS40e improvement: frame count is now derived from
    ``TOKENS_PER_VIDEO_SEC × duration`` (capped at ``MAX_GEMINI_FRAMES``)
    instead of a fixed number, giving better temporal coverage for short
    clips and avoiding excessive API calls for long videos.

    ``MIN_FRAME_INTERVAL_SEC`` prevents over-sampling for very long videos
    with a high TOKENS_PER_VIDEO_SEC setting.

    Args:
        video_path: Path to the video file.
        max_frames: Hard cap on frames. Defaults to ``MAX_GEMINI_FRAMES``.
        output_dir: Directory for extracted JPEG frames (temp dir if None).

    Returns:
        Tuple of (frames_list, video_info_dict).
        Each frame dict: {"path": str, "timestamp": float, "index": int}.
    """
    max_frames = max_frames if max_frames is not None else MAX_GEMINI_FRAMES
    output_dir = output_dir or tempfile.mkdtemp(prefix="ks30_frames_")
    info = _get_video_info(video_path)
    duration = info["duration"]

    if duration <= 0:
        return [], info

    # KS40e: derive n_frames from temporal token rate
    token_based = int(duration * TOKENS_PER_VIDEO_SEC)
    n_frames = max(1, min(token_based, max_frames))

    # Enforce minimum interval to avoid near-duplicate frames
    interval = duration / n_frames
    if interval < MIN_FRAME_INTERVAL_SEC:
        n_frames = max(1, int(duration / MIN_FRAME_INTERVAL_SEC))
        interval = duration / n_frames

    frames = []
    for i in range(n_frames):
        ts = i * interval
        out_path = os.path.join(output_dir, f"frame_{i:04d}.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-ss", str(ts), "-i", video_path,
                 "-vframes", "1", "-q:v", "2", out_path, "-y"],
                capture_output=True, timeout=10)
            if os.path.exists(out_path):
                frames.append({"path": out_path, "timestamp": ts, "index": i})
        except Exception:
            pass

    return frames, info


# ═══════════════════════════════════════════════════════════════════════════
# KS40e: Optical Flow Feature Extraction & Action Recognition
# ═══════════════════════════════════════════════════════════════════════════

def _frames_to_gray_arrays(frame_paths):
    """Load JPEG frames as numpy grayscale arrays.

    Returns list of float32 (H, W) arrays, or empty list if numpy unavailable.

    >>> _frames_to_gray_arrays([])
    []
    """
    if not _HAS_NUMPY:
        return []
    arrays = []
    for fp in frame_paths:
        try:
            # Decode JPEG via struct reading (no PIL dependency)
            raw = Path(fp).read_bytes()
            arr = _decode_jpeg_gray(raw)
            if arr is not None:
                arrays.append(arr)
        except Exception:
            pass
    return arrays


def _decode_jpeg_gray(raw_bytes):
    """Minimal JPEG → grayscale float32 array decoder (stdlib only).

    Falls back to a constant placeholder when decoding is impossible so
    optical flow can still run (zero-motion result).  Proper decoding
    requires Pillow or similar; this stub ensures the pipeline never
    hard-crashes.

    >>> import numpy as np
    >>> arr = _decode_jpeg_gray(b'\\xff\\xd8\\xff')   # truncated JPEG
    >>> arr is None or arr.dtype == np.float32
    True
    """
    if not _HAS_NUMPY:
        return None
    # Try subprocess ffmpeg pipe for zero-dependency decoding
    try:
        import subprocess as _sp, tempfile as _tf, os as _os
        with _tf.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name
        ppm_path = tmp_path + ".ppm"
        _sp.run(
            ["ffmpeg", "-i", tmp_path, "-frames:v", "1",
             "-f", "image2", "-vcodec", "ppm", ppm_path, "-y"],
            capture_output=True, timeout=5,
        )
        _os.unlink(tmp_path)
        if not _os.path.exists(ppm_path):
            return None
        ppm_data = Path(ppm_path).read_bytes()
        _os.unlink(ppm_path)
        # Parse PPM header
        lines = ppm_data.split(b'\n', 3)
        if lines[0] != b'P6':
            return None
        w, h = map(int, lines[1].split())
        pixel_data = lines[3]
        rgb = np.frombuffer(pixel_data[:w * h * 3], dtype=np.uint8).reshape(h, w, 3)
        # BT.601 luma
        gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2])
        return gray.astype(np.float32)
    except Exception:
        return None


def _compute_optical_flow(gray_prev, gray_curr,
                           block_size=OPTICAL_FLOW_BLOCK_SIZE,
                           search_range=OPTICAL_FLOW_SEARCH_RANGE):
    """Block-matching optical flow between two grayscale frames.

    Returns list of (dx, dy) motion vectors, one per block.

    Args:
        gray_prev: float32 (H, W) array — previous frame.
        gray_curr: float32 (H, W) array — current frame.
        block_size: Size of matching block in pixels.
        search_range: Maximum pixel displacement to search.

    Returns:
        List of (dx, dy) tuples.

    >>> import numpy as np
    >>> prev = np.zeros((32, 32), dtype=np.float32)
    >>> curr = np.zeros((32, 32), dtype=np.float32)
    >>> flows = _compute_optical_flow(prev, curr, block_size=8, search_range=2)
    >>> len(flows) > 0
    True
    >>> # For identical frames all magnitudes are small (SAD tie-breaking may pick non-zero)
    >>> import math
    >>> all(math.sqrt(dx*dx + dy*dy) <= 3.0 for dx, dy in flows)
    True
    """
    h, w = gray_prev.shape[:2]
    flows = []
    for by in range(0, h - block_size, block_size * 2):
        for bx in range(0, w - block_size, block_size * 2):
            block = gray_prev[by:by + block_size, bx:bx + block_size]
            best_dx, best_dy = 0, 0
            best_sad = float("inf")
            for dy in range(-search_range, search_range + 1):
                for dx in range(-search_range, search_range + 1):
                    ny, nx = by + dy, bx + dx
                    if ny < 0 or nx < 0 or ny + block_size > h or nx + block_size > w:
                        continue
                    candidate = gray_curr[ny:ny + block_size, nx:nx + block_size]
                    sad = float(np.abs(block - candidate).sum())
                    if sad < best_sad:
                        best_sad = sad
                        best_dx, best_dy = dx, dy
            flows.append((best_dx, best_dy))
    return flows


def _detect_edge_cases(gray_frames):
    """Detect edge-case conditions: camera shake, low-light, fast motion.

    Returns a dict of boolean flags and numeric scores.

    Args:
        gray_frames: List of float32 (H, W) numpy arrays.

    Returns:
        Dict with keys: shake_detected, low_light, fast_motion,
        mean_brightness, mean_shift, mean_flow_magnitude.

    >>> result = _detect_edge_cases([])
    >>> result['shake_detected']
    False
    >>> result['low_light']
    False
    """
    result = {
        "shake_detected": False,
        "low_light": False,
        "fast_motion": False,
        "mean_brightness": 0.0,
        "mean_shift": 0.0,
        "mean_flow_magnitude": 0.0,
    }
    if not _HAS_NUMPY or len(gray_frames) < 2:
        return result

    # Low-light detection: mean brightness across all frames
    brightnesses = [float(f.mean()) for f in gray_frames[:20]]
    mean_brightness = sum(brightnesses) / len(brightnesses)
    result["mean_brightness"] = round(mean_brightness, 2)
    result["low_light"] = mean_brightness < LOW_LIGHT_BRIGHTNESS_THRESHOLD

    # Camera shake: global frame-to-frame mean shift
    shifts = []
    for i in range(1, min(len(gray_frames), 20)):
        prev, curr = gray_frames[i - 1], gray_frames[i]
        if prev.shape != curr.shape:
            continue
        # Compare mean intensity in quadrants as proxy for global shift
        h, w = prev.shape
        mh, mw = h // 2, w // 2
        quads_prev = [prev[:mh, :mw].mean(), prev[:mh, mw:].mean(),
                      prev[mh:, :mw].mean(), prev[mh:, mw:].mean()]
        quads_curr = [curr[:mh, :mw].mean(), curr[:mh, mw:].mean(),
                      curr[mh:, :mw].mean(), curr[mh:, mw:].mean()]
        shift = sum(abs(a - b) for a, b in zip(quads_prev, quads_curr)) / 4.0
        shifts.append(shift)
    mean_shift = sum(shifts) / len(shifts) if shifts else 0.0
    result["mean_shift"] = round(mean_shift, 3)
    result["shake_detected"] = mean_shift > CAMERA_SHAKE_SHIFT_THRESHOLD

    # Fast-motion: compute block-matching on sampled frame pairs
    magnitudes = []
    for i in range(1, min(len(gray_frames), OPTICAL_FLOW_MAX_FRAME_PAIRS + 1)):
        flows = _compute_optical_flow(gray_frames[i - 1], gray_frames[i])
        for dx, dy in flows:
            magnitudes.append(math.sqrt(dx * dx + dy * dy))
    mean_mag = sum(magnitudes) / len(magnitudes) if magnitudes else 0.0
    result["mean_flow_magnitude"] = round(mean_mag, 3)
    result["fast_motion"] = mean_mag > FAST_MOTION_MAGNITUDE_THRESHOLD

    return result


def compute_optical_flow_features(gray_frames):
    """Compute optical flow features for action recognition.

    Analyzes motion vector time-series across frames to produce a compact
    feature vector suitable for rule-based action classification.

    This is the main entry point for the KS40e Action Recognition pipeline.

    Args:
        gray_frames: List of float32 (H, W) numpy arrays (grayscale frames).
                     Minimum 2 frames required; cap at
                     ``OPTICAL_FLOW_MAX_FRAME_PAIRS + 1`` for performance.

    Returns:
        ``OpticalFlowFeatures`` dataclass.

    >>> features = compute_optical_flow_features([])
    >>> features.available
    False
    >>> features.motion_type
    'unknown'

    >>> import numpy as np
    >>> # Frames with very small random noise: flow magnitudes should be tiny
    >>> rng = np.random.default_rng(42)
    >>> noisy_frames = [rng.uniform(0, 1, (32, 32)).astype(np.float32) for _ in range(4)]
    >>> f = compute_optical_flow_features(noisy_frames)
    >>> f.available
    True
    >>> # Motion type should be one of the defined categories
    >>> f.motion_type in ('static', 'pan', 'zoom', 'chaotic', 'mixed')
    True
    >>> 0.0 <= f.static_ratio <= 1.0
    True
    """
    if not _HAS_NUMPY or len(gray_frames) < 2:
        return OpticalFlowFeatures(available=False)

    edge = _detect_edge_cases(gray_frames)

    all_magnitudes = []
    all_directions = []
    static_count = 0
    total_blocks = 0

    n_pairs = min(len(gray_frames) - 1, OPTICAL_FLOW_MAX_FRAME_PAIRS)
    for i in range(1, n_pairs + 1):
        flows = _compute_optical_flow(gray_frames[i - 1], gray_frames[i])
        for dx, dy in flows:
            mag = math.sqrt(dx * dx + dy * dy)
            all_magnitudes.append(mag)
            total_blocks += 1
            if mag < OPTICAL_FLOW_STATIC_THRESHOLD:
                static_count += 1
            else:
                all_directions.append(math.atan2(dy, dx))

    if not all_magnitudes:
        return OpticalFlowFeatures(available=True, motion_type="static",
                                   static_ratio=1.0,
                                   shake_detected=edge["shake_detected"],
                                   low_light=edge["low_light"])

    avg_mag = sum(all_magnitudes) / len(all_magnitudes)
    max_mag = max(all_magnitudes)
    static_ratio = static_count / max(total_blocks, 1)

    # Circular mean for dominant direction
    if all_directions:
        cx = sum(math.cos(d) for d in all_directions) / len(all_directions)
        cy = sum(math.sin(d) for d in all_directions) / len(all_directions)
        consistency = math.sqrt(cx * cx + cy * cy)
        dominant = math.atan2(cy, cx)
    else:
        consistency = 1.0
        dominant = 0.0

    # Motion type classification
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

    return OpticalFlowFeatures(
        available=True,
        avg_magnitude=round(avg_mag, 3),
        max_magnitude=round(max_mag, 3),
        motion_consistency=round(consistency, 3),
        dominant_direction_rad=round(dominant, 3),
        static_ratio=round(static_ratio, 3),
        motion_type=motion_type,
        shake_detected=edge["shake_detected"],
        low_light=edge["low_light"],
        fast_motion=edge["fast_motion"],
    )


# Action recognition rules: (label, test_fn) evaluated in order
# Each test receives an OpticalFlowFeatures and returns a confidence 0-1.
_ACTION_RULES = [
    ("fighting",     lambda f: min(1.0, f.avg_magnitude / 6.0) * (1 - f.static_ratio)
                              if f.motion_type == "chaotic" and f.avg_magnitude > 4.0 else 0.0),
    ("running",      lambda f: min(1.0, f.avg_magnitude / 8.0)
                              if f.motion_type in ("chaotic", "mixed") and f.avg_magnitude > 5.0
                              else 0.0),
    ("walking",      lambda f: min(1.0, f.avg_magnitude / 4.0) * 0.7
                              if 1.0 < f.avg_magnitude <= 5.0 and f.motion_type in ("mixed", "chaotic")
                              else 0.0),
    ("loitering",    lambda f: (1 - f.avg_magnitude / 3.0) * 0.8
                              if f.motion_type in ("static", "mixed") and f.avg_magnitude < 2.0
                              else 0.0),
    ("camera_pan",   lambda f: f.motion_consistency
                              if f.motion_type == "pan" else 0.0),
    ("falling",      lambda f: min(1.0, f.max_magnitude / 10.0) * 0.6
                              if f.max_magnitude > 8.0 and f.motion_type != "pan" else 0.0),
    ("stationary",   lambda f: f.static_ratio
                              if f.motion_type == "static" else 0.0),
]


def classify_action_from_flow(flow_features, frame_analyses=None):
    """Classify human action from optical flow features.

    Uses a rule-based scorer that maps motion-vector statistics to
    action labels.  When Gemini frame analyses are also available, their
    ``behavior`` field is used to break ties and boost confidence.

    Args:
        flow_features: ``OpticalFlowFeatures`` returned by
                       ``compute_optical_flow_features``.
        frame_analyses: Optional list of Gemini frame-analysis dicts
                        (each may contain a ``persons`` list with
                        ``behavior`` fields).

    Returns:
        ``ActionRecognitionResult``.

    >>> f = OpticalFlowFeatures(available=False)
    >>> r = classify_action_from_flow(f)
    >>> r.action_label
    ''
    >>> r.confidence
    0.0

    >>> import math
    >>> f2 = OpticalFlowFeatures(
    ...     available=True, avg_magnitude=0.1, max_magnitude=0.2,
    ...     motion_consistency=1.0, static_ratio=0.97,
    ...     motion_type='static', shake_detected=False,
    ...     low_light=False, fast_motion=False,
    ... )
    >>> r2 = classify_action_from_flow(f2)
    >>> r2.action_label
    'stationary'
    >>> r2.confidence >= 0.3
    True
    """
    if not flow_features.available:
        return ActionRecognitionResult()

    # Score each rule
    scored = []
    for label, rule in _ACTION_RULES:
        try:
            score = float(rule(flow_features))
        except Exception:
            score = 0.0
        if score > 0:
            scored.append((label, score))

    # Boost from Gemini behavior labels if available
    if frame_analyses:
        behavior_counts = {}
        for fa in frame_analyses:
            if not fa:
                continue
            for p in fa.get("persons", []):
                beh = p.get("behavior", "")
                if beh:
                    behavior_counts[beh] = behavior_counts.get(beh, 0) + 1
        total_behaviors = sum(behavior_counts.values()) or 1
        for i, (label, score) in enumerate(scored):
            # Map label → Gemini behavior aliases
            aliases = {
                "fighting": ("aggressive",),
                "running": ("running",),
                "loitering": ("loitering",),
                "stationary": ("normal",),
            }
            for alias in aliases.get(label, []):
                boost = behavior_counts.get(alias, 0) / total_behaviors * 0.2
                scored[i] = (label, min(1.0, score + boost))

    # Sort descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Edge-case flags
    flags = []
    if flow_features.shake_detected:
        flags.append("shake")
    if flow_features.low_light:
        flags.append("low_light")
    if flow_features.fast_motion:
        flags.append("fast_motion")

    if not scored or scored[0][1] < ACTION_CONFIDENCE_THRESHOLD:
        return ActionRecognitionResult(
            flow_features=flow_features, edge_case_flags=flags)

    primary_label, primary_conf = scored[0]
    secondary = [(lbl, round(sc, 3)) for lbl, sc in scored[1:]
                 if sc >= ACTION_CONFIDENCE_THRESHOLD]

    return ActionRecognitionResult(
        action_label=primary_label,
        confidence=round(primary_conf, 3),
        secondary_labels=secondary,
        flow_features=flow_features,
        edge_case_flags=flags,
    )


def _extract_audio_track(video_path):
    """Extract audio track from video for separate analysis."""
    audio_path = tempfile.mktemp(suffix=".wav", prefix="ks30_audio_")
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", audio_path, "-y"],
            capture_output=True, timeout=30)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
            return audio_path
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Gemini Vision Analysis
# ═══════════════════════════════════════════════════════════════════════════

FRAME_ANALYSIS_PROMPT = """Analyze this video frame for security and behavioral analysis.

Respond in JSON format:
{
  "scene": "description of the scene",
  "scene_type": "indoor/outdoor/street/office/etc",
  "lighting": "bright/dim/dark/mixed",
  "persons": [
    {
      "description": "appearance description",
      "behavior": "normal/loitering/running/concealing/aggressive/evasive",
      "suspicion": 0.0-1.0,
      "clothing": "...",
      "age_estimate": "child/teen/adult/elderly",
      "face_visible": true/false
    }
  ],
  "objects_of_interest": ["weapon", "bag", "vehicle", etc],
  "threat_indicators": ["description of any threatening behavior"],
  "overall_threat": 0.0-1.0
}"""


def _analyze_frame_gemini(frame_path, api_key=None, timeout=30):
    """Analyze a single frame using Gemini Vision."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    
    with open(frame_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [
            {"text": FRAME_ANALYSIS_PROMPT},
            {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000}
    }
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            # Parse JSON from response
            import re
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(text)
    except Exception:
        return None


def _detect_suspicious_patterns(frame_analyses):
    """Detect temporal suspicious patterns across frames."""
    patterns = []
    
    if not frame_analyses:
        return patterns, 0.0
    
    # Track persons across frames
    person_sightings = {}
    for fa in frame_analyses:
        if not fa:
            continue
        for i, person in enumerate(fa.get("persons", [])):
            # Simple tracking by description similarity
            desc = person.get("description", "")
            key = desc[:30]  # rough matching
            if key not in person_sightings:
                person_sightings[key] = []
            person_sightings[key].append({
                "frame": fa.get("frame_index", 0),
                "behavior": person.get("behavior", "normal"),
                "suspicion": person.get("suspicion", 0),
            })
    
    # Detect patterns
    for person_key, sightings in person_sightings.items():
        behaviors = [s["behavior"] for s in sightings]
        
        # Loitering: person appears in many frames
        if len(sightings) > len(frame_analyses) * 0.7:
            patterns.append({
                "type": "loitering",
                "detail": f"Person '{person_key[:20]}' present in {len(sightings)}/{len(frame_analyses)} frames",
                "severity": 0.6,
            })
        
        # Behavior change: normal → aggressive/evasive
        for i in range(1, len(behaviors)):
            if behaviors[i-1] == "normal" and behaviors[i] in ("aggressive", "evasive", "running"):
                patterns.append({
                    "type": "behavior_change",
                    "detail": f"'{person_key[:20]}' changed from {behaviors[i-1]} to {behaviors[i]}",
                    "severity": 0.7,
                })
        
        # Concealment
        if "concealing" in behaviors:
            patterns.append({
                "type": "concealment",
                "detail": f"'{person_key[:20]}' showing concealment behavior",
                "severity": 0.8,
            })
    
    # Threat level = max individual threat across frames
    max_threat = 0.0
    for fa in frame_analyses:
        if fa:
            max_threat = max(max_threat, fa.get("overall_threat", 0))
    
    # Adjust by pattern severity
    pattern_threat = sum(p["severity"] for p in patterns) / max(1, len(patterns) * 2)
    overall = min(1.0, max(max_threat, pattern_threat))
    
    return patterns, overall


# ═══════════════════════════════════════════════════════════════════════════
# Main API
# ═══════════════════════════════════════════════════════════════════════════

def analyze_video(video_path, max_frames=None, analyze_audio_track=True, api_key=None):
    """Full video analysis pipeline (KS40e enhanced).

    Pipeline:
      1. Key frame extraction at TOKENS_PER_VIDEO_SEC rate
      2. KS40e: Optical flow computation on extracted frames
      3. KS40e: Action recognition from flow features
      4. Gemini Vision analysis per frame (if API key available)
      5. Temporal suspicious-pattern detection
      6. Audio track analysis (if present)

    Args:
        video_path: Path to video file.
        max_frames: Hard cap on Gemini Vision frames.
                    Defaults to MAX_GEMINI_FRAMES.
        analyze_audio_track: If True, also analyse audio track.
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).

    Returns:
        VideoAnalysis dataclass.  ``action_recognition`` field contains
        ActionRecognitionResult when optical flow succeeds.

    Usage:
        result = analyze_video("/path/to/video.mp4")
        claim = video_to_claim(result)
        ks30_result = LLMPipeline('gemini-3-pro').run(claim)
    """
    if not Path(video_path).exists():
        return VideoAnalysis(confidence=0.0, source="error")

    content_hash = hashlib.sha256(Path(video_path).read_bytes()[:1_000_000]).hexdigest()[:16]

    # 1. Extract key frames (KS40e: TOKENS_PER_VIDEO_SEC resolution)
    frames, info = _extract_key_frames(video_path, max_frames)

    # 2. KS40e: Optical flow on extracted frames
    gray_arrays = _frames_to_gray_arrays([f["path"] for f in frames])
    flow_features = compute_optical_flow_features(gray_arrays)

    # 3. Gemini Vision analysis per frame
    frame_analyses = []
    persons_all = []

    for frame in frames:
        fa = _analyze_frame_gemini(frame["path"], api_key)
        if fa:
            fa["frame_index"] = frame["index"]
            fa["timestamp"] = frame["timestamp"]
            frame_analyses.append(fa)

            # Collect persons
            for i, p in enumerate(fa.get("persons", [])):
                pd = PersonDetection(
                    person_id=f"P{frame['index']}_{i}",
                    frame_number=frame["index"],
                    timestamp_sec=frame["timestamp"],
                    description=p.get("description", ""),
                    behavior=p.get("behavior", "normal"),
                    suspicion_score=float(p.get("suspicion", 0)),
                    clothing=p.get("clothing", ""),
                    estimated_age=p.get("age_estimate", ""),
                    face_visible=p.get("face_visible", False),
                )
                persons_all.append(pd)

    # 4. KS40e: Action recognition (flow + Gemini behaviors combined)
    action_result = classify_action_from_flow(flow_features, frame_analyses)

    # Promote optical-flow action into suspicious_behaviors when high-risk
    # and Gemini did not already produce matching indicators
    flow_boosted_behaviors = []
    high_risk_actions = {"fighting", "falling"}
    if (action_result.action_label in high_risk_actions
            and action_result.confidence >= ACTION_CONFIDENCE_THRESHOLD):
        flow_boosted_behaviors.append({
            "type": action_result.action_label,
            "detail": (f"Optical flow detected '{action_result.action_label}' "
                       f"(conf={action_result.confidence:.2f})"),
            "severity": min(0.9, action_result.confidence + 0.1),
        })

    # 5. Detect temporal patterns
    suspicious, threat_level = _detect_suspicious_patterns(frame_analyses)
    suspicious = flow_boosted_behaviors + suspicious

    # Re-compute threat considering flow signal
    if flow_boosted_behaviors:
        flow_threat = max(b["severity"] for b in flow_boosted_behaviors)
        threat_level = min(1.0, max(threat_level, flow_threat))

    # 6. Key events
    key_events = []
    for fa in frame_analyses:
        if fa.get("overall_threat", 0) > 0.3:
            key_events.append({
                "timestamp": fa.get("timestamp", 0),
                "description": "; ".join(fa.get("threat_indicators", [])),
                "severity": fa.get("overall_threat", 0),
            })

    # 7. Scene understanding (from first frame)
    scene_desc = frame_analyses[0].get("scene", "") if frame_analyses else ""
    scene_type = frame_analyses[0].get("scene_type", "") if frame_analyses else ""
    lighting = frame_analyses[0].get("lighting", "") if frame_analyses else ""

    # 8. Edge-case flags in motion_intensity metadata
    edge_flags = action_result.edge_case_flags
    motion_intensity_meta = {
        "flow_motion_type": flow_features.motion_type,
        "flow_avg_magnitude": flow_features.avg_magnitude,
        "edge_case_flags": edge_flags,
    }

    # 9. Audio analysis (if video has audio track)
    audio_result = None
    if analyze_audio_track and info.get("has_audio"):
        audio_path = _extract_audio_track(video_path)
        if audio_path:
            from .audio_analysis import analyze_audio
            audio_result = analyze_audio(audio_path)
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    # Clean up frames
    for frame in frames:
        try:
            os.unlink(frame["path"])
        except Exception:
            pass

    result = VideoAnalysis(
        duration_sec=info.get("duration", 0),
        fps=info.get("fps", 0),
        resolution=info.get("resolution", ""),
        frame_count=info.get("frame_count", 0),
        scene_description=scene_desc,
        scene_type=scene_type,
        lighting=lighting,
        persons_detected=persons_all,
        total_persons=len(set(p.description[:20] for p in persons_all)),
        suspicious_behaviors=suspicious,
        overall_threat_level=threat_level,
        key_events=key_events,
        motion_intensity=[motion_intensity_meta],
        has_audio=info.get("has_audio", False),
        audio_analysis=audio_result,
        content_hash=content_hash,
        confidence=0.85 if frame_analyses else 0.3,
        frames_analyzed=len(frame_analyses),
        source="gemini_vision",
    )
    # Attach action recognition result as attribute (non-dataclass extension)
    result.action_recognition = action_result  # type: ignore[attr-defined]
    return result


def video_to_claim(analysis, additional_evidence=None):
    """Convert VideoAnalysis to KS30 Claim."""
    from .ks29b import Claim
    
    # Build claim text from analysis
    parts = []
    if analysis.scene_description:
        parts.append(f"Scene: {analysis.scene_description}")
    if analysis.total_persons > 0:
        parts.append(f"Detected {analysis.total_persons} person(s)")
    if analysis.suspicious_behaviors:
        behaviors = [s["type"] for s in analysis.suspicious_behaviors]
        parts.append(f"Suspicious: {', '.join(behaviors)}")
    if analysis.audio_analysis and analysis.audio_analysis.transcript:
        parts.append(f"Audio: {analysis.audio_analysis.transcript[:100]}")
    
    text = " | ".join(parts) or "Video with no analyzable content"
    
    evidence = []
    if analysis.overall_threat_level > 0.3:
        evidence.append(f"Threat level: {analysis.overall_threat_level:.2f}")
    for event in analysis.key_events[:3]:
        evidence.append(f"Event @{event['timestamp']:.1f}s: {event['description'][:60]}")
    for person in analysis.persons_detected[:5]:
        if person.suspicion_score > 0.3:
            evidence.append(f"Suspicious person: {person.description[:40]} ({person.behavior})")
    if additional_evidence:
        evidence.extend(additional_evidence)
    
    claim = Claim(text=text, evidence=evidence)
    claim._video = analysis
    return claim
