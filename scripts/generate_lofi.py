#!/usr/bin/env python3
"""
LoFi Music Generator — Chill beats procedurally generated.

Youta: "LoFi Musicを生成して。Chillな感じ。"

Generates a MIDI file with classic LoFi characteristics:
- Jazzy chord progressions (7ths, 9ths, minor voicings)
- Slow tempo (70-85 BPM)
- Vinyl crackle/rain aesthetic (via note choices + swing)
- Rhodes/EP piano, muted bass, gentle drums
- Swing feel (humanized timing)
- Lo-fi note imperfections (slight detuning, velocity variation)

Then converts to WAV via FluidSynth or outputs MIDI directly.
"""

import os
import sys
import random
import math
from midiutil import MIDIFile

# ═══════════════════════════════════════════════════════════════════
# LoFi Constants
# ═══════════════════════════════════════════════════════════════════

TEMPO_BPM = 75           # Classic lofi tempo
SWING_AMOUNT = 0.08      # Swing feel (beat offset in beats)
BARS = 32                # Total bars
BEATS_PER_BAR = 4
TOTAL_BEATS = BARS * BEATS_PER_BAR

# MIDI channels
CH_KEYS = 0              # Rhodes/EP
CH_BASS = 1              # Muted bass
CH_DRUMS = 9             # Drums (GM channel 10, 0-indexed = 9)
CH_PAD = 2               # Ambient pad

# GM Programs
PROG_RHODES = 4           # Electric Piano 1 (Rhodes)
PROG_BASS = 33            # Finger Bass
PROG_PAD = 89             # Warm Pad

# Drum GM notes
KICK = 36
SNARE = 38
CLOSED_HH = 42
OPEN_HH = 46
RIDE = 51
CROSS_STICK = 37
SHAKER = 70

# ═══════════════════════════════════════════════════════════════════
# Chord Progressions — LoFi jazzy voicings
# ═══════════════════════════════════════════════════════════════════

# Classic lofi progressions (MIDI note numbers, rooted around C4=60)
# Using 7th/9th chords for that jazzy feel
PROGRESSIONS = [
    # ii-V-I-vi in Bb major (Cm7 - F7 - Bbmaj7 - Gm7)
    [
        [60, 63, 67, 70],      # Cm7
        [65, 69, 72, 75],      # F7 (dominant)
        [58, 62, 65, 69],      # Bbmaj7
        [55, 58, 62, 65],      # Gm7
    ],
    # I-vi-ii-V in C (Cmaj7 - Am7 - Dm7 - G7)
    [
        [60, 64, 67, 71],      # Cmaj7
        [57, 60, 64, 67],      # Am7
        [62, 65, 69, 72],      # Dm7
        [55, 59, 62, 65],      # G7
    ],
    # iii-vi-ii-V in C (Em7 - Am7 - Dm9 - G13)
    [
        [64, 67, 71, 74],      # Em7
        [57, 60, 64, 67],      # Am7
        [62, 65, 69, 72, 76],  # Dm9
        [55, 59, 62, 65, 69],  # G13
    ],
    # Chill minor: i-bVI-bIII-bVII (Am - F - C - G)
    [
        [57, 60, 64, 67],      # Am7
        [53, 57, 60, 64],      # Fmaj7
        [60, 64, 67, 71],      # Cmaj7
        [55, 59, 62, 67],      # G7
    ],
]


def humanize_time(beat: float) -> float:
    """Add subtle timing imperfection."""
    return beat + random.gauss(0, 0.012)


def humanize_velocity(base_vel: int, variance: int = 12) -> int:
    """Add velocity variation for organic feel."""
    return max(30, min(110, base_vel + random.randint(-variance, variance)))


def apply_swing(beat: float) -> float:
    """Apply swing to off-beats."""
    beat_in_bar = beat % 1.0
    if 0.4 < beat_in_bar < 0.6:  # Off-beat (approximate)
        return beat + SWING_AMOUNT
    return beat


# ═══════════════════════════════════════════════════════════════════
# Generators
# ═══════════════════════════════════════════════════════════════════

def generate_keys(midi: MIDIFile, track: int, progression: list):
    """Generate Rhodes/EP chord track."""
    midi.addProgramChange(track, CH_KEYS, 0, PROG_RHODES)

    for bar in range(BARS):
        chord_idx = bar % len(progression)
        chord = progression[chord_idx]
        beat_start = bar * BEATS_PER_BAR

        # Main chord hit on beat 1
        for note in chord:
            t = humanize_time(apply_swing(beat_start))
            vel = humanize_velocity(65)
            dur = 3.5 + random.uniform(-0.2, 0.2)
            midi.addNote(track, CH_KEYS, note, t, dur, vel)

        # Ghost chord on beat 3 (softer, shorter) — 60% chance
        if random.random() < 0.6:
            for note in chord:
                t = humanize_time(apply_swing(beat_start + 2))
                vel = humanize_velocity(45, variance=8)
                dur = 1.5 + random.uniform(-0.3, 0.3)
                midi.addNote(track, CH_KEYS, note, t, dur, vel)

        # Occasional single note ornament on beat 4 — 30% chance
        if random.random() < 0.3:
            ornament = random.choice(chord) + random.choice([0, 12, -12])
            t = humanize_time(apply_swing(beat_start + 3.5))
            midi.addNote(track, CH_KEYS, ornament, t, 0.5,
                        humanize_velocity(50, variance=10))


def generate_bass(midi: MIDIFile, track: int, progression: list):
    """Generate muted bass line."""
    midi.addProgramChange(track, CH_BASS, 0, PROG_BASS)

    for bar in range(BARS):
        chord = progression[bar % len(progression)]
        root = chord[0] - 12  # One octave down
        fifth = root + 7
        beat_start = bar * BEATS_PER_BAR

        # Root on beat 1
        t = humanize_time(beat_start)
        midi.addNote(track, CH_BASS, root, t, 1.8,
                    humanize_velocity(75))

        # Walking pattern
        patterns = [
            [(2, root, 0.8), (3, fifth, 0.8)],                  # Root-fifth
            [(1.5, root + 3, 0.5), (2, root + 5, 1.0), (3.5, root, 0.5)],  # Walk up
            [(2, fifth, 1.5)],                                    # Simple fifth
            [(1, root + 7, 0.5), (2, root + 5, 0.5), (3, root + 3, 0.5), (3.5, root, 0.5)],  # Walk down
        ]

        pattern = random.choice(patterns)
        for offset, note, dur in pattern:
            t = humanize_time(apply_swing(beat_start + offset))
            midi.addNote(track, CH_BASS, note, t, dur,
                        humanize_velocity(65))


def generate_drums(midi: MIDIFile, track: int):
    """Generate chill drum pattern — LoFi boom-bap."""
    for bar in range(BARS):
        beat_start = bar * BEATS_PER_BAR

        # Kick pattern: 1 and 2.5 (classic boom-bap)
        midi.addNote(track, CH_DRUMS, KICK,
                    humanize_time(beat_start), 0.5,
                    humanize_velocity(80))

        if random.random() < 0.85:
            midi.addNote(track, CH_DRUMS, KICK,
                        humanize_time(apply_swing(beat_start + 2.5)), 0.5,
                        humanize_velocity(70))

        # Snare/cross-stick on 2 and 4
        snare_type = CROSS_STICK if random.random() < 0.4 else SNARE
        midi.addNote(track, CH_DRUMS, snare_type,
                    humanize_time(beat_start + 1), 0.5,
                    humanize_velocity(68))
        midi.addNote(track, CH_DRUMS, snare_type,
                    humanize_time(beat_start + 3), 0.5,
                    humanize_velocity(72))

        # Hi-hat pattern: 8th notes with swing and ghost notes
        for eighth in range(8):
            t = beat_start + eighth * 0.5
            t = humanize_time(apply_swing(t))

            if eighth % 2 == 0:
                # On-beat: normal
                vel = humanize_velocity(55, variance=8)
            else:
                # Off-beat: ghost (softer)
                vel = humanize_velocity(35, variance=6)

            # Occasional open hi-hat
            if eighth in [3, 7] and random.random() < 0.2:
                midi.addNote(track, CH_DRUMS, OPEN_HH, t, 0.3, vel)
            else:
                midi.addNote(track, CH_DRUMS, CLOSED_HH, t, 0.2, vel)

        # Occasional ride instead of hi-hat (every 4-8 bars)
        if bar % random.randint(4, 8) == 0:
            for q in range(4):
                t = humanize_time(beat_start + q)
                midi.addNote(track, CH_DRUMS, RIDE, t, 0.8,
                            humanize_velocity(45))


def generate_pad(midi: MIDIFile, track: int, progression: list):
    """Generate ambient pad — very subtle background warmth."""
    midi.addProgramChange(track, CH_PAD, 0, PROG_PAD)

    for bar in range(0, BARS, 4):  # Change every 4 bars
        chord = progression[bar % len(progression)]
        beat_start = bar * BEATS_PER_BAR

        # Pad notes: very long, very soft
        for note in chord[:3]:  # Only first 3 notes
            pad_note = note + 12  # Up one octave
            t = humanize_time(beat_start)
            dur = BEATS_PER_BAR * 4 - 0.5  # Almost 4 bars
            midi.addNote(track, CH_PAD, pad_note, t, dur,
                        humanize_velocity(35, variance=5))


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def generate_lofi(output_path: str, progression_idx: int = -1,
                  bars: int = 32, tempo: int = 75) -> dict:
    """Generate a LoFi track.

    Args:
        output_path: Output MIDI file path
        progression_idx: Which progression to use (-1 = random)
        bars: Number of bars
        tempo: BPM

    Returns:
        dict with generation details
    """
    global BARS, TEMPO_BPM
    BARS = bars
    TEMPO_BPM = tempo

    if progression_idx < 0:
        progression_idx = random.randint(0, len(PROGRESSIONS) - 1)
    progression = PROGRESSIONS[progression_idx % len(PROGRESSIONS)]

    midi = MIDIFile(4)  # 4 tracks
    midi.addTempo(0, 0, TEMPO_BPM)

    # Track names
    track_names = ["Rhodes Keys", "Muted Bass", "LoFi Drums", "Warm Pad"]
    for i, name in enumerate(track_names):
        midi.addTrackName(i, 0, name)

    # Generate each part
    generate_keys(midi, 0, progression)
    generate_bass(midi, 1, progression)
    generate_drums(midi, 2)
    generate_pad(midi, 3, progression)

    # Write MIDI
    with open(output_path, "wb") as f:
        midi.writeFile(f)

    duration_seconds = (BARS * BEATS_PER_BAR / TEMPO_BPM) * 60
    chord_names_map = {
        0: ["Cm7", "F7", "Bbmaj7", "Gm7"],
        1: ["Cmaj7", "Am7", "Dm7", "G7"],
        2: ["Em7", "Am7", "Dm9", "G13"],
        3: ["Am7", "Fmaj7", "Cmaj7", "G7"],
    }
    chord_names = chord_names_map.get(progression_idx, ["?"])

    return {
        "output": output_path,
        "tempo": TEMPO_BPM,
        "bars": BARS,
        "duration_seconds": round(duration_seconds, 1),
        "progression": " → ".join(chord_names),
        "progression_index": progression_idx,
        "tracks": track_names,
        "style": "LoFi Chill",
        "features": [
            "Jazzy 7th/9th chord voicings",
            "Boom-bap drums with swing",
            "Humanized timing + velocity",
            "Rhodes EP + muted bass",
            "Ghost hi-hats",
            "Ambient warm pad",
        ],
    }


def midi_to_wav(midi_path: str, wav_path: str) -> bool:
    """Convert MIDI to WAV using FluidSynth (if available)."""
    import subprocess

    # Try FluidSynth
    soundfonts = [
        "/usr/share/sounds/sf2/FluidR3_GM.sf2",
        "/usr/share/soundfonts/FluidR3_GM.sf2",
        "/opt/homebrew/share/fluidsynth/sf2/default.sf2",
        os.path.expanduser("~/.fluidsynth/default.sf2"),
    ]

    sf2 = None
    for sf in soundfonts:
        if os.path.exists(sf):
            sf2 = sf
            break

    if sf2:
        try:
            subprocess.run([
                "fluidsynth", "-ni", sf2, midi_path,
                "-F", wav_path, "-r", "44100"
            ], check=True, capture_output=True, timeout=30)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Try timidity
    try:
        subprocess.run([
            "timidity", midi_path, "-Ow", "-o", wav_path
        ], check=True, capture_output=True, timeout=30)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return False


if __name__ == "__main__":
    output_dir = "/Users/nicolas/work/katala/output"
    os.makedirs(output_dir, exist_ok=True)

    midi_path = os.path.join(output_dir, "lofi_chill.mid")
    wav_path = os.path.join(output_dir, "lofi_chill.wav")

    print("🎵 Generating LoFi Chill Music...")
    print()

    result = generate_lofi(midi_path, progression_idx=-1, bars=32, tempo=75)

    print(f"  Style:       {result['style']}")
    print(f"  Tempo:       {result['tempo']} BPM")
    print(f"  Bars:        {result['bars']}")
    print(f"  Duration:    {result['duration_seconds']}s ({result['duration_seconds']/60:.1f}min)")
    print(f"  Progression: {result['progression']}")
    print(f"  Tracks:      {', '.join(result['tracks'])}")
    print(f"  MIDI:        {result['output']}")
    print()
    print("  Features:")
    for f in result['features']:
        print(f"    ✦ {f}")
    print()

    # Try WAV conversion
    if midi_to_wav(midi_path, wav_path):
        print(f"  WAV:  {wav_path} ✅")
    else:
        print("  WAV:  FluidSynth/TiMidity not found — MIDI only")
        print("        Install: brew install fluid-synth")

    print()
    print("Done! 🐻‍❄️")
