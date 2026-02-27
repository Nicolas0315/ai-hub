"""
KS30 Video Analysis Engine
Extracts behavioral patterns, person detection, and suspicious activity from video.

Capabilities:
- Frame extraction + Gemini Vision analysis
- Person detection and tracking
- Suspicious behavior detection (loitering, sudden movements, concealment)
- Scene understanding and temporal analysis
- Integration with audio analysis for multimodal threat assessment

Design: Youta Hilono
Implementation: Shirokuma
"""

import json
import urllib.request
import os
import hashlib
import subprocess
import tempfile
import base64
import time
from dataclasses import dataclass, field
from pathlib import Path


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


def _extract_key_frames(video_path, max_frames=8, output_dir=None):
    """Extract key frames from video at regular intervals."""
    output_dir = output_dir or tempfile.mkdtemp(prefix="ks30_frames_")
    info = _get_video_info(video_path)
    duration = info["duration"]
    
    if duration <= 0:
        return [], info
    
    # Calculate intervals
    n_frames = min(max_frames, max(1, int(duration)))
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

def analyze_video(video_path, max_frames=8, analyze_audio_track=True, api_key=None):
    """Full video analysis pipeline.
    
    Pipeline: video → key frames → Gemini Vision per frame → temporal analysis
              ↓ audio track → AudioAnalysis (emotion, voiceprint)
    
    Usage:
        result = analyze_video("/path/to/video.mp4")
        claim = video_to_claim(result)
        ks30_result = LLMPipeline('gemini-3-pro').run(claim)
    """
    if not Path(video_path).exists():
        return VideoAnalysis(confidence=0.0, source="error")
    
    content_hash = hashlib.sha256(Path(video_path).read_bytes()[:1_000_000]).hexdigest()[:16]
    
    # 1. Extract key frames
    frames, info = _extract_key_frames(video_path, max_frames)
    
    # 2. Analyze each frame with Gemini Vision
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
    
    # 3. Detect temporal patterns
    suspicious, threat_level = _detect_suspicious_patterns(frame_analyses)
    
    # 4. Key events
    key_events = []
    for fa in frame_analyses:
        if fa.get("overall_threat", 0) > 0.3:
            key_events.append({
                "timestamp": fa.get("timestamp", 0),
                "description": "; ".join(fa.get("threat_indicators", [])),
                "severity": fa.get("overall_threat", 0),
            })
    
    # 5. Scene understanding (from first frame)
    scene_desc = frame_analyses[0].get("scene", "") if frame_analyses else ""
    scene_type = frame_analyses[0].get("scene_type", "") if frame_analyses else ""
    lighting = frame_analyses[0].get("lighting", "") if frame_analyses else ""
    
    # 6. Audio analysis (if video has audio track)
    audio_result = None
    if analyze_audio_track and info.get("has_audio"):
        audio_path = _extract_audio_track(video_path)
        if audio_path:
            from .audio_analysis import analyze_audio
            audio_result = analyze_audio(audio_path)
            # Clean up
            try: os.unlink(audio_path)
            except: pass
    
    # Clean up frames
    for frame in frames:
        try: os.unlink(frame["path"])
        except: pass
    
    return VideoAnalysis(
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
        motion_intensity=[],
        has_audio=info.get("has_audio", False),
        audio_analysis=audio_result,
        content_hash=content_hash,
        confidence=0.85 if frame_analyses else 0.3,
        frames_analyzed=len(frame_analyses),
        source="gemini_vision",
    )


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
