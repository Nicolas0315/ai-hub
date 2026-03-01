#!/usr/bin/env python3
"""
LoFi Music Synthesizer — Pure Python WAV generation.
No SoundFont needed. Direct waveform synthesis.

Generates warm LoFi chill beats with:
- Rhodes-like EP tones (FM synthesis)
- Muted bass (filtered sine)
- Lo-fi drums (noise + sine hits)
- Vinyl crackle overlay
- Tape saturation effect
"""

import math
import os
import random
import struct
import wave
from dataclasses import dataclass
from typing import List, Tuple

SAMPLE_RATE = 44100
CHANNELS = 2  # Stereo

# ═══════════════════════════════════════════════════════════════════
# Synthesis primitives
# ═══════════════════════════════════════════════════════════════════

def sine(freq: float, t: float, phase: float = 0.0) -> float:
    return math.sin(2 * math.pi * freq * t + phase)

def saw(freq: float, t: float) -> float:
    """Band-limited sawtooth approximation."""
    val = 0.0
    for k in range(1, 8):
        val += (-1)**k * math.sin(2 * math.pi * k * freq * t) / k
    return val * 0.5

def noise() -> float:
    return random.uniform(-1, 1)

def soft_clip(x: float, drive: float = 1.5) -> float:
    """Tape-style soft saturation."""
    return math.tanh(x * drive)

def lpf_sample(x: float, prev: float, cutoff_norm: float) -> float:
    """Simple 1-pole low-pass filter."""
    a = cutoff_norm
    return prev + a * (x - prev)

def adsr(t: float, a: float, d: float, s: float, r: float,
         dur: float, s_level: float = 0.6) -> float:
    """ADSR envelope."""
    if t < 0:
        return 0.0
    if t < a:
        return t / a
    t2 = t - a
    if t2 < d:
        return 1.0 - (1.0 - s_level) * (t2 / d)
    t3 = t - a - d
    sus_dur = dur - a - d - r
    if t3 < sus_dur:
        return s_level
    t4 = t - dur + r
    if t4 < r:
        return s_level * (1.0 - t4 / r)
    return 0.0

# ═══════════════════════════════════════════════════════════════════
# Instrument synths
# ═══════════════════════════════════════════════════════════════════

def rhodes_tone(freq: float, t: float, vel: float = 0.7) -> float:
    """Rhodes-like FM electric piano."""
    mod_ratio = 1.0
    mod_depth = vel * 2.0
    modulator = mod_depth * sine(freq * mod_ratio, t)
    carrier = sine(freq, t, modulator)
    # Add bell harmonics
    bell = 0.15 * sine(freq * 4, t) * math.exp(-t * 8)
    return (carrier + bell) * vel

def bass_tone(freq: float, t: float, vel: float = 0.8) -> float:
    """Warm muted bass — filtered sine + sub."""
    fundamental = sine(freq, t) * 0.7
    sub = sine(freq * 0.5, t) * 0.3
    # Gentle attack pluck
    pluck = math.exp(-t * 5) * sine(freq * 3, t) * 0.2
    return (fundamental + sub + pluck) * vel

def hihat(t: float, vel: float = 0.4, open_: bool = False) -> float:
    """Hi-hat — filtered noise."""
    decay = 0.15 if open_ else 0.04
    env = math.exp(-t / decay) if t >= 0 else 0
    n = noise()
    # Bandpass around 8kHz feel
    return n * env * vel * 0.3

def kick(t: float, vel: float = 0.9) -> float:
    """Kick drum — pitch-swept sine."""
    if t < 0:
        return 0.0
    freq = 150 * math.exp(-t * 30) + 45
    env = math.exp(-t * 8)
    click = math.exp(-t * 80) * 0.5 * noise()
    return (sine(freq, t) * env + click) * vel

def snare(t: float, vel: float = 0.6) -> float:
    """Snare — sine body + noise rattle."""
    if t < 0:
        return 0.0
    body = sine(180, t) * math.exp(-t * 15) * 0.5
    rattle = noise() * math.exp(-t * 10) * 0.4
    return (body + rattle) * vel

def vinyl_crackle() -> float:
    """Vinyl crackle — sparse impulse noise."""
    if random.random() < 0.003:
        return random.uniform(-0.03, 0.03)
    return random.uniform(-0.001, 0.001)

# ═══════════════════════════════════════════════════════════════════
# Music data
# ═══════════════════════════════════════════════════════════════════

def midi_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

# Chord progressions (MIDI notes) — classic lofi
PROGRESSIONS = [
    # Am7 → Fmaj7 → Cmaj7 → G7
    [[57, 60, 64, 67], [53, 57, 60, 64], [60, 64, 67, 71], [55, 59, 62, 65]],
    # Em7 → Am7 → Dm9 → G13
    [[64, 67, 71, 74], [57, 60, 64, 67], [62, 65, 69, 72], [55, 59, 62, 65]],
    # Cm7 → Fm7 → Bbmaj7 → Ebmaj7
    [[60, 63, 67, 70], [53, 56, 60, 63], [58, 62, 65, 69], [51, 55, 58, 62]],
]

@dataclass
class Note:
    start_sample: int
    freq: float
    duration_samples: int
    velocity: float
    instrument: str  # "rhodes", "bass"

@dataclass
class DrumHit:
    start_sample: int
    drum_type: str  # "kick", "snare", "hihat", "hihat_open"
    velocity: float

def generate_lofi_wav(output_path: str, duration_seconds: float = 102.0,
                       tempo: int = 75, prog_idx: int = -1) -> dict:
    """Generate a LoFi chill WAV file.

    Returns dict with generation metadata.
    """
    if prog_idx < 0:
        prog_idx = random.randint(0, len(PROGRESSIONS) - 1)
    progression = PROGRESSIONS[prog_idx % len(PROGRESSIONS)]

    beat_duration = 60.0 / tempo  # seconds per beat
    bar_duration = beat_duration * 4
    total_samples = int(duration_seconds * SAMPLE_RATE)
    bars = int(duration_seconds / bar_duration)

    # ── Schedule notes ──
    notes: List[Note] = []
    drums: List[DrumHit] = []

    for bar in range(bars):
        chord = progression[bar % len(progression)]
        bar_start_sec = bar * bar_duration

        # ── Rhodes chords ──
        # Hit on beat 1
        for midi_note in chord:
            freq = midi_to_freq(midi_note)
            start = int((bar_start_sec + random.gauss(0, 0.008)) * SAMPLE_RATE)
            dur = int((bar_duration * 0.85) * SAMPLE_RATE)
            vel = 0.25 + random.uniform(-0.05, 0.05)
            notes.append(Note(start, freq, dur, vel, "rhodes"))

        # Ghost chord on beat 3 (60% chance)
        if random.random() < 0.6:
            for midi_note in chord:
                freq = midi_to_freq(midi_note)
                start = int((bar_start_sec + beat_duration * 2 + random.gauss(0, 0.01)) * SAMPLE_RATE)
                dur = int((beat_duration * 1.5) * SAMPLE_RATE)
                vel = 0.15 + random.uniform(-0.03, 0.03)
                notes.append(Note(start, freq, dur, vel, "rhodes"))

        # ── Bass ──
        root = chord[0] - 12
        root_freq = midi_to_freq(root)
        start = int((bar_start_sec + random.gauss(0, 0.005)) * SAMPLE_RATE)
        dur = int((beat_duration * 1.8) * SAMPLE_RATE)
        notes.append(Note(start, root_freq, dur, 0.4, "bass"))

        # Walking bass note
        fifth = root + 7
        fifth_freq = midi_to_freq(fifth)
        start = int((bar_start_sec + beat_duration * 2.5 + random.gauss(0, 0.008)) * SAMPLE_RATE)
        dur = int((beat_duration * 1.2) * SAMPLE_RATE)
        notes.append(Note(start, fifth_freq, dur, 0.3, "bass"))

        # ── Drums ──
        # Kick on 1 and 2.5
        drums.append(DrumHit(
            int((bar_start_sec + random.gauss(0, 0.003)) * SAMPLE_RATE),
            "kick", 0.7))
        if random.random() < 0.85:
            drums.append(DrumHit(
                int((bar_start_sec + beat_duration * 2.5 + random.gauss(0, 0.005)) * SAMPLE_RATE),
                "kick", 0.6))

        # Snare on 2 and 4
        drums.append(DrumHit(
            int((bar_start_sec + beat_duration + random.gauss(0, 0.004)) * SAMPLE_RATE),
            "snare", 0.45))
        drums.append(DrumHit(
            int((bar_start_sec + beat_duration * 3 + random.gauss(0, 0.004)) * SAMPLE_RATE),
            "snare", 0.5))

        # Hi-hats: 8th notes with swing
        for eighth in range(8):
            swing = 0.02 if eighth % 2 == 1 else 0.0
            t_sec = bar_start_sec + eighth * (beat_duration / 2) + swing
            vel = 0.25 if eighth % 2 == 0 else 0.12  # Ghost on off-beats
            is_open = eighth in [3, 7] and random.random() < 0.15
            drums.append(DrumHit(
                int((t_sec + random.gauss(0, 0.003)) * SAMPLE_RATE),
                "hihat_open" if is_open else "hihat",
                vel + random.uniform(-0.03, 0.03)))

    # ── Render audio ──
    print(f"  Rendering {total_samples} samples ({duration_seconds:.1f}s)...")
    left = [0.0] * total_samples
    right = [0.0] * total_samples

    # Render notes
    for note in notes:
        for i in range(note.duration_samples):
            idx = note.start_sample + i
            if 0 <= idx < total_samples:
                t = i / SAMPLE_RATE
                env = adsr(t, 0.01, 0.3, note.duration_samples / SAMPLE_RATE, 0.5, note.duration_samples / SAMPLE_RATE, 0.6)
                if note.instrument == "rhodes":
                    sample = rhodes_tone(note.freq, t, note.velocity) * env
                else:
                    sample = bass_tone(note.freq, t, note.velocity) * env

                # Slight stereo spread
                pan = 0.5 + random.gauss(0, 0.05) if note.instrument == "rhodes" else 0.5
                pan = max(0, min(1, pan))
                left[idx] += sample * (1 - pan)
                right[idx] += sample * pan

    # Render drums
    drum_samples = int(0.5 * SAMPLE_RATE)  # max 0.5s per hit
    for hit in drums:
        for i in range(drum_samples):
            idx = hit.start_sample + i
            if 0 <= idx < total_samples:
                t = i / SAMPLE_RATE
                if hit.drum_type == "kick":
                    s = kick(t, hit.velocity)
                elif hit.drum_type == "snare":
                    s = snare(t, hit.velocity)
                elif hit.drum_type == "hihat":
                    s = hihat(t, hit.velocity, open_=False)
                elif hit.drum_type == "hihat_open":
                    s = hihat(t, hit.velocity, open_=True)
                else:
                    s = 0.0
                left[idx] += s
                right[idx] += s

    # Add vinyl crackle + soft saturation
    print("  Adding vinyl warmth...")
    lpf_l = 0.0
    lpf_r = 0.0
    for i in range(total_samples):
        # Vinyl crackle
        crackle = vinyl_crackle()
        left[i] += crackle
        right[i] += crackle * 0.8

        # Soft clip (tape saturation)
        left[i] = soft_clip(left[i], 1.3)
        right[i] = soft_clip(right[i], 1.3)

        # Gentle low-pass for lo-fi warmth
        lpf_l = lpf_sample(left[i], lpf_l, 0.15)
        lpf_r = lpf_sample(right[i], lpf_r, 0.15)
        left[i] = left[i] * 0.6 + lpf_l * 0.4
        right[i] = right[i] * 0.6 + lpf_r * 0.4

    # Normalize
    peak = max(max(abs(s) for s in left), max(abs(s) for s in right))
    if peak > 0:
        gain = 0.85 / peak
        left = [s * gain for s in left]
        right = [s * gain for s in right]

    # Write WAV
    print(f"  Writing WAV to {output_path}...")
    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)

        frames = bytearray()
        for i in range(total_samples):
            l_int = max(-32767, min(32767, int(left[i] * 32767)))
            r_int = max(-32767, min(32767, int(right[i] * 32767)))
            frames.extend(struct.pack('<hh', l_int, r_int))
        wf.writeframes(bytes(frames))

    file_size = os.path.getsize(output_path)

    chord_names = {
        0: "Am7 → Fmaj7 → Cmaj7 → G7",
        1: "Em7 → Am7 → Dm9 → G13",
        2: "Cm7 → Fm7 → Bbmaj7 → Ebmaj7",
    }

    return {
        "output": output_path,
        "size_mb": round(file_size / (1024 * 1024), 1),
        "duration": round(duration_seconds, 1),
        "tempo": tempo,
        "bars": bars,
        "progression": chord_names.get(prog_idx, "?"),
        "notes_rendered": len(notes),
        "drum_hits": len(drums),
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "features": [
            "FM Rhodes electric piano",
            "Warm filtered bass",
            "Boom-bap drums with swing",
            "Humanized timing + velocity",
            "Vinyl crackle",
            "Tape soft-saturation",
            "Lo-fi low-pass warmth",
            "Stereo spread",
        ],
    }


if __name__ == "__main__":
    output_dir = "/Users/nicolas/work/katala/output"
    os.makedirs(output_dir, exist_ok=True)

    wav_path = os.path.join(output_dir, "lofi_chill.wav")

    print("🎵 LoFi Chill Generator — Pure Python Synthesis")
    print()

    result = generate_lofi_wav(wav_path, duration_seconds=102.0, tempo=75)

    print()
    print(f"  ✅ Generated: {result['output']}")
    print(f"  📦 Size:       {result['size_mb']} MB")
    print(f"  ⏱  Duration:   {result['duration']}s")
    print(f"  🎵 Tempo:      {result['tempo']} BPM")
    print(f"  🎹 Bars:       {result['bars']}")
    print(f"  🎶 Progression: {result['progression']}")
    print(f"  🎼 Notes:      {result['notes_rendered']}")
    print(f"  🥁 Drum hits:  {result['drum_hits']}")
    print()
    print("  Features:")
    for f in result['features']:
        print(f"    ✦ {f}")
    print()
    print("Done! 🐻‍❄️")
