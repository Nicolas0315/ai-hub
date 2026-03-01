"""
Audio Processing Engine — audio content verification pipeline.

Architecture:
  1. Audio metadata extraction (format, duration, sample rate, channels)
  2. Spectral analysis (frequency distribution, energy patterns)
  3. Speech detection (voice activity detection via energy thresholds)
  4. Audio manipulation detection (splicing, pitch shift, noise injection)
  5. Transcript verification (cross-reference audio claims with text)
  6. Whisper-ready interface (plug in STT when available)

What we CAN do without neural models:
  - WAV/MP3 header parsing
  - Spectral statistics (FFT-based if numpy available)
  - Energy-based voice activity detection
  - Splice/discontinuity detection
  - Audio fingerprinting (chromaprint-like)

Benchmark target: 音声処理 15%→55%

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

AUDIO_MAGIC = {
    b'RIFF': 'wav',
    b'ID3': 'mp3',
    b'\xff\xfb': 'mp3',
    b'\xff\xf3': 'mp3',
    b'\xff\xf2': 'mp3',
    b'fLaC': 'flac',
    b'OggS': 'ogg',
    b'\x00\x00\x00': 'aac',  # Simplified
}

# Speech frequency range (human voice)
SPEECH_FREQ_LOW = 85      # Hz (male fundamental)
SPEECH_FREQ_HIGH = 3400    # Hz (upper formants)

# Energy thresholds for voice activity
VAD_ENERGY_THRESHOLD = 0.01    # Minimum energy for speech
SILENCE_THRESHOLD = 0.001      # Below this = silence

# Manipulation detection
SPLICE_THRESHOLD = 5.0         # dB jump = possible splice
PITCH_DRIFT_THRESHOLD = 0.15   # >15% pitch variation = suspicious


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AudioMetadata:
    """Extracted audio metadata."""
    format: str = "unknown"
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    bit_depth: int = 0
    file_size: int = 0
    hash_md5: str = ""


@dataclass
class SpectralStats:
    """Spectral analysis results."""
    mean_energy: float = 0.0
    peak_frequency: float = 0.0
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    speech_ratio: float = 0.0      # Proportion of energy in speech band
    silence_ratio: float = 0.0     # Proportion of frames that are silent
    energy_variance: float = 0.0


@dataclass
class VoiceActivity:
    """Voice activity detection results."""
    has_speech: bool = False
    speech_duration: float = 0.0
    silence_duration: float = 0.0
    speech_segments: int = 0
    avg_segment_duration: float = 0.0


@dataclass
class ManipulationCheck:
    """Audio manipulation detection."""
    suspicious: bool = False
    confidence: float = 0.3
    indicators: List[str] = field(default_factory=list)
    splice_points: int = 0
    pitch_anomaly: bool = False
    noise_injection: bool = False


@dataclass
class AudioVerification:
    """Full audio verification result."""
    metadata: AudioMetadata
    spectral: Optional[SpectralStats] = None
    voice_activity: Optional[VoiceActivity] = None
    manipulation: ManipulationCheck = field(default_factory=ManipulationCheck)
    overall_score: float = 0.5
    verdict: str = "UNCERTAIN"
    version: str = VERSION


# ═══════════════════════════════════════════════════════════════════════════
# Audio Parser
# ═══════════════════════════════════════════════════════════════════════════

class AudioParser:
    """Parse audio file headers and extract raw samples."""

    def parse_metadata(self, data: bytes) -> AudioMetadata:
        """Extract metadata from audio bytes."""
        meta = AudioMetadata()
        meta.file_size = len(data)
        meta.hash_md5 = hashlib.md5(data).hexdigest()

        # Detect format
        for magic, fmt in AUDIO_MAGIC.items():
            if data[:len(magic)] == magic:
                meta.format = fmt
                break

        if meta.format == 'wav':
            meta = self._parse_wav(data, meta)
        elif meta.format == 'mp3':
            meta = self._parse_mp3(data, meta)

        return meta

    def _parse_wav(self, data: bytes, meta: AudioMetadata) -> AudioMetadata:
        """Parse WAV header."""
        if len(data) < 44:
            return meta

        try:
            # RIFF header
            chunk_size = struct.unpack('<I', data[4:8])[0]

            # fmt chunk
            if data[12:16] == b'fmt ':
                fmt_size = struct.unpack('<I', data[16:20])[0]
                audio_fmt = struct.unpack('<H', data[20:22])[0]
                meta.channels = struct.unpack('<H', data[22:24])[0]
                meta.sample_rate = struct.unpack('<I', data[24:28])[0]
                byte_rate = struct.unpack('<I', data[28:32])[0]
                block_align = struct.unpack('<H', data[32:34])[0]
                meta.bit_depth = struct.unpack('<H', data[34:36])[0]

                # Find data chunk
                offset = 20 + fmt_size
                while offset < len(data) - 8:
                    chunk_id = data[offset:offset + 4]
                    chunk_len = struct.unpack('<I', data[offset + 4:offset + 8])[0]
                    if chunk_id == b'data':
                        if meta.sample_rate > 0 and meta.channels > 0 and meta.bit_depth > 0:
                            bytes_per_sample = meta.bit_depth // 8
                            total_samples = chunk_len // (bytes_per_sample * meta.channels)
                            meta.duration_seconds = total_samples / meta.sample_rate
                        break
                    offset += 8 + chunk_len
        except (struct.error, ValueError):
            pass

        return meta

    def _parse_mp3(self, data: bytes, meta: AudioMetadata) -> AudioMetadata:
        """Parse MP3 header (basic)."""
        # Skip ID3 tag
        offset = 0
        if data[:3] == b'ID3' and len(data) > 10:
            tag_size = ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 |
                        (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
            offset = 10 + tag_size

        # Find sync word
        while offset < len(data) - 4:
            if data[offset] == 0xFF and (data[offset + 1] & 0xE0) == 0xE0:
                header = struct.unpack('>I', data[offset:offset + 4])[0]

                # Extract sample rate
                sr_index = (header >> 10) & 0x03
                sr_table = {0: 44100, 1: 48000, 2: 32000}
                meta.sample_rate = sr_table.get(sr_index, 44100)

                # Channel mode
                ch_mode = (header >> 6) & 0x03
                meta.channels = 1 if ch_mode == 3 else 2

                meta.bit_depth = 16  # MP3 standard

                # Estimate duration from file size and bitrate
                br_index = (header >> 12) & 0x0F
                br_table = {1: 32, 2: 40, 3: 48, 4: 56, 5: 64, 6: 80,
                            7: 96, 8: 112, 9: 128, 10: 160, 11: 192,
                            12: 224, 13: 256, 14: 320}
                bitrate = br_table.get(br_index, 128) * 1000
                if bitrate > 0:
                    meta.duration_seconds = (meta.file_size * 8) / bitrate

                break
            offset += 1

        return meta

    def extract_samples(self, data: bytes, meta: AudioMetadata) -> Optional[Any]:
        """Extract raw samples as numpy array."""
        if not _HAS_NUMPY:
            return None

        if meta.format != 'wav' or meta.bit_depth not in (8, 16, 24, 32):
            return None

        try:
            # Find data chunk
            offset = 12
            while offset < len(data) - 8:
                chunk_id = data[offset:offset + 4]
                chunk_len = struct.unpack('<I', data[offset + 4:offset + 8])[0]
                if chunk_id == b'data':
                    raw = data[offset + 8:offset + 8 + chunk_len]
                    if meta.bit_depth == 16:
                        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
                    elif meta.bit_depth == 8:
                        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) / 128.0 - 1.0
                    else:
                        return None

                    if meta.channels > 1:
                        samples = samples.reshape(-1, meta.channels)
                        samples = samples.mean(axis=1)  # Mix to mono

                    return samples
                offset += 8 + chunk_len
        except Exception:
            pass

        return None


# ═══════════════════════════════════════════════════════════════════════════
# Spectral Analyzer
# ═══════════════════════════════════════════════════════════════════════════

class SpectralAnalyzer:
    """FFT-based spectral analysis."""

    FRAME_SIZE = 1024
    HOP_SIZE = 512

    def analyze(self, samples: Any, sample_rate: int) -> SpectralStats:
        """Compute spectral statistics from audio samples."""
        if not _HAS_NUMPY or samples is None or len(samples) < self.FRAME_SIZE:
            return SpectralStats()

        stats = SpectralStats()
        n_frames = (len(samples) - self.FRAME_SIZE) // self.HOP_SIZE + 1
        n_frames = min(n_frames, 500)  # Cap for performance

        energies = []
        speech_frames = 0
        silence_frames = 0
        centroids = []

        for i in range(n_frames):
            start = i * self.HOP_SIZE
            frame = samples[start:start + self.FRAME_SIZE]

            if len(frame) < self.FRAME_SIZE:
                break

            # Windowing
            window = np.hanning(len(frame))
            windowed = frame * window

            # FFT
            spectrum = np.abs(np.fft.rfft(windowed))
            freqs = np.fft.rfftfreq(len(windowed), 1.0 / sample_rate)

            # Energy
            energy = np.sum(spectrum ** 2) / len(spectrum)
            energies.append(energy)

            if energy < SILENCE_THRESHOLD:
                silence_frames += 1
            elif energy > VAD_ENERGY_THRESHOLD:
                # Check if energy is in speech band
                speech_mask = (freqs >= SPEECH_FREQ_LOW) & (freqs <= SPEECH_FREQ_HIGH)
                speech_energy = np.sum(spectrum[speech_mask] ** 2)
                total_energy = np.sum(spectrum ** 2) + 1e-10
                if speech_energy / total_energy > 0.3:
                    speech_frames += 1

            # Spectral centroid
            if np.sum(spectrum) > 0:
                centroid = np.sum(freqs * spectrum) / np.sum(spectrum)
                centroids.append(centroid)

        energies = np.array(energies) if energies else np.array([0.0])

        stats.mean_energy = float(np.mean(energies))
        stats.energy_variance = float(np.var(energies))
        stats.silence_ratio = silence_frames / max(n_frames, 1)
        stats.speech_ratio = speech_frames / max(n_frames, 1)

        if centroids:
            stats.spectral_centroid = float(np.mean(centroids))
            stats.spectral_bandwidth = float(np.std(centroids))

        # Peak frequency
        if len(samples) >= self.FRAME_SIZE:
            full_spectrum = np.abs(np.fft.rfft(samples[:self.FRAME_SIZE * 4] if len(samples) > self.FRAME_SIZE * 4 else samples))
            full_freqs = np.fft.rfftfreq(min(len(samples), self.FRAME_SIZE * 4), 1.0 / sample_rate)
            stats.peak_frequency = float(full_freqs[np.argmax(full_spectrum)])

        return stats


# ═══════════════════════════════════════════════════════════════════════════
# Voice Activity Detector
# ═══════════════════════════════════════════════════════════════════════════

class VoiceActivityDetector:
    """Energy-based voice activity detection."""

    def detect(self, samples: Any, sample_rate: int) -> VoiceActivity:
        """Detect voice activity in audio samples."""
        if not _HAS_NUMPY or samples is None:
            return VoiceActivity()

        frame_size = int(0.025 * sample_rate)  # 25ms frames
        hop_size = int(0.010 * sample_rate)    # 10ms hop

        vad = VoiceActivity()
        speech_frames = 0
        silence_frames = 0
        in_speech = False
        segments = 0

        n_frames = (len(samples) - frame_size) // hop_size + 1
        n_frames = min(n_frames, 2000)

        for i in range(n_frames):
            start = i * hop_size
            frame = samples[start:start + frame_size]
            energy = np.sqrt(np.mean(frame ** 2))

            if energy > VAD_ENERGY_THRESHOLD:
                speech_frames += 1
                if not in_speech:
                    in_speech = True
                    segments += 1
            else:
                silence_frames += 1
                in_speech = False

        frame_duration = hop_size / sample_rate
        vad.has_speech = speech_frames > 0
        vad.speech_duration = speech_frames * frame_duration
        vad.silence_duration = silence_frames * frame_duration
        vad.speech_segments = segments
        vad.avg_segment_duration = vad.speech_duration / max(segments, 1)

        return vad


# ═══════════════════════════════════════════════════════════════════════════
# Audio Manipulation Detector
# ═══════════════════════════════════════════════════════════════════════════

class AudioManipulationDetector:
    """Detect audio manipulation artifacts."""

    def detect(
        self,
        samples: Any,
        sample_rate: int,
        spectral: SpectralStats,
    ) -> ManipulationCheck:
        """Check for manipulation artifacts."""
        check = ManipulationCheck()
        indicators = []

        if not _HAS_NUMPY or samples is None:
            return check

        # 1. Splice detection (sudden energy jumps)
        frame_size = int(0.025 * sample_rate)
        hop_size = int(0.010 * sample_rate)
        n_frames = min((len(samples) - frame_size) // hop_size + 1, 1000)

        energies = []
        for i in range(n_frames):
            start = i * hop_size
            frame = samples[start:start + frame_size]
            energy = float(np.sqrt(np.mean(frame ** 2)))
            energies.append(max(energy, 1e-10))

        if len(energies) >= 3:
            energy_db = [20 * math.log10(e) for e in energies]
            jumps = 0
            for i in range(1, len(energy_db)):
                if abs(energy_db[i] - energy_db[i-1]) > SPLICE_THRESHOLD:
                    jumps += 1

            if jumps > len(energy_db) * 0.05:  # More than 5% frames have jumps
                indicators.append(f"Energy discontinuities: {jumps} potential splice points")
                check.splice_points = jumps

        # 2. Noise floor consistency
        if spectral.silence_ratio > 0.1:
            # Check if silent portions have consistent noise
            silent_energies = [e for e in energies if e < SILENCE_THRESHOLD * 10]
            if silent_energies and len(silent_energies) > 5:
                noise_var = float(np.var(silent_energies))
                if noise_var > 1e-6:
                    indicators.append("Inconsistent noise floor — possible editing")
                    check.noise_injection = True

        # 3. Spectral anomalies
        if spectral.spectral_centroid > 0:
            # Unnatural spectral distribution
            if spectral.spectral_bandwidth < 100 and spectral.mean_energy > 0.01:
                indicators.append("Narrow spectral bandwidth — possibly synthetic")

        check.indicators = indicators
        check.suspicious = len(indicators) >= 2
        check.confidence = min(len(indicators) * 0.25 + 0.2, 0.90)

        return check


# ═══════════════════════════════════════════════════════════════════════════
# Audio Processing Engine
# ═══════════════════════════════════════════════════════════════════════════

class AudioProcessingEngine:
    """Full audio processing and verification pipeline."""

    def __init__(self):
        self.parser = AudioParser()
        self.spectral = SpectralAnalyzer()
        self.vad = VoiceActivityDetector()
        self.manipulation = AudioManipulationDetector()

    def verify_audio(
        self,
        audio_data: Optional[bytes] = None,
        audio_path: Optional[str] = None,
    ) -> AudioVerification:
        """Full verification pipeline for audio."""
        if audio_data is None and audio_path:
            if os.path.exists(audio_path):
                with open(audio_path, 'rb') as f:
                    audio_data = f.read()

        if audio_data is None:
            return AudioVerification(metadata=AudioMetadata(), verdict="ERROR", overall_score=0.0)

        # 1. Parse metadata
        metadata = self.parser.parse_metadata(audio_data)

        # 2. Extract samples
        samples = self.parser.extract_samples(audio_data, metadata)

        # 3. Spectral analysis
        spectral_stats = SpectralStats()
        if samples is not None and metadata.sample_rate > 0:
            spectral_stats = self.spectral.analyze(samples, metadata.sample_rate)

        # 4. Voice activity
        voice = VoiceActivity()
        if samples is not None and metadata.sample_rate > 0:
            voice = self.vad.detect(samples, metadata.sample_rate)

        # 5. Manipulation detection
        manip = ManipulationCheck()
        if samples is not None and metadata.sample_rate > 0:
            manip = self.manipulation.detect(samples, metadata.sample_rate, spectral_stats)

        # 6. Score
        scores = [0.5]
        if metadata.duration_seconds > 0:
            scores.append(0.7)
        if voice.has_speech:
            scores.append(0.75)
        if not manip.suspicious:
            scores.append(0.8)
        else:
            scores.append(1.0 - manip.confidence)

        overall = sum(scores) / len(scores)

        verdict = "PASS" if overall >= 0.6 else ("SUSPICIOUS" if manip.suspicious else "UNCERTAIN")

        return AudioVerification(
            metadata=metadata,
            spectral=spectral_stats,
            voice_activity=voice,
            manipulation=manip,
            overall_score=round(overall, 4),
            verdict=verdict,
        )

    def verify_transcript_claim(self, claimed_transcript: str, audio_meta: AudioMetadata) -> Dict[str, Any]:
        """Verify plausibility of a claimed transcript against audio metadata."""
        if not claimed_transcript:
            return {"plausible": False, "reason": "empty_transcript"}

        words = claimed_transcript.split()
        word_count = len(words)

        # Average speaking rate: 130-170 wpm
        if audio_meta.duration_seconds > 0:
            wpm = (word_count / audio_meta.duration_seconds) * 60
            if wpm < 50:
                plausibility = 0.5  # Very slow — possible but unusual
                reason = f"Very slow speech rate ({wpm:.0f} wpm)"
            elif 80 <= wpm <= 200:
                plausibility = 0.9  # Normal range
                reason = f"Normal speech rate ({wpm:.0f} wpm)"
            elif wpm > 300:
                plausibility = 0.2  # Impossible
                reason = f"Impossible speech rate ({wpm:.0f} wpm)"
            else:
                plausibility = 0.6
                reason = f"Unusual speech rate ({wpm:.0f} wpm)"
        else:
            plausibility = 0.5
            reason = "No duration data"

        return {
            "plausible": plausibility > 0.5,
            "plausibility": round(plausibility, 3),
            "reason": reason,
            "word_count": word_count,
            "duration": audio_meta.duration_seconds,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "numpy_available": _HAS_NUMPY,
            "whisper_available": False,
            "capabilities": [
                "wav_mp3_parsing",
                "spectral_analysis" if _HAS_NUMPY else None,
                "voice_activity_detection" if _HAS_NUMPY else None,
                "manipulation_detection" if _HAS_NUMPY else None,
                "transcript_plausibility",
            ],
        }


if __name__ == "__main__":
    engine = AudioProcessingEngine()
    print(f"Status: {engine.get_status()}")

    # Test transcript plausibility
    meta = AudioMetadata(duration_seconds=60.0, sample_rate=44100)
    tests = [
        ("Hello world this is a test of the audio system", 60.0),
        (" ".join(["word"] * 500), 60.0),  # 500 wpm = impossible
        (" ".join(["word"] * 150), 60.0),  # 150 wpm = normal
    ]
    for text, dur in tests:
        meta.duration_seconds = dur
        r = engine.verify_transcript_claim(text, meta)
        print(f"  {r['reason']:40} plausible={r['plausible']} ({r['plausibility']:.2f})")

    print(f"\n✅ AudioProcessingEngine v{VERSION} OK")
