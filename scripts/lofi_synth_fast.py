#!/usr/bin/env python3
"""
LoFi Music Synthesizer — NumPy-accelerated version.
~10x faster than pure Python via vectorized operations.

Bottleneck fix: Nicolas "ボトルネックがあるんなら、改善して"
"""

import math
import os
import random
import struct
import time
import wave
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

SAMPLE_RATE = 44100
CHANNELS = 2

# ═══════════════════════════════════════════════════════════════
# Vectorized synthesis
# ═══════════════════════════════════════════════════════════════

def v_sine(freq: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq * t + phase)


def v_noise(n: int) -> np.ndarray:
    return np.random.uniform(-1, 1, n)


def v_soft_clip(x: np.ndarray, drive: float = 1.5) -> np.ndarray:
    return np.tanh(x * drive)


def v_adsr(t: np.ndarray, a: float, d: float, s_dur: float,
           r: float, s_level: float = 0.6) -> np.ndarray:
    """Vectorized ADSR envelope."""
    env = np.zeros_like(t)
    # Attack
    mask_a = t < a
    env[mask_a] = t[mask_a] / a
    # Decay
    mask_d = (t >= a) & (t < a + d)
    env[mask_d] = 1.0 - (1.0 - s_level) * ((t[mask_d] - a) / d)
    # Sustain
    mask_s = (t >= a + d) & (t < a + d + s_dur)
    env[mask_s] = s_level
    # Release
    total = a + d + s_dur
    mask_r = (t >= total) & (t < total + r)
    env[mask_r] = s_level * (1.0 - (t[mask_r] - total) / r)
    return env


def v_rhodes(freq: float, t: np.ndarray, vel: float = 0.7) -> np.ndarray:
    """Vectorized Rhodes FM synthesis."""
    mod = vel * 2.0 * v_sine(freq, t)
    carrier = v_sine(freq, t, mod)
    bell = 0.15 * v_sine(freq * 4, t) * np.exp(-t * 8)
    return (carrier + bell) * vel


def v_bass(freq: float, t: np.ndarray, vel: float = 0.8) -> np.ndarray:
    fundamental = v_sine(freq, t) * 0.7
    sub = v_sine(freq * 0.5, t) * 0.3
    pluck = np.exp(-t * 5) * v_sine(freq * 3, t) * 0.2
    return (fundamental + sub + pluck) * vel


def v_kick(t: np.ndarray, vel: float = 0.9) -> np.ndarray:
    freq = 150 * np.exp(-t * 30) + 45
    env = np.exp(-t * 8)
    click = np.exp(-t * 80) * 0.5 * v_noise(len(t))
    return (np.sin(2 * np.pi * freq * t) * env + click) * vel


def v_snare(t: np.ndarray, vel: float = 0.6) -> np.ndarray:
    body = v_sine(180, t) * np.exp(-t * 15) * 0.5
    rattle = v_noise(len(t)) * np.exp(-t * 10) * 0.4
    return (body + rattle) * vel


def v_hihat(t: np.ndarray, vel: float = 0.4, open_: bool = False) -> np.ndarray:
    decay = 0.15 if open_ else 0.04
    env = np.exp(-t / decay)
    return v_noise(len(t)) * env * vel * 0.3


# ═══════════════════════════════════════════════════════════════
# Music data
# ═══════════════════════════════════════════════════════════════

def midi_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


PROGRESSIONS = [
    [[57, 60, 64, 67], [53, 57, 60, 64], [60, 64, 67, 71], [55, 59, 62, 65]],
    [[64, 67, 71, 74], [57, 60, 64, 67], [62, 65, 69, 72], [55, 59, 62, 65]],
    [[60, 63, 67, 70], [53, 56, 60, 63], [58, 62, 65, 69], [51, 55, 58, 62]],
]


def generate_lofi_fast(output_path: str, duration_seconds: float = 102.0,
                        tempo: int = 75, prog_idx: int = -1) -> dict:
    """Generate LoFi WAV using NumPy vectorization."""
    t0 = time.time()

    if prog_idx < 0:
        prog_idx = random.randint(0, len(PROGRESSIONS) - 1)
    progression = PROGRESSIONS[prog_idx % len(PROGRESSIONS)]

    beat_dur = 60.0 / tempo
    bar_dur = beat_dur * 4
    total_samples = int(duration_seconds * SAMPLE_RATE)
    bars = int(duration_seconds / bar_dur)

    # Pre-allocate stereo buffer
    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)

    max_note_samples = int(bar_dur * SAMPLE_RATE)
    max_drum_samples = int(0.5 * SAMPLE_RATE)

    note_count = 0
    drum_count = 0

    for bar in range(bars):
        chord = progression[bar % len(progression)]
        bar_start = bar * bar_dur

        # ── Rhodes chords ──
        for midi_note in chord:
            freq = midi_to_freq(midi_note)
            start_s = bar_start + random.gauss(0, 0.008)
            start_idx = max(0, int(start_s * SAMPLE_RATE))
            dur_samples = int(bar_dur * 0.85 * SAMPLE_RATE)
            end_idx = min(start_idx + dur_samples, total_samples)
            n = end_idx - start_idx
            if n <= 0:
                continue

            t = np.arange(n) / SAMPLE_RATE
            vel = 0.25 + random.uniform(-0.05, 0.05)
            sig = v_rhodes(freq, t, vel)
            env = v_adsr(t, 0.01, 0.3, dur_samples/SAMPLE_RATE - 0.81, 0.5, 0.6)
            sig *= env

            pan = 0.5 + random.gauss(0, 0.05)
            pan = max(0.1, min(0.9, pan))
            left[start_idx:end_idx] += sig * (1 - pan)
            right[start_idx:end_idx] += sig * pan
            note_count += 1

        # Ghost chord (60%)
        if random.random() < 0.6:
            for midi_note in chord:
                freq = midi_to_freq(midi_note)
                start_s = bar_start + beat_dur * 2 + random.gauss(0, 0.01)
                start_idx = max(0, int(start_s * SAMPLE_RATE))
                dur_samples = int(beat_dur * 1.5 * SAMPLE_RATE)
                end_idx = min(start_idx + dur_samples, total_samples)
                n = end_idx - start_idx
                if n <= 0:
                    continue
                t = np.arange(n) / SAMPLE_RATE
                vel = 0.15 + random.uniform(-0.03, 0.03)
                sig = v_rhodes(freq, t, vel) * v_adsr(t, 0.01, 0.2, n/SAMPLE_RATE-0.51, 0.3, 0.5)
                left[start_idx:end_idx] += sig * 0.5
                right[start_idx:end_idx] += sig * 0.5
                note_count += 1

        # ── Bass ──
        root = chord[0] - 12
        for bass_note, offset, dur_beats in [(root, 0, 1.8), (root+7, 2.5, 1.2)]:
            freq = midi_to_freq(bass_note)
            start_s = bar_start + beat_dur * offset + random.gauss(0, 0.005)
            start_idx = max(0, int(start_s * SAMPLE_RATE))
            dur_samples = int(beat_dur * dur_beats * SAMPLE_RATE)
            end_idx = min(start_idx + dur_samples, total_samples)
            n = end_idx - start_idx
            if n <= 0:
                continue
            t = np.arange(n) / SAMPLE_RATE
            vel = 0.4 if offset == 0 else 0.3
            sig = v_bass(freq, t, vel) * v_adsr(t, 0.005, 0.15, n/SAMPLE_RATE-0.355, 0.2, 0.7)
            left[start_idx:end_idx] += sig
            right[start_idx:end_idx] += sig
            note_count += 1

        # ── Drums ──
        drum_defs = [
            (0, 'kick', 0.7),
            (beat_dur, 'snare', 0.45),
            (beat_dur * 3, 'snare', 0.5),
        ]
        if random.random() < 0.85:
            drum_defs.append((beat_dur * 2.5, 'kick', 0.6))

        for eighth in range(8):
            swing = 0.02 if eighth % 2 == 1 else 0.0
            vel = 0.25 if eighth % 2 == 0 else 0.12
            is_open = eighth in [3, 7] and random.random() < 0.15
            drum_defs.append((
                eighth * beat_dur / 2 + swing,
                'hihat_open' if is_open else 'hihat',
                vel + random.uniform(-0.03, 0.03)))

        for offset, dtype, vel in drum_defs:
            start_s = bar_start + offset + random.gauss(0, 0.003)
            start_idx = max(0, int(start_s * SAMPLE_RATE))
            end_idx = min(start_idx + max_drum_samples, total_samples)
            n = end_idx - start_idx
            if n <= 0:
                continue
            t = np.arange(n) / SAMPLE_RATE

            if dtype == 'kick':
                sig = v_kick(t, vel)
            elif dtype == 'snare':
                sig = v_snare(t, vel)
            elif dtype == 'hihat':
                sig = v_hihat(t, vel, False)
            elif dtype == 'hihat_open':
                sig = v_hihat(t, vel, True)
            else:
                continue

            left[start_idx:end_idx] += sig
            right[start_idx:end_idx] += sig
            drum_count += 1

    # ── Post-processing (vectorized) ──
    # Vinyl crackle
    crackle = np.zeros(total_samples)
    impulse_mask = np.random.random(total_samples) < 0.003
    crackle[impulse_mask] = np.random.uniform(-0.03, 0.03, impulse_mask.sum())
    crackle[~impulse_mask] = np.random.uniform(-0.001, 0.001, (~impulse_mask).sum())
    left += crackle
    right += crackle * 0.8

    # Soft clip
    left = v_soft_clip(left, 1.3)
    right = v_soft_clip(right, 1.3)

    # Lo-fi LPF (scipy IIR filter — fully vectorized)
    try:
        from scipy.signal import lfilter
        alpha = 0.15
        b = [alpha]
        a = [1.0, -(1.0 - alpha)]
        for _ in range(3):
            left_filtered = lfilter(b, a, left)
            right_filtered = lfilter(b, a, right)
            left = left * 0.6 + left_filtered * 0.4
            right = right * 0.6 + right_filtered * 0.4
    except ImportError:
        pass  # Skip LPF if scipy not available

    # Normalize
    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    if peak > 0:
        gain = 0.85 / peak
        left *= gain
        right *= gain

    # Write WAV
    left_16 = np.clip(left * 32767, -32767, 32767).astype(np.int16)
    right_16 = np.clip(right * 32767, -32767, 32767).astype(np.int16)
    interleaved = np.column_stack([left_16, right_16]).flatten()

    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(interleaved.tobytes())

    elapsed = time.time() - t0
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
        "notes_rendered": note_count,
        "drum_hits": drum_count,
        "render_time": round(elapsed, 2),
        "realtime_ratio": round(duration_seconds / elapsed, 1),
    }


if __name__ == "__main__":
    output_dir = "/Users/nicolas/work/katala/output"
    os.makedirs(output_dir, exist_ok=True)
    wav_path = os.path.join(output_dir, "lofi_chill_fast.wav")

    print("🎵 LoFi Chill Generator — NumPy Accelerated")
    print()
    result = generate_lofi_fast(wav_path, duration_seconds=102.0, tempo=75)
    print(f"  ✅ Generated: {result['output']}")
    print(f"  📦 Size: {result['size_mb']} MB")
    print(f"  ⏱  Duration: {result['duration']}s")
    print(f"  🚀 Render: {result['render_time']}s ({result['realtime_ratio']}x realtime)")
    print(f"  🎵 Notes: {result['notes_rendered']}, Drums: {result['drum_hits']}")
    print(f"  🎶 Progression: {result['progression']}")
