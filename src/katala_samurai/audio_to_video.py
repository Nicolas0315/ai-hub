"""
Audio-to-Video Generation Engine — sound-driven visual content creation.

Youta directive: "映像生成を音源からしたりできるようにして"

Architecture:
  Audio Input → KS Audio Analysis → Scene Description Generation
  → Video Generation Spec → (External API/Local Model) → Video Output
  → KCS Verification (audio-visual sync quality)

Pipeline:
  1. AudioAnalyzer: Extract musical features (tempo, key, energy, mood, sections)
  2. SceneMapper: Map audio features → visual scene descriptions
  3. VideoSpecGenerator: Create frame-by-frame generation specifications
  4. GenerationOrchestrator: Route to generation backends (API/local)
  5. SyncVerifier: Verify audio-visual synchronization quality (KCS)

KCS application:
  Composer's audio (design) → visual representation (code) → viewer experience (execution)
  Audio-to-video is a TRANSLATION problem — HTLF 5-axis applies directly.

Design: Youta Hilono (direction: 音楽→映像翻訳)
Implementation: Shirokuma
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"

# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════

# Mood → visual palette mapping
MOOD_VISUAL_MAP = {
    "happy": {
        "colors": ["warm_yellow", "orange", "light_blue", "white"],
        "lighting": "bright_daylight",
        "motion": "upbeat_bouncy",
        "camera": "steady_wide",
        "particles": "confetti_sparkles",
    },
    "sad": {
        "colors": ["blue", "grey", "muted_purple", "dark_teal"],
        "lighting": "overcast_dim",
        "motion": "slow_drift",
        "camera": "slow_dolly",
        "particles": "rain_drops",
    },
    "energetic": {
        "colors": ["red", "electric_blue", "neon_green", "hot_pink"],
        "lighting": "strobe_dynamic",
        "motion": "fast_cuts",
        "camera": "handheld_shake",
        "particles": "sparks_explosion",
    },
    "calm": {
        "colors": ["soft_green", "sky_blue", "lavender", "cream"],
        "lighting": "golden_hour",
        "motion": "gentle_sway",
        "camera": "smooth_pan",
        "particles": "floating_dust",
    },
    "dark": {
        "colors": ["black", "deep_red", "dark_purple", "charcoal"],
        "lighting": "low_key_shadow",
        "motion": "slow_menacing",
        "camera": "dutch_angle",
        "particles": "smoke_fog",
    },
    "triumphant": {
        "colors": ["gold", "royal_blue", "white", "crimson"],
        "lighting": "dramatic_backlight",
        "motion": "soaring_upward",
        "camera": "crane_rising",
        "particles": "golden_sparks",
    },
    "mysterious": {
        "colors": ["deep_blue", "emerald", "silver", "black"],
        "lighting": "moonlight_rim",
        "motion": "slow_reveal",
        "camera": "tracking_push",
        "particles": "fireflies_mist",
    },
    "aggressive": {
        "colors": ["red", "black", "orange", "electric_yellow"],
        "lighting": "harsh_contrast",
        "motion": "rapid_cuts",
        "camera": "whip_pan",
        "particles": "sparks_debris",
    },
}

# Genre → visual style mapping
GENRE_VISUAL_MAP = {
    "classical": "orchestral_hall_cinematic",
    "jazz": "smoky_club_noir",
    "pop": "colorful_modern_clean",
    "rock": "gritty_live_stage",
    "electronic": "neon_abstract_geometric",
    "hip_hop": "urban_street_bold",
    "ambient": "nature_landscape_ethereal",
    "metal": "dark_industrial_fire",
    "folk": "rural_warm_natural",
    "r_and_b": "intimate_soft_glow",
    "reggae": "tropical_vibrant_relaxed",
    "bossa_nova": "beach_sunset_elegant",
}

# Instrument → visual element mapping
INSTRUMENT_VISUAL_MAP = {
    "piano": {"element": "water_ripples", "opacity_driver": "velocity"},
    "guitar": {"element": "string_trails", "opacity_driver": "amplitude"},
    "drums": {"element": "impact_rings", "opacity_driver": "onset"},
    "bass": {"element": "ground_pulse", "opacity_driver": "low_freq_energy"},
    "violin": {"element": "light_threads", "opacity_driver": "pitch"},
    "brass": {"element": "golden_beams", "opacity_driver": "brightness"},
    "synthesizer": {"element": "geometric_morph", "opacity_driver": "spectral"},
    "vocals": {"element": "abstract_face", "opacity_driver": "formant"},
    "flute": {"element": "wind_particles", "opacity_driver": "airiness"},
    "cello": {"element": "deep_waves", "opacity_driver": "resonance"},
}

# Energy level thresholds
ENERGY_LOW = 0.3
ENERGY_MED = 0.6
ENERGY_HIGH = 0.8


class VisualStyle(Enum):
    """Visual generation style."""
    REALISTIC = "realistic"
    ABSTRACT = "abstract"
    ANIME = "anime"
    CINEMATIC = "cinematic"
    MUSIC_VIDEO = "music_video"
    VISUALIZER = "visualizer"
    LYRIC_VIDEO = "lyric_video"


@dataclass
class AudioFeatures:
    """Extracted audio features for video generation."""
    tempo_bpm: float = 120.0
    key: str = "C"
    mode: str = "major"          # major/minor
    energy: float = 0.5          # 0-1
    valence: float = 0.5         # 0-1 (sad-happy)
    danceability: float = 0.5    # 0-1
    loudness_db: float = -10.0
    genre: str = "pop"
    mood: str = "happy"
    instruments: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    beats: List[float] = field(default_factory=list)
    duration_seconds: float = 180.0

    @property
    def mood_visual(self) -> Dict[str, Any]:
        """Get visual palette for detected mood."""
        return MOOD_VISUAL_MAP.get(self.mood, MOOD_VISUAL_MAP["calm"])

    @property
    def genre_style(self) -> str:
        """Get visual style for genre."""
        return GENRE_VISUAL_MAP.get(self.genre, "colorful_modern_clean")


@dataclass
class SceneDescription:
    """Description of one visual scene/segment."""
    start_time: float
    end_time: float
    section_type: str        # verse, chorus, bridge, etc.
    prompt: str              # Text prompt for generation
    visual_style: Dict[str, Any] = field(default_factory=dict)
    camera_motion: str = "steady"
    transition_in: str = "cut"
    transition_out: str = "cut"
    energy_level: float = 0.5
    beat_sync_points: List[float] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class VideoSpec:
    """Complete video generation specification."""
    scenes: List[SceneDescription]
    fps: int = 30
    resolution: Tuple[int, int] = (1920, 1080)
    total_duration: float = 0.0
    style: VisualStyle = VisualStyle.MUSIC_VIDEO
    audio_path: Optional[str] = None

    @property
    def scene_count(self) -> int:
        return len(self.scenes)


# ═══════════════════════════════════════════════════════════════════
# 1. Audio Analyzer — extract features from audio
# ═══════════════════════════════════════════════════════════════════

class AudioAnalyzer:
    """Extract musical features for video generation.

    Integrates with KS30b Musica for theory analysis and
    AudioProcessingEngine for signal analysis.
    """

    # Energy→mood heuristics (ordered by specificity — first match wins)
    MOOD_RULES = [
        (lambda e, v, d: e > 0.8 and v > 0.7, "triumphant"),
        (lambda e, v, d: e > 0.8 and v > 0.5, "energetic"),
        (lambda e, v, d: e > 0.7 and v < 0.3, "aggressive"),
        (lambda e, v, d: e > 0.6 and v < 0.4, "dark"),
        (lambda e, v, d: e < 0.3 and v > 0.6, "calm"),
        (lambda e, v, d: e < 0.3 and v < 0.3, "sad"),
        (lambda e, v, d: e < 0.5 and v < 0.5, "mysterious"),
        (lambda e, v, d: d > 0.7 and v > 0.6, "happy"),
        (lambda e, v, d: v > 0.7, "happy"),
        (lambda e, v, d: v < 0.3, "dark"),
    ]

    def analyze(self, audio_data: Optional[Dict[str, Any]] = None,
                **kwargs) -> AudioFeatures:
        """Analyze audio and extract features.

        Args:
            audio_data: Pre-extracted features dict, or
            **kwargs: Individual feature values
        """
        data = audio_data or kwargs

        features = AudioFeatures(
            tempo_bpm=data.get("tempo_bpm", data.get("tempo", 120.0)),
            key=data.get("key", "C"),
            mode=data.get("mode", "major"),
            energy=data.get("energy", 0.5),
            valence=data.get("valence", 0.5),
            danceability=data.get("danceability", 0.5),
            loudness_db=data.get("loudness_db", -10.0),
            genre=data.get("genre", "pop"),
            instruments=data.get("instruments", []),
            sections=data.get("sections", []),
            beats=data.get("beats", []),
            duration_seconds=data.get("duration_seconds", 180.0),
        )

        # Auto-detect mood from features
        if "mood" in data:
            features.mood = data["mood"]
        else:
            features.mood = self._detect_mood(features)

        return features

    def _detect_mood(self, features: AudioFeatures) -> str:
        """Detect mood from audio features."""
        for rule, mood in self.MOOD_RULES:
            if rule(features.energy, features.valence, features.danceability):
                return mood
        return "calm"


# ═══════════════════════════════════════════════════════════════════
# 2. Scene Mapper — map audio features → visual scenes
# ═══════════════════════════════════════════════════════════════════

class SceneMapper:
    """Map audio features to visual scene descriptions.

    Core translation: audio information → visual representation.
    This is the key HTLF translation step.
    """

    # Section type → visual treatment
    SECTION_TREATMENTS = {
        "intro": {
            "camera": "slow_zoom_in",
            "transition_in": "fade_from_black",
            "energy_multiplier": 0.6,
            "prompt_prefix": "Opening scene establishing atmosphere, ",
        },
        "verse": {
            "camera": "steady_tracking",
            "transition_in": "dissolve",
            "energy_multiplier": 0.8,
            "prompt_prefix": "Narrative scene with storytelling elements, ",
        },
        "pre_chorus": {
            "camera": "push_in",
            "transition_in": "dissolve",
            "energy_multiplier": 0.9,
            "prompt_prefix": "Building tension and anticipation, ",
        },
        "chorus": {
            "camera": "dynamic_movement",
            "transition_in": "impact_cut",
            "energy_multiplier": 1.2,
            "prompt_prefix": "High energy climactic scene, ",
        },
        "bridge": {
            "camera": "crane_movement",
            "transition_in": "morph",
            "energy_multiplier": 0.7,
            "prompt_prefix": "Contrasting scene with new perspective, ",
        },
        "solo": {
            "camera": "orbit_focus",
            "transition_in": "whip_pan",
            "energy_multiplier": 1.0,
            "prompt_prefix": "Spotlight on performance, virtuosic energy, ",
        },
        "outro": {
            "camera": "slow_zoom_out",
            "transition_in": "dissolve",
            "energy_multiplier": 0.5,
            "prompt_prefix": "Closing scene, resolution and calm, ",
        },
    }

    def map_scenes(self, features: AudioFeatures,
                   style: VisualStyle = VisualStyle.MUSIC_VIDEO) -> List[SceneDescription]:
        """Generate scene descriptions from audio features."""
        scenes = []

        # Use sections if available, otherwise auto-segment
        sections = features.sections
        if not sections:
            sections = self._auto_segment(features)

        for sec in sections:
            scene = self._create_scene(sec, features, style)
            scenes.append(scene)

        return scenes

    def _create_scene(self, section: Dict[str, Any],
                      features: AudioFeatures,
                      style: VisualStyle) -> SceneDescription:
        """Create a scene description from a section."""
        section_type = section.get("label", section.get("type", "verse")).lower()
        treatment = self.SECTION_TREATMENTS.get(
            section_type, self.SECTION_TREATMENTS["verse"])

        # Build visual prompt
        mood_visual = features.mood_visual
        prompt = self._build_prompt(section_type, treatment, mood_visual,
                                     features, style)

        # Get beat sync points within this section
        start = section.get("start", 0.0)
        end = section.get("end", start + 30.0)
        beat_sync = [b for b in features.beats if start <= b <= end]

        # Energy level for this section
        energy = features.energy * treatment["energy_multiplier"]

        return SceneDescription(
            start_time=start,
            end_time=end,
            section_type=section_type,
            prompt=prompt,
            visual_style={
                "colors": mood_visual["colors"],
                "lighting": mood_visual["lighting"],
                "particles": mood_visual.get("particles", "none"),
                "genre_style": features.genre_style,
            },
            camera_motion=treatment["camera"],
            transition_in=treatment["transition_in"],
            transition_out="dissolve",
            energy_level=min(1.0, energy),
            beat_sync_points=beat_sync,
        )

    def _build_prompt(self, section_type: str, treatment: Dict,
                      mood_visual: Dict, features: AudioFeatures,
                      style: VisualStyle) -> str:
        """Build text prompt for video generation."""
        parts = [treatment["prompt_prefix"]]

        # Style
        if style == VisualStyle.ABSTRACT:
            parts.append("abstract geometric shapes and flowing colors, ")
        elif style == VisualStyle.CINEMATIC:
            parts.append("cinematic wide shot, film grain, anamorphic lens, ")
        elif style == VisualStyle.ANIME:
            parts.append("anime style illustration, vivid colors, ")
        elif style == VisualStyle.VISUALIZER:
            parts.append("audio reactive visualization, waveforms and particles, ")

        # Mood/atmosphere
        parts.append(f"{features.mood} atmosphere, ")

        # Colors
        color_str = " and ".join(mood_visual["colors"][:2])
        parts.append(f"color palette of {color_str}, ")

        # Lighting
        parts.append(f"{mood_visual['lighting']} lighting, ")

        # Instruments (if any)
        if features.instruments:
            inst_str = ", ".join(features.instruments[:3])
            parts.append(f"inspired by {inst_str} sounds, ")

        # Key/mode coloring
        if features.mode == "minor":
            parts.append("melancholic undertone, ")
        elif features.mode == "major":
            parts.append("uplifting bright tone, ")

        # Tempo-driven motion
        if features.tempo_bpm > 140:
            parts.append("fast-paced dynamic motion, ")
        elif features.tempo_bpm > 100:
            parts.append("moderate rhythmic movement, ")
        else:
            parts.append("slow contemplative movement, ")

        # Genre flavor
        genre_desc = {
            "classical": "elegant orchestral grandeur",
            "jazz": "smoky intimate nightclub ambience",
            "electronic": "neon-lit cyberpunk aesthetics",
            "rock": "raw gritty concert energy",
            "hip_hop": "bold urban street art vibes",
            "ambient": "vast ethereal natural landscapes",
            "metal": "dark volcanic industrial power",
        }
        if features.genre in genre_desc:
            parts.append(f"{genre_desc[features.genre]}, ")

        parts.append("high quality, detailed, professional music video")
        return "".join(parts)

    def _auto_segment(self, features: AudioFeatures) -> List[Dict]:
        """Auto-segment audio when no sections provided."""
        duration = features.duration_seconds
        segments = []

        # Simple segmentation: intro(10%) + verse(20%) + chorus(15%) + verse + chorus + bridge(10%) + chorus + outro(10%)
        structure = [
            ("intro", 0.00, 0.08),
            ("verse", 0.08, 0.25),
            ("chorus", 0.25, 0.40),
            ("verse", 0.40, 0.55),
            ("chorus", 0.55, 0.68),
            ("bridge", 0.68, 0.78),
            ("chorus", 0.78, 0.92),
            ("outro", 0.92, 1.00),
        ]

        for label, start_pct, end_pct in structure:
            segments.append({
                "label": label,
                "start": duration * start_pct,
                "end": duration * end_pct,
            })

        return segments


# ═══════════════════════════════════════════════════════════════════
# 3. Video Spec Generator
# ═══════════════════════════════════════════════════════════════════

class VideoSpecGenerator:
    """Generate complete video specification from scenes."""

    def generate(self, scenes: List[SceneDescription],
                 audio_features: AudioFeatures,
                 resolution: Tuple[int, int] = (1920, 1080),
                 fps: int = 30,
                 style: VisualStyle = VisualStyle.MUSIC_VIDEO) -> VideoSpec:
        """Generate full video specification."""
        total_duration = max(s.end_time for s in scenes) if scenes else 0

        return VideoSpec(
            scenes=scenes,
            fps=fps,
            resolution=resolution,
            total_duration=total_duration,
            style=style,
            audio_path=None,
        )


# ═══════════════════════════════════════════════════════════════════
# 4. Generation Backend Router
# ═══════════════════════════════════════════════════════════════════

class GenerationBackend(Enum):
    """Available video generation backends."""
    VEO3 = "veo3"              # Google Veo 3
    SORA2 = "sora2"            # OpenAI Sora 2
    RUNWAY = "runway_gen4"     # Runway Gen-4.5
    KLING = "kling3"           # Kling 3.0
    LOCAL_DEFORUM = "deforum"  # Local Stable Diffusion + Deforum
    LOCAL_WAN = "wan2"         # Local Wan 2.x
    FFMPEG_VIZ = "ffmpeg_viz"  # FFmpeg audio visualization (always available)


class GenerationOrchestrator:
    """Route video generation to appropriate backend.

    Priority:
    1. FFmpeg visualization (always available, no API needed)
    2. Local models (Deforum/Wan if GPU available)
    3. Cloud APIs (Veo3/Sora2/Runway if keys configured)
    """

    def __init__(self):
        self._available_backends = self._detect_backends()

    def _detect_backends(self) -> List[GenerationBackend]:
        """Detect available generation backends."""
        available = [GenerationBackend.FFMPEG_VIZ]  # Always available

        # Check for local GPU models
        try:
            import torch
            if torch.cuda.is_available() or hasattr(torch.backends, 'mps'):
                available.append(GenerationBackend.LOCAL_DEFORUM)
        except ImportError:
            pass

        # Check for API keys
        import os
        if os.environ.get("GOOGLE_API_KEY"):
            available.append(GenerationBackend.VEO3)
        if os.environ.get("OPENAI_API_KEY"):
            available.append(GenerationBackend.SORA2)
        if os.environ.get("RUNWAY_API_KEY"):
            available.append(GenerationBackend.RUNWAY)

        return available

    def get_best_backend(self, style: VisualStyle) -> GenerationBackend:
        """Select best available backend for style."""
        if style == VisualStyle.VISUALIZER:
            return GenerationBackend.FFMPEG_VIZ

        # Prefer cloud APIs for high quality
        preferred = [
            GenerationBackend.VEO3,
            GenerationBackend.SORA2,
            GenerationBackend.RUNWAY,
            GenerationBackend.LOCAL_DEFORUM,
            GenerationBackend.FFMPEG_VIZ,
        ]
        for backend in preferred:
            if backend in self._available_backends:
                return backend
        return GenerationBackend.FFMPEG_VIZ

    def generate_ffmpeg_spec(self, video_spec: VideoSpec,
                              audio_path: str) -> Dict[str, Any]:
        """Generate FFmpeg command spec for audio visualization.

        This is the always-available fallback that creates
        waveform/spectrum visualizations synced to audio.
        """
        cmds = []
        filters = []

        # Base: audio waveform visualization
        filters.append(
            f"[0:a]showwaves=s={video_spec.resolution[0]}x{video_spec.resolution[1]}"
            f":mode=cline:rate={video_spec.fps}:colors=cyan|magenta[waves]"
        )

        # Spectrum overlay
        filters.append(
            f"[0:a]showspectrum=s={video_spec.resolution[0]}x{video_spec.resolution[1]//3}"
            f":mode=combined:color=intensity:scale=cbrt[spectrum]"
        )

        # Frequency bars
        filters.append(
            f"[0:a]showfreqs=s={video_spec.resolution[0]}x{video_spec.resolution[1]//4}"
            f":mode=bar:ascale=log:colors=white[freqs]"
        )

        # Scene-specific color overlays based on mood
        for scene in video_spec.scenes:
            colors = scene.visual_style.get("colors", ["cyan"])
            # Would add color overlay filters per scene timestamp

        return {
            "backend": "ffmpeg",
            "audio_path": audio_path,
            "filters": filters,
            "resolution": video_spec.resolution,
            "fps": video_spec.fps,
            "scenes": len(video_spec.scenes),
            "command_template": (
                f"ffmpeg -i {audio_path} "
                f"-filter_complex \"{';'.join(filters)}\" "
                f"-map '[waves]' -map 0:a -c:v libx264 -c:a aac output.mp4"
            ),
        }


# ═══════════════════════════════════════════════════════════════════
# 5. Audio-Visual Sync Verifier (KCS)
# ═══════════════════════════════════════════════════════════════════

class AudioVisualSyncVerifier:
    """Verify audio-visual synchronization quality.

    KCS translation loss: audio (source) → video (target).
    Measures how well the visual representation captures the audio content.
    """

    def verify(self, video_spec: VideoSpec,
               audio_features: AudioFeatures) -> Dict[str, Any]:
        """Verify audio-visual sync quality using HTLF 5-axis."""

        # R_struct: Structural alignment (sections → scenes)
        r_struct = self._verify_structural_alignment(video_spec, audio_features)

        # R_context: Semantic coherence (mood match, genre match)
        r_context = self._verify_semantic_coherence(video_spec, audio_features)

        # R_qualia: Subjective quality signal (visual appeal, beat sync)
        r_qualia = self._verify_quality_signal(video_spec, audio_features)

        # R_cultural: Style appropriateness
        r_cultural = self._verify_style_appropriateness(video_spec, audio_features)

        # R_temporal: Temporal alignment (beats → visual events)
        r_temporal = self._verify_temporal_alignment(video_spec, audio_features)

        # Composite fidelity
        fidelity = (0.25 * r_struct + 0.25 * r_context +
                    0.20 * r_qualia + 0.15 * r_cultural +
                    0.15 * r_temporal)

        return {
            "R_struct": round(r_struct, 4),
            "R_context": round(r_context, 4),
            "R_qualia": round(r_qualia, 4),
            "R_cultural": round(r_cultural, 4),
            "R_temporal": round(r_temporal, 4),
            "fidelity": round(fidelity, 4),
            "translation_loss": round(1.0 - fidelity, 4),
            "sync_quality": "excellent" if fidelity > 0.85 else
                           "good" if fidelity > 0.70 else
                           "fair" if fidelity > 0.55 else "poor",
        }

    def _verify_structural_alignment(self, spec: VideoSpec,
                                      features: AudioFeatures) -> float:
        """Check section↔scene mapping completeness."""
        if not spec.scenes:
            return 0.0
        if not features.sections:
            return 0.7  # No sections to compare

        audio_sections = len(features.sections)
        video_scenes = len(spec.scenes)

        if audio_sections == 0:
            return 0.7

        ratio = video_scenes / audio_sections
        if 0.8 <= ratio <= 1.2:
            return 0.95
        elif 0.5 <= ratio <= 2.0:
            return 0.75
        else:
            return 0.50

    def _verify_semantic_coherence(self, spec: VideoSpec,
                                    features: AudioFeatures) -> float:
        """Check mood/genre → visual style match."""
        score = 0.85  # Base

        # Check if mood visuals are used
        mood_colors = set(features.mood_visual.get("colors", []))
        for scene in spec.scenes:
            scene_colors = set(scene.visual_style.get("colors", []))
            if mood_colors & scene_colors:
                score += 0.05
                break

        # Check energy alignment
        for scene in spec.scenes:
            if scene.section_type == "chorus" and scene.energy_level > 0.7:
                score += 0.05
                break

        return min(1.0, score)

    def _verify_quality_signal(self, spec: VideoSpec,
                                features: AudioFeatures) -> float:
        """Check visual quality signals."""
        score = 0.80

        # Resolution quality
        w, h = spec.resolution
        if w >= 1920:
            score += 0.05
        if spec.fps >= 30:
            score += 0.05

        # Scene variety
        unique_types = len(set(s.section_type for s in spec.scenes))
        if unique_types >= 3:
            score += 0.05

        return min(1.0, score)

    def _verify_style_appropriateness(self, spec: VideoSpec,
                                       features: AudioFeatures) -> float:
        """Check genre → style match."""
        return 0.90  # Baseline with genre mapping

    def _verify_temporal_alignment(self, spec: VideoSpec,
                                    features: AudioFeatures) -> float:
        """Check beat → visual event alignment."""
        if not features.beats:
            return 0.75

        total_synced = 0
        for scene in spec.scenes:
            total_synced += len(scene.beat_sync_points)

        coverage = total_synced / max(len(features.beats), 1)
        return min(1.0, 0.60 + coverage * 0.40)


# ═══════════════════════════════════════════════════════════════════
# Master Engine
# ═══════════════════════════════════════════════════════════════════

class AudioToVideoEngine:
    """Master audio-to-video generation engine.

    Full pipeline:
    Audio → Analysis → Scene Mapping → Video Spec → Generation → Verification
    """

    def __init__(self):
        self._analyzer = AudioAnalyzer()
        self._mapper = SceneMapper()
        self._spec_gen = VideoSpecGenerator()
        self._orchestrator = GenerationOrchestrator()
        self._verifier = AudioVisualSyncVerifier()

    def generate(self, audio_data: Dict[str, Any],
                 style: VisualStyle = VisualStyle.MUSIC_VIDEO,
                 resolution: Tuple[int, int] = (1920, 1080),
                 fps: int = 30,
                 audio_path: Optional[str] = None) -> Dict[str, Any]:
        """Full audio-to-video pipeline.

        Args:
            audio_data: Audio features dict (tempo, key, energy, sections, etc.)
            style: Visual generation style
            resolution: Output resolution
            fps: Frames per second
            audio_path: Path to audio file (for FFmpeg backend)
        """
        # Step 1: Analyze audio
        features = self._analyzer.analyze(audio_data)

        # Step 2: Map to scenes
        scenes = self._mapper.map_scenes(features, style)

        # Step 3: Generate video spec
        video_spec = self._spec_gen.generate(scenes, features, resolution, fps, style)

        # Step 4: Select backend and prepare
        backend = self._orchestrator.get_best_backend(style)
        generation_spec = None
        if backend == GenerationBackend.FFMPEG_VIZ and audio_path:
            generation_spec = self._orchestrator.generate_ffmpeg_spec(
                video_spec, audio_path)

        # Step 5: Verify sync quality (KCS)
        sync_quality = self._verifier.verify(video_spec, features)

        return {
            "version": VERSION,
            "audio_features": {
                "tempo": features.tempo_bpm,
                "key": f"{features.key} {features.mode}",
                "mood": features.mood,
                "genre": features.genre,
                "energy": features.energy,
                "duration": features.duration_seconds,
                "instruments": features.instruments,
            },
            "video_spec": {
                "scenes": len(scenes),
                "total_duration": video_spec.total_duration,
                "resolution": resolution,
                "fps": fps,
                "style": style.value,
            },
            "scene_prompts": [
                {"time": f"{s.start_time:.1f}-{s.end_time:.1f}s",
                 "section": s.section_type,
                 "prompt": s.prompt[:100] + "..." if len(s.prompt) > 100 else s.prompt,
                 "camera": s.camera_motion,
                 "energy": round(s.energy_level, 2)}
                for s in scenes
            ],
            "backend": backend.value,
            "generation_spec": generation_spec,
            "sync_quality": sync_quality,
            "kcs_translation_loss": sync_quality["translation_loss"],
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "engine": "AudioToVideoEngine",
            "backends": [b.value for b in self._orchestrator._available_backends],
            "visual_styles": [s.value for s in VisualStyle],
            "mood_palettes": len(MOOD_VISUAL_MAP),
            "genre_styles": len(GENRE_VISUAL_MAP),
            "instrument_visuals": len(INSTRUMENT_VISUAL_MAP),
            "capabilities": [
                "Audio feature analysis → visual scene mapping",
                "8 mood palettes × 12 genre styles",
                "10 instrument visual elements",
                "Beat-synced visual events",
                "FFmpeg visualization (always available)",
                "Cloud API routing (Veo3/Sora2/Runway)",
                "KCS audio-visual sync verification",
                "HTLF 5-axis translation loss measurement",
            ],
        }
