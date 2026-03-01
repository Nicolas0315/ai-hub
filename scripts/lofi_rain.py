#!/usr/bin/env python3
"""
LoFi Rain — Rainy chill beats with ambient rain sounds.
Youta: "雨音入りでよろ"
NumPy + scipy accelerated (81x realtime base).
"""

import math
import os
import random
import time
import wave

import numpy as np
from scipy.signal import lfilter

SAMPLE_RATE = 44100
CHANNELS = 2


def v_sine(freq, t, phase=0.0):
    return np.sin(2 * np.pi * freq * t + phase)


def v_soft_clip(x, drive=1.5):
    return np.tanh(x * drive)


def v_adsr(t, a, d, s_dur, r, s_level=0.6):
    env = np.zeros_like(t)
    env[t < a] = t[t < a] / a
    mask_d = (t >= a) & (t < a + d)
    env[mask_d] = 1.0 - (1.0 - s_level) * ((t[mask_d] - a) / d)
    mask_s = (t >= a + d) & (t < a + d + s_dur)
    env[mask_s] = s_level
    total = a + d + s_dur
    mask_r = (t >= total) & (t < total + r)
    env[mask_r] = s_level * (1.0 - (t[mask_r] - total) / r)
    return env


def v_rhodes(freq, t, vel=0.7):
    mod = vel * 2.0 * v_sine(freq, t)
    carrier = v_sine(freq, t, mod)
    bell = 0.15 * v_sine(freq * 4, t) * np.exp(-t * 8)
    return (carrier + bell) * vel


def v_bass(freq, t, vel=0.8):
    fundamental = v_sine(freq, t) * 0.7
    sub = v_sine(freq * 0.5, t) * 0.3
    pluck = np.exp(-t * 5) * v_sine(freq * 3, t) * 0.2
    return (fundamental + sub + pluck) * vel


def v_kick(t, vel=0.9):
    freq = 150 * np.exp(-t * 30) + 45
    env = np.exp(-t * 8)
    click = np.exp(-t * 80) * 0.5 * np.random.uniform(-1, 1, len(t))
    return (np.sin(2 * np.pi * freq * t) * env + click) * vel


def v_snare(t, vel=0.6):
    body = v_sine(180, t) * np.exp(-t * 15) * 0.5
    rattle = np.random.uniform(-1, 1, len(t)) * np.exp(-t * 10) * 0.4
    return (body + rattle) * vel


def v_hihat(t, vel=0.4, open_=False):
    decay = 0.15 if open_ else 0.04
    env = np.exp(-t / decay)
    return np.random.uniform(-1, 1, len(t)) * env * vel * 0.3


def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


# ═══════════════════════════════════════════════════════════════
# Rain synthesis
# ═══════════════════════════════════════════════════════════════

def generate_rain(total_samples: int, intensity: float = 0.7) -> tuple:
    """Generate stereo rain ambience.

    Components:
    - Continuous rain (filtered white noise)
    - Individual raindrop impacts (random pings)
    - Distant thunder rumbles (rare)
    - Puddle drips (random LP filtered drops)
    """
    left = np.zeros(total_samples)
    right = np.zeros(total_samples)

    # 1. Continuous rain — band-pass filtered noise
    rain_noise_l = np.random.normal(0, 1, total_samples) * 0.08 * intensity
    rain_noise_r = np.random.normal(0, 1, total_samples) * 0.08 * intensity

    # Low-pass filter for rain character (softer than white noise)
    alpha = 0.05
    b_lp = [alpha]
    a_lp = [1.0, -(1.0 - alpha)]
    for _ in range(4):  # Multi-pass for steeper rolloff
        rain_noise_l = lfilter(b_lp, a_lp, rain_noise_l)
        rain_noise_r = lfilter(b_lp, a_lp, rain_noise_r)

    # Add some high-frequency sizzle
    sizzle_l = np.random.normal(0, 1, total_samples) * 0.02 * intensity
    sizzle_r = np.random.normal(0, 1, total_samples) * 0.02 * intensity
    alpha_hp = 0.8
    b_hp = [alpha_hp]
    a_hp = [1.0, -(1.0 - alpha_hp)]
    sizzle_l = sizzle_l - lfilter(b_hp, a_hp, sizzle_l)
    sizzle_r = sizzle_r - lfilter(b_hp, a_hp, sizzle_r)

    left += rain_noise_l + sizzle_l
    right += rain_noise_r + sizzle_r

    # 2. Individual raindrop impacts
    n_drops = int(total_samples / SAMPLE_RATE * 15 * intensity)
    for _ in range(n_drops):
        pos = random.randint(0, total_samples - SAMPLE_RATE // 10)
        length = random.randint(SAMPLE_RATE // 100, SAMPLE_RATE // 20)
        end = min(pos + length, total_samples)
        n = end - pos

        t = np.arange(n) / SAMPLE_RATE
        freq = random.uniform(2000, 6000)
        amp = random.uniform(0.01, 0.04) * intensity
        drop = np.sin(2 * np.pi * freq * t) * np.exp(-t * random.uniform(30, 80)) * amp

        pan = random.uniform(0.1, 0.9)
        left[pos:end] += drop * (1 - pan)
        right[pos:end] += drop * pan

    # 3. Distant thunder (rare, every 20-40 seconds)
    thunder_interval = SAMPLE_RATE * random.randint(20, 40)
    pos = random.randint(SAMPLE_RATE * 5, total_samples // 2)
    while pos < total_samples - SAMPLE_RATE * 4:
        length = int(SAMPLE_RATE * random.uniform(2.0, 4.0))
        end = min(pos + length, total_samples)
        n = end - pos

        t = np.arange(n) / SAMPLE_RATE
        # Thunder = very low frequency rumble
        rumble = np.zeros(n)
        for f in [30, 45, 60, 80]:
            rumble += np.sin(2 * np.pi * f * t + random.uniform(0, 6.28)) * random.uniform(0.01, 0.03)
        rumble *= np.exp(-t * 0.8) * intensity * 0.5

        # Random noise bursts within thunder
        noise_env = np.exp(-((t - random.uniform(0.2, 1.0)) ** 2) / 0.3)
        rumble += np.random.normal(0, 0.01, n) * noise_env * intensity

        left[pos:end] += rumble
        right[pos:end] += rumble * 0.9  # Slightly offset for spatial effect
        pos += thunder_interval + random.randint(-SAMPLE_RATE * 5, SAMPLE_RATE * 5)

    # 4. Slow volume modulation (rain intensity waves)
    wave_period = SAMPLE_RATE * random.uniform(8, 15)
    t_full = np.arange(total_samples) / wave_period
    mod = 0.7 + 0.3 * np.sin(2 * np.pi * t_full)
    left *= mod
    right *= mod

    return left, right


def generate_lofi_rain(output_path: str, duration_seconds: float = 120.0,
                        tempo: int = 72, rain_intensity: float = 0.7) -> dict:
    """Generate LoFi chill beats with rain ambience."""
    t0 = time.time()

    # Rainy jazz progressions (darker voicings)
    progressions = [
        [[57, 60, 64, 67], [53, 57, 60, 65], [60, 63, 67, 70], [55, 58, 62, 65]],  # Am7→Fmaj9→Cm7→Gm7
        [[62, 65, 69, 72], [57, 60, 64, 67], [60, 63, 67, 70], [55, 59, 62, 65]],   # Dm7→Am7→Cm7→G7
        [[64, 67, 71, 74], [60, 63, 67, 70], [57, 60, 64, 67], [53, 57, 60, 64]],   # Em7→Cm7→Am7→Fmaj7
    ]
    progression = random.choice(progressions)
    beat_dur = 60.0 / tempo
    bar_dur = beat_dur * 4
    total_samples = int(duration_seconds * SAMPLE_RATE)
    bars = int(duration_seconds / bar_dur)

    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)
    max_drum_samples = int(0.5 * SAMPLE_RATE)

    note_count = 0
    drum_count = 0

    for bar in range(bars):
        chord = progression[bar % len(progression)]
        bar_start = bar * bar_dur

        # Rhodes — softer, more reverb-y for rain mood
        for midi_note in chord:
            freq = midi_to_freq(midi_note)
            start_s = bar_start + random.gauss(0, 0.012)  # More timing drift
            start_idx = max(0, int(start_s * SAMPLE_RATE))
            dur_samples = int(bar_dur * 0.9 * SAMPLE_RATE)
            end_idx = min(start_idx + dur_samples, total_samples)
            n = end_idx - start_idx
            if n <= 0:
                continue
            t = np.arange(n) / SAMPLE_RATE
            vel = 0.20 + random.uniform(-0.04, 0.04)  # Quieter for rain
            sig = v_rhodes(freq, t, vel)
            env = v_adsr(t, 0.02, 0.4, n / SAMPLE_RATE - 0.92, 0.5, 0.55)
            sig *= env
            pan = 0.5 + random.gauss(0, 0.08)
            pan = max(0.1, min(0.9, pan))
            left[start_idx:end_idx] += sig * (1 - pan)
            right[start_idx:end_idx] += sig * pan
            note_count += 1

        # Bass — rounder, less attack for rain
        root = chord[0] - 12
        freq = midi_to_freq(root)
        start_s = bar_start + random.gauss(0, 0.005)
        start_idx = max(0, int(start_s * SAMPLE_RATE))
        dur_samples = int(beat_dur * 2.5 * SAMPLE_RATE)
        end_idx = min(start_idx + dur_samples, total_samples)
        n = end_idx - start_idx
        if n > 0:
            t = np.arange(n) / SAMPLE_RATE
            sig = v_bass(freq, t, 0.35)
            sig *= v_adsr(t, 0.01, 0.2, n / SAMPLE_RATE - 0.51, 0.3, 0.65)
            left[start_idx:end_idx] += sig
            right[start_idx:end_idx] += sig
            note_count += 1

        # Drums — sparser, softer for rain
        if bar % 2 == 0 or random.random() < 0.7:
            drum_defs = [(0, 'kick', 0.55), (beat_dur * 3, 'snare', 0.35)]
        else:
            drum_defs = [(0, 'kick', 0.5)]

        # Sparse hihats
        for eighth in range(8):
            if random.random() < 0.6:  # Skip some for rain feel
                swing = 0.025 if eighth % 2 == 1 else 0.0
                vel = 0.15 if eighth % 2 == 0 else 0.08
                drum_defs.append((eighth * beat_dur / 2 + swing, 'hihat', vel))

        for offset, dtype, vel in drum_defs:
            start_s = bar_start + offset + random.gauss(0, 0.004)
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
            else:
                sig = v_hihat(t, vel, False)
            left[start_idx:end_idx] += sig
            right[start_idx:end_idx] += sig
            drum_count += 1

    # ── Rain layer ──
    rain_l, rain_r = generate_rain(total_samples, rain_intensity)
    left += rain_l
    right += rain_r

    # ── Vinyl crackle (more subdued) ──
    crackle = np.zeros(total_samples)
    impulse_mask = np.random.random(total_samples) < 0.002
    crackle[impulse_mask] = np.random.uniform(-0.02, 0.02, impulse_mask.sum())
    left += crackle
    right += crackle * 0.7

    # ── Post-processing ──
    left = v_soft_clip(left, 1.2)
    right = v_soft_clip(right, 1.2)

    # Lo-fi LPF
    alpha = 0.12
    b = [alpha]
    a = [1.0, -(1.0 - alpha)]
    for _ in range(3):
        left_f = lfilter(b, a, left)
        right_f = lfilter(b, a, right)
        left = left * 0.5 + left_f * 0.5
        right = right * 0.5 + right_f * 0.5

    # Normalize
    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    if peak > 0:
        gain = 0.82 / peak
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

    return {
        "output": output_path,
        "size_mb": round(file_size / (1024 * 1024), 1),
        "duration": round(duration_seconds, 1),
        "tempo": tempo,
        "bars": bars,
        "rain_intensity": rain_intensity,
        "notes_rendered": note_count,
        "drum_hits": drum_count,
        "render_time": round(elapsed, 2),
        "realtime_ratio": round(duration_seconds / elapsed, 1),
    }


if __name__ == "__main__":
    output_dir = "/Users/nicolas/work/katala/output"
    os.makedirs(output_dir, exist_ok=True)
    wav_path = os.path.join(output_dir, "lofi_rain.wav")

    print("🌧️ LoFi Rain Generator")
    result = generate_lofi_rain(wav_path, duration_seconds=120.0, tempo=72, rain_intensity=0.7)
    print(f"  ✅ {result['output']}")
    print(f"  📦 {result['size_mb']} MB, {result['duration']}s")
    print(f"  🚀 {result['render_time']}s ({result['realtime_ratio']}x realtime)")
    print(f"  🌧️ Rain intensity: {result['rain_intensity']}")
    print(f"  🎵 Notes: {result['notes_rendered']}, Drums: {result['drum_hits']}")
