"""
Harmony Theory Engine — 芸大和声 + Berklee Jazz Harmony unified framework.

Youta directive: "芸大和声を読解せよ。バークリーのジャズ和声の本を理解せよ。"

Two harmonic traditions unified:
  1. 芸大和声 (Geidai Wasei) — 島岡譲体系: Classical functional harmony
     - 4声体 strict voice leading
     - 禁則 (parallel 5ths/8ves, hidden 5ths/8ves)
     - 限定進行音 (tendency tones must resolve)
     - 転調/借用和音/変化和音
  2. Berklee Jazz Harmony — Mulholland/Hojnacki体系
     - Chord-scale theory
     - ii-V-I progressions
     - Tritone substitution
     - Upper structure triads
     - Modal interchange
     - Reharmonization

KCS connection:
  Composer's harmonic intent (design) → notation/voicing (code) → sound (execution)
  Translation loss at each stage — HTLF 5-axis applies.

Design: Youta Hilono (direction)
Implementation: Shirokuma
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

VERSION = "1.0.0"

# ═══════════════════════════════════════════════════════════════
# Pitch & Interval Constants
# ═══════════════════════════════════════════════════════════════

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
ENHARMONIC = {
    'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#',
    'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B',
    'E#': 'F', 'B#': 'C',
}

INTERVAL_NAMES = {
    0: 'P1', 1: 'm2', 2: 'M2', 3: 'm3', 4: 'M3', 5: 'P4',
    6: 'TT', 7: 'P5', 8: 'm6', 9: 'M6', 10: 'm7', 11: 'M7',
}

# Scale templates (semitone intervals from root)
SCALES = {
    'major':            [0, 2, 4, 5, 7, 9, 11],
    'natural_minor':    [0, 2, 3, 5, 7, 8, 10],
    'harmonic_minor':   [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor':    [0, 2, 3, 5, 7, 9, 11],
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':       [0, 2, 4, 5, 7, 9, 10],
    'lydian':           [0, 2, 4, 6, 7, 9, 11],
    'phrygian':         [0, 1, 3, 5, 7, 8, 10],
    'locrian':          [0, 1, 3, 5, 6, 8, 10],
    'whole_tone':       [0, 2, 4, 6, 8, 10],
    'diminished':       [0, 2, 3, 5, 6, 8, 9, 11],  # half-whole
    'blues':            [0, 3, 5, 6, 7, 10],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'pentatonic_minor': [0, 3, 5, 7, 10],
}


def note_to_midi(note: str, octave: int = 4) -> int:
    """Convert note name + octave to MIDI number."""
    n = ENHARMONIC.get(note, note)
    return NOTE_NAMES.index(n) + (octave + 1) * 12


def midi_to_note(midi: int) -> Tuple[str, int]:
    """Convert MIDI number to (note_name, octave)."""
    return NOTE_NAMES[midi % 12], (midi // 12) - 1


def interval(n1: int, n2: int) -> int:
    """Interval in semitones (mod 12)."""
    return (n2 - n1) % 12


# ═══════════════════════════════════════════════════════════════
# Chord Types
# ═══════════════════════════════════════════════════════════════

class ChordQuality(Enum):
    """Chord quality types."""
    MAJOR = "maj"
    MINOR = "min"
    DIMINISHED = "dim"
    AUGMENTED = "aug"
    DOMINANT = "dom"
    HALF_DIM = "half_dim"       # m7b5
    MAJOR_7 = "maj7"
    MINOR_7 = "min7"
    DOMINANT_7 = "dom7"
    DIMINISHED_7 = "dim7"
    MINOR_MAJOR_7 = "minmaj7"
    AUGMENTED_7 = "aug7"
    SUS4 = "sus4"
    SUS2 = "sus2"
    ADD9 = "add9"
    NINTH = "9"
    MINOR_9 = "min9"
    MAJOR_9 = "maj9"
    THIRTEENTH = "13"


# Chord templates: intervals from root
CHORD_TEMPLATES = {
    ChordQuality.MAJOR:         [0, 4, 7],
    ChordQuality.MINOR:         [0, 3, 7],
    ChordQuality.DIMINISHED:    [0, 3, 6],
    ChordQuality.AUGMENTED:     [0, 4, 8],
    ChordQuality.MAJOR_7:       [0, 4, 7, 11],
    ChordQuality.MINOR_7:       [0, 3, 7, 10],
    ChordQuality.DOMINANT_7:    [0, 4, 7, 10],
    ChordQuality.HALF_DIM:      [0, 3, 6, 10],
    ChordQuality.DIMINISHED_7:  [0, 3, 6, 9],
    ChordQuality.MINOR_MAJOR_7: [0, 3, 7, 11],
    ChordQuality.AUGMENTED_7:   [0, 4, 8, 10],
    ChordQuality.SUS4:          [0, 5, 7],
    ChordQuality.SUS2:          [0, 2, 7],
    ChordQuality.NINTH:         [0, 4, 7, 10, 14],
    ChordQuality.MINOR_9:       [0, 3, 7, 10, 14],
    ChordQuality.MAJOR_9:       [0, 4, 7, 11, 14],
    ChordQuality.THIRTEENTH:    [0, 4, 7, 10, 14, 21],
}


@dataclass
class Chord:
    """A chord with root, quality, and voicing."""
    root: int              # MIDI note number of root
    quality: ChordQuality
    inversion: int = 0     # 0=root, 1=1st, 2=2nd, 3=3rd
    voicing: List[int] = field(default_factory=list)  # actual MIDI notes

    @property
    def name(self) -> str:
        note, _ = midi_to_note(self.root)
        inv_str = ["", "/1st", "/2nd", "/3rd"][min(self.inversion, 3)]
        return f"{note}{self.quality.value}{inv_str}"

    @property
    def pitch_classes(self) -> Set[int]:
        template = CHORD_TEMPLATES.get(self.quality, [0, 4, 7])
        return {(self.root + i) % 12 for i in template}

    def build_voicing(self, bass_octave: int = 2, spread: str = "close") -> List[int]:
        """Build a 4-voice voicing."""
        template = CHORD_TEMPLATES.get(self.quality, [0, 4, 7])
        root_pc = self.root % 12

        if spread == "close":
            base = root_pc + (bass_octave + 1) * 12
            notes = [base + i for i in template]
        elif spread == "open":
            base = root_pc + (bass_octave + 1) * 12
            notes = []
            for i, t in enumerate(template):
                oct_add = 12 if i % 2 == 1 else 0
                notes.append(base + t + oct_add)
        else:
            base = root_pc + (bass_octave + 1) * 12
            notes = [base + i for i in template]

        # Apply inversion
        if self.inversion > 0 and len(notes) > self.inversion:
            for i in range(self.inversion):
                notes[i] += 12

        self.voicing = sorted(notes)
        return self.voicing


# ═══════════════════════════════════════════════════════════════
# 芸大和声 (Geidai Harmony) — Classical voice leading rules
# ═══════════════════════════════════════════════════════════════

class GeidaiHarmonyRules:
    """芸大和声の禁則・連結規則チェッカー.

    島岡譲体系に基づく4声体和声法のルール集:
    - 連続5度/8度/1度の禁止
    - 並達5度/8度の条件付き禁止
    - 導音の上行解決義務
    - 限定進行音の解決
    - 対斜の禁止
    - 声部交差の禁止
    """

    # 完全音程 (禁則対象)
    PERFECT_INTERVALS = {0, 5, 7}  # P1, P4, P5 (mod 12)

    @staticmethod
    def check_parallel_motion(voice1_prev: int, voice1_next: int,
                               voice2_prev: int, voice2_next: int) -> List[str]:
        """Check for forbidden parallel motion between two voices.

        Returns list of violation descriptions.
        """
        violations = []
        int_prev = interval(voice2_prev, voice1_prev)
        int_next = interval(voice2_next, voice1_next)

        # 連続1度 (parallel unisons) — 完全禁止
        if int_prev == 0 and int_next == 0:
            violations.append("連続1度 (parallel unisons) — 禁止")

        # 連続5度 (parallel fifths) — 完全禁止
        if int_prev == 7 and int_next == 7:
            violations.append("連続5度 (parallel fifths) — 禁止")

        # 連続8度 (parallel octaves) — 完全禁止
        if int_prev == 0 and int_next == 0 and abs(voice1_prev - voice2_prev) == 12:
            violations.append("連続8度 (parallel octaves) — 禁止")

        # Detect motion direction
        v1_motion = voice1_next - voice1_prev
        v2_motion = voice2_next - voice2_prev

        # 並達 (hidden/direct): Both voices move in same direction to perfect interval
        if v1_motion != 0 and v2_motion != 0:
            same_direction = (v1_motion > 0) == (v2_motion > 0)
            if same_direction and int_next in {0, 7}:
                # 並達5度/8度 with soprano leap = forbidden
                soprano_leaps = abs(v1_motion) > 2
                if soprano_leaps:
                    interval_name = "5度" if int_next == 7 else "1度/8度"
                    violations.append(f"並達{interval_name} (hidden) with soprano leap — 禁止")

        return violations

    @staticmethod
    def check_voice_crossing(voices_prev: List[int],
                              voices_next: List[int]) -> List[str]:
        """Check for voice crossing (声部交差).

        Voices should maintain their register order: bass < tenor < alto < soprano.
        """
        violations = []
        labels = ["Bass", "Tenor", "Alto", "Soprano"]

        for i in range(len(voices_next) - 1):
            if voices_next[i] >= voices_next[i + 1]:
                violations.append(
                    f"声部交差: {labels[i]} ({voices_next[i]}) ≥ "
                    f"{labels[i+1]} ({voices_next[i+1]})")

        return violations

    @staticmethod
    def check_leading_tone_resolution(key_root: int, mode: str,
                                       prev_chord: List[int],
                                       next_chord: List[int]) -> List[str]:
        """Check leading tone resolution (導音進行).

        Leading tone (7th degree in major) must resolve upward to tonic.
        """
        violations = []

        if mode == "major":
            leading_tone_pc = (key_root + 11) % 12  # 7th degree
            tonic_pc = key_root % 12

            for i, note in enumerate(prev_chord):
                if note % 12 == leading_tone_pc:
                    # This voice has the leading tone — check resolution
                    if i < len(next_chord):
                        next_note = next_chord[i]
                        if next_note % 12 != tonic_pc:
                            violations.append(
                                f"導音未解決: voice {i} has leading tone "
                                f"({NOTE_NAMES[leading_tone_pc]}) but resolves to "
                                f"{NOTE_NAMES[next_note % 12]} instead of "
                                f"{NOTE_NAMES[tonic_pc]}")

        return violations

    @staticmethod
    def check_tendency_tone_resolution(chord_quality: ChordQuality,
                                        chord_root: int,
                                        prev_voicing: List[int],
                                        next_voicing: List[int]) -> List[str]:
        """Check tendency tone (限定進行音) resolution.

        In dominant 7th chords:
        - 3rd (leading tone) must resolve up by half step
        - 7th must resolve down by half step or step
        """
        violations = []

        if chord_quality in (ChordQuality.DOMINANT_7, ChordQuality.NINTH):
            third_pc = (chord_root + 4) % 12  # Major 3rd
            seventh_pc = (chord_root + 10) % 12  # Minor 7th

            for i, note in enumerate(prev_voicing):
                pc = note % 12
                if i < len(next_voicing):
                    next_pc = next_voicing[i] % 12
                    motion = next_voicing[i] - note

                    # 3rd should resolve up
                    if pc == third_pc and motion < 0:
                        violations.append(
                            f"限定進行音違反: Dom7の3度({NOTE_NAMES[pc]})が下行")

                    # 7th should resolve down
                    if pc == seventh_pc and motion > 0:
                        violations.append(
                            f"限定進行音違反: Dom7の7度({NOTE_NAMES[pc]})が上行")

        return violations

    @staticmethod
    def check_cross_relation(prev_voicing: List[int],
                              next_voicing: List[int]) -> List[str]:
        """Check for cross-relation (対斜).

        Chromatic alteration should occur in the SAME voice, not across voices.
        """
        violations = []

        for i, prev_note in enumerate(prev_voicing):
            for j, next_note in enumerate(next_voicing):
                if i != j:  # Different voices
                    # Check if they form a chromatic semitone
                    if abs(prev_note % 12 - next_note % 12) == 1:
                        # And neither is a stepwise motion in its own voice
                        if i < len(next_voicing) and j < len(prev_voicing):
                            own_motion_i = abs(next_voicing[i] - prev_note) if i < len(next_voicing) else 0
                            own_motion_j = abs(next_note - prev_voicing[j]) if j < len(prev_voicing) else 0
                            # Only flag if this creates an obvious cross-relation
                            if own_motion_i > 2 and own_motion_j > 2:
                                violations.append(
                                    f"対斜: voice {i}({NOTE_NAMES[prev_note%12]}) → "
                                    f"voice {j}({NOTE_NAMES[next_note%12]})")

        return violations

    def full_check(self, key_root: int, mode: str,
                   prev_voicing: List[int], next_voicing: List[int],
                   chord_quality: Optional[ChordQuality] = None,
                   chord_root: Optional[int] = None) -> Dict[str, Any]:
        """Run all Geidai harmony rule checks.

        Returns dict with violations and overall pass/fail.
        """
        all_violations = []

        # Voice crossing
        all_violations.extend(self.check_voice_crossing(prev_voicing, next_voicing))

        # Parallel motion (check all voice pairs)
        n = min(len(prev_voicing), len(next_voicing))
        for i in range(n):
            for j in range(i + 1, n):
                all_violations.extend(
                    self.check_parallel_motion(
                        prev_voicing[i], next_voicing[i],
                        prev_voicing[j], next_voicing[j]))

        # Leading tone
        all_violations.extend(
            self.check_leading_tone_resolution(key_root, mode,
                                               prev_voicing, next_voicing))

        # Tendency tones
        if chord_quality and chord_root is not None:
            all_violations.extend(
                self.check_tendency_tone_resolution(
                    chord_quality, chord_root,
                    prev_voicing, next_voicing))

        # Cross-relation
        all_violations.extend(
            self.check_cross_relation(prev_voicing, next_voicing))

        return {
            "violations": all_violations,
            "violation_count": len(all_violations),
            "passed": len(all_violations) == 0,
            "severity": "critical" if any("禁止" in v for v in all_violations) else
                       "warning" if all_violations else "clean",
        }


# ═══════════════════════════════════════════════════════════════
# Berklee Jazz Harmony — Chord-scale theory & reharmonization
# ═══════════════════════════════════════════════════════════════

class HarmonicFunction(Enum):
    """Harmonic function categories (Berklee system)."""
    TONIC = "T"
    SUBDOMINANT = "SD"
    DOMINANT = "D"
    TONIC_MINOR = "Tm"
    SUBDOMINANT_MINOR = "SDm"


# Diatonic function assignments (major key)
DIATONIC_FUNCTIONS = {
    1: HarmonicFunction.TONIC,        # Imaj7
    2: HarmonicFunction.SUBDOMINANT,  # ii7
    3: HarmonicFunction.TONIC,        # iii7
    4: HarmonicFunction.SUBDOMINANT,  # IVmaj7
    5: HarmonicFunction.DOMINANT,     # V7
    6: HarmonicFunction.TONIC,        # vi7
    7: HarmonicFunction.DOMINANT,     # vii°7
}

# Chord-scale assignments (Berklee system)
CHORD_SCALE_MAP = {
    (ChordQuality.MAJOR_7, 1): 'major',          # Ionian
    (ChordQuality.MINOR_7, 2): 'dorian',          # Dorian
    (ChordQuality.MINOR_7, 3): 'phrygian',        # Phrygian
    (ChordQuality.MAJOR_7, 4): 'lydian',          # Lydian
    (ChordQuality.DOMINANT_7, 5): 'mixolydian',   # Mixolydian
    (ChordQuality.MINOR_7, 6): 'major',           # Aeolian (relative of major)
    (ChordQuality.HALF_DIM, 7): 'locrian',        # Locrian
}


class BerkleeJazzHarmony:
    """Berklee jazz harmony analysis and generation.

    Implements:
    - Chord-scale theory
    - ii-V-I progressions
    - Tritone substitution
    - Secondary dominants
    - Modal interchange
    - Upper structure triads
    - Reharmonization techniques
    """

    @staticmethod
    def get_chord_scale(root: int, quality: ChordQuality,
                        degree: int = 1) -> List[int]:
        """Get the appropriate scale for a chord (chord-scale theory)."""
        key = (quality, degree)
        scale_name = CHORD_SCALE_MAP.get(key, 'major')
        return [(root + i) % 12 for i in SCALES[scale_name]]

    @staticmethod
    def get_available_tensions(root: int, quality: ChordQuality) -> Dict[str, int]:
        """Get available tensions for a chord type.

        Returns dict of tension name → MIDI interval from root.
        """
        tensions = {}

        if quality == ChordQuality.MAJOR_7:
            tensions = {'9': 14, '#11': 18, '13': 21}
        elif quality == ChordQuality.MINOR_7:
            tensions = {'9': 14, '11': 17, '13': 21}
        elif quality == ChordQuality.DOMINANT_7:
            tensions = {
                '9': 14, 'b9': 13, '#9': 15,
                '#11': 18,
                '13': 21, 'b13': 20,
            }
        elif quality == ChordQuality.HALF_DIM:
            tensions = {'9': 14, '11': 17, 'b13': 20}

        return tensions

    @staticmethod
    def tritone_substitution(dominant_root: int) -> int:
        """Get tritone substitute root.

        V7 → bII7 (same tritone interval between 3rd and 7th).
        Example: G7 → Db7 (both contain B and F).
        """
        return (dominant_root + 6) % 12

    @staticmethod
    def secondary_dominant(target_degree: int, key_root: int,
                           scale: str = 'major') -> int:
        """Get secondary dominant root (V7/X).

        Returns the root of V7 that resolves to the target degree.
        """
        scale_intervals = SCALES[scale]
        target_interval = scale_intervals[(target_degree - 1) % len(scale_intervals)]
        target_root = (key_root + target_interval) % 12
        return (target_root + 7) % 12  # V of target

    @staticmethod
    def generate_ii_V_I(key_root: int, mode: str = "major") -> List[Chord]:
        """Generate a ii-V-I progression.

        Major: Dm7 → G7 → Cmaj7
        Minor: Dm7b5 → G7alt → Cm(maj7)
        """
        if mode == "major":
            ii = Chord(root=(key_root + 2) % 12 + 48,
                      quality=ChordQuality.MINOR_7)
            V = Chord(root=(key_root + 7) % 12 + 48,
                     quality=ChordQuality.DOMINANT_7)
            I = Chord(root=key_root % 12 + 48,
                     quality=ChordQuality.MAJOR_7)
        else:  # minor
            ii = Chord(root=(key_root + 2) % 12 + 48,
                      quality=ChordQuality.HALF_DIM)
            V = Chord(root=(key_root + 7) % 12 + 48,
                     quality=ChordQuality.DOMINANT_7)
            I = Chord(root=key_root % 12 + 48,
                     quality=ChordQuality.MINOR_MAJOR_7)

        return [ii, V, I]

    @staticmethod
    def modal_interchange_chords(key_root: int) -> Dict[str, Chord]:
        """Get modal interchange chords (borrowed from parallel minor).

        Common borrowings: bIII, bVI, bVII, iv, ii°
        """
        return {
            'bIII': Chord(root=(key_root + 3) % 12 + 48, quality=ChordQuality.MAJOR),
            'iv': Chord(root=(key_root + 5) % 12 + 48, quality=ChordQuality.MINOR),
            'bVI': Chord(root=(key_root + 8) % 12 + 48, quality=ChordQuality.MAJOR),
            'bVII': Chord(root=(key_root + 10) % 12 + 48, quality=ChordQuality.MAJOR),
            'ii°': Chord(root=(key_root + 2) % 12 + 48, quality=ChordQuality.DIMINISHED),
        }

    @staticmethod
    def upper_structure_triad(dom_root: int, tension: str) -> List[int]:
        """Build upper structure triad over dominant chord.

        Upper structures: major triads built on tensions.
        Example: G7(#11) → D major triad (D F# A) over G7 (G B D F)
        """
        structures = {
            '#11': [6, 10, 1],   # Tritone, m7, b9 relative positions
            'b13': [8, 0, 4],    # b6, root, 3rd
            '9':   [2, 6, 9],    # 9th, #11, 13th
            '#9':  [3, 7, 10],   # #9, 5th, b7
        }
        intervals = structures.get(tension, [2, 6, 9])
        return [(dom_root + i) % 12 + 72 for i in intervals]  # Upper octave

    @staticmethod
    def reharmonize_with_tritone_sub(progression: List[Chord]) -> List[Chord]:
        """Reharmonize dominant chords with tritone substitutions."""
        result = []
        for chord in progression:
            if chord.quality == ChordQuality.DOMINANT_7:
                # 50% chance to substitute (for variety)
                if random.random() < 0.5:
                    new_root = (chord.root + 6) % 12 + (chord.root // 12) * 12
                    result.append(Chord(root=new_root,
                                       quality=ChordQuality.DOMINANT_7))
                    continue
            result.append(chord)
        return result

    def analyze_progression(self, chords: List[Chord],
                            key_root: int) -> List[Dict[str, Any]]:
        """Analyze a chord progression functionally.

        Returns analysis for each chord: degree, function, tensions, etc.
        """
        analysis = []
        for chord in chords:
            root_interval = (chord.root - key_root) % 12

            # Determine degree
            major_scale = SCALES['major']
            degree = None
            for i, s in enumerate(major_scale):
                if s == root_interval:
                    degree = i + 1
                    break

            func = DIATONIC_FUNCTIONS.get(degree, None) if degree else None
            tensions = self.get_available_tensions(chord.root, chord.quality)

            # Check for secondary dominant
            is_secondary_dom = False
            sec_target = None
            if chord.quality == ChordQuality.DOMINANT_7 and degree != 5:
                # This is a V7 of something
                resolves_to = (chord.root + 5) % 12  # P4 up = target
                for i, s in enumerate(major_scale):
                    if (key_root + s) % 12 == resolves_to:
                        is_secondary_dom = True
                        sec_target = i + 1
                        break

            analysis.append({
                "chord": chord.name,
                "degree": degree,
                "function": func.value if func else "?",
                "available_tensions": list(tensions.keys()),
                "is_secondary_dominant": is_secondary_dom,
                "secondary_target": sec_target,
                "chord_scale": self.get_chord_scale(chord.root, chord.quality,
                                                     degree or 1),
            })

        return analysis


# ═══════════════════════════════════════════════════════════════
# Unified Harmony Engine
# ═══════════════════════════════════════════════════════════════

class HarmonyEngine:
    """Unified harmony engine combining 芸大和声 + Berklee.

    Uses classical voice leading rules (Geidai) for correctness checking,
    and jazz harmony theory (Berklee) for creative generation/analysis.
    """

    def __init__(self):
        self.geidai = GeidaiHarmonyRules()
        self.berklee = BerkleeJazzHarmony()

    def generate_jazz_progression(self, key: str = "C", mode: str = "major",
                                   bars: int = 8,
                                   style: str = "lofi") -> List[Chord]:
        """Generate a jazz chord progression with style.

        Styles: lofi, bossa, standard, modal, blues
        """
        key_root = NOTE_NAMES.index(ENHARMONIC.get(key, key))

        if style == "lofi":
            return self._lofi_progression(key_root, bars)
        elif style == "bossa":
            return self._bossa_progression(key_root, bars)
        elif style == "blues":
            return self._blues_progression(key_root, bars)
        elif style == "modal":
            return self._modal_progression(key_root, bars)
        else:
            return self._standard_progression(key_root, bars)

    def _lofi_progression(self, key_root: int, bars: int) -> List[Chord]:
        """LoFi chill progressions — jazzy 7ths with smooth motion."""
        templates = [
            # Classic lofi patterns (degrees, qualities)
            [(2, ChordQuality.MINOR_7), (5, ChordQuality.DOMINANT_7),
             (1, ChordQuality.MAJOR_7), (6, ChordQuality.MINOR_7)],
            [(3, ChordQuality.MINOR_7), (6, ChordQuality.MINOR_7),
             (2, ChordQuality.MINOR_9), (5, ChordQuality.THIRTEENTH)],
            [(1, ChordQuality.MAJOR_7), (6, ChordQuality.MINOR_7),
             (2, ChordQuality.MINOR_7), (5, ChordQuality.DOMINANT_7)],
            [(6, ChordQuality.MINOR_7), (4, ChordQuality.MAJOR_7),
             (1, ChordQuality.MAJOR_7), (5, ChordQuality.DOMINANT_7)],
        ]

        template = random.choice(templates)
        major_scale = SCALES['major']
        chords = []

        for bar in range(bars):
            degree, quality = template[bar % len(template)]
            root_interval = major_scale[(degree - 1) % 7]
            root = (key_root + root_interval) % 12 + 48
            chords.append(Chord(root=root, quality=quality))

        return chords

    def _bossa_progression(self, key_root: int, bars: int) -> List[Chord]:
        """Bossa nova patterns — Jobim-style."""
        templates = [
            [(1, ChordQuality.MAJOR_7), (2, ChordQuality.MINOR_7),
             (5, ChordQuality.DOMINANT_7), (1, ChordQuality.MAJOR_7)],
            [(1, ChordQuality.MAJOR_7), (4, ChordQuality.MAJOR_7),
             (3, ChordQuality.MINOR_7), (6, ChordQuality.MINOR_7)],
        ]
        template = random.choice(templates)
        major_scale = SCALES['major']
        chords = []
        for bar in range(bars):
            degree, quality = template[bar % len(template)]
            root = (key_root + major_scale[(degree-1)%7]) % 12 + 48
            chords.append(Chord(root=root, quality=quality))
        return chords

    def _blues_progression(self, key_root: int, bars: int) -> List[Chord]:
        """12-bar blues (extended to requested bars)."""
        pattern_12 = [1,1,1,1, 4,4,1,1, 5,4,1,5]
        chords = []
        for bar in range(bars):
            degree = pattern_12[bar % 12]
            root = (key_root + SCALES['major'][(degree-1)%7]) % 12 + 48
            chords.append(Chord(root=root, quality=ChordQuality.DOMINANT_7))
        return chords

    def _modal_progression(self, key_root: int, bars: int) -> List[Chord]:
        """Modal jazz — sustained harmonies, Dorian/Mixolydian flavor."""
        patterns = [
            [(2, ChordQuality.MINOR_7)] * 4 + [(2, ChordQuality.MINOR_7)] * 4,  # Dorian vamp
            [(1, ChordQuality.MAJOR_7)] * 2 + [(2, ChordQuality.MINOR_7)] * 2 +
            [(4, ChordQuality.MAJOR_7)] * 2 + [(1, ChordQuality.MAJOR_7)] * 2,  # So What inspired
        ]
        template = random.choice(patterns)
        major_scale = SCALES['major']
        chords = []
        for bar in range(bars):
            degree, quality = template[bar % len(template)]
            root = (key_root + major_scale[(degree-1)%7]) % 12 + 48
            chords.append(Chord(root=root, quality=quality))
        return chords

    def _standard_progression(self, key_root: int, bars: int) -> List[Chord]:
        """Standard jazz — ii-V-I based."""
        chords = []
        for bar in range(0, bars, 4):
            ii_v_i = self.berklee.generate_ii_V_I(key_root, "major")
            chords.extend(ii_v_i)
            # Add a turnaround
            turnaround_root = (key_root + 9) % 12 + 48  # vi
            chords.append(Chord(root=turnaround_root, quality=ChordQuality.MINOR_7))
        return chords[:bars]

    def verify_voice_leading(self, progression: List[List[int]],
                              key_root: int, mode: str = "major") -> Dict[str, Any]:
        """Verify an entire progression's voice leading using Geidai rules.

        Args:
            progression: List of voicings (each voicing = list of 4 MIDI notes)
            key_root: MIDI note of key root
            mode: "major" or "minor"
        """
        all_violations = []
        clean_transitions = 0
        total_transitions = len(progression) - 1

        for i in range(total_transitions):
            result = self.geidai.full_check(
                key_root, mode,
                progression[i], progression[i + 1])
            if result['passed']:
                clean_transitions += 1
            else:
                for v in result['violations']:
                    all_violations.append(f"Bar {i+1}→{i+2}: {v}")

        voice_leading_score = clean_transitions / max(total_transitions, 1)

        return {
            "total_transitions": total_transitions,
            "clean_transitions": clean_transitions,
            "violations": all_violations,
            "voice_leading_score": round(voice_leading_score, 4),
            "grade": "A" if voice_leading_score >= 0.9 else
                    "B" if voice_leading_score >= 0.7 else
                    "C" if voice_leading_score >= 0.5 else "D",
        }

    def analyze_and_suggest(self, chords: List[Chord],
                             key_root: int) -> Dict[str, Any]:
        """Analyze a progression and suggest reharmonization options."""
        analysis = self.berklee.analyze_progression(chords, key_root)

        suggestions = []
        for i, (chord, info) in enumerate(zip(chords, analysis)):
            # Suggest tritone subs for dominants
            if chord.quality == ChordQuality.DOMINANT_7:
                tri_root = self.berklee.tritone_substitution(chord.root)
                tri_name, _ = midi_to_note(tri_root)
                suggestions.append(
                    f"Bar {i+1}: {chord.name} → tritone sub: {tri_name}7")

            # Suggest secondary dominants
            if info['function'] in ('T', 'SD') and i < len(chords) - 1:
                sec_root = (chords[i+1].root + 7) % 12
                sec_name, _ = midi_to_note(sec_root)
                suggestions.append(
                    f"Bar {i+1}: Can add {sec_name}7 as secondary V7 → {chords[i+1].name}")

        return {
            "analysis": analysis,
            "suggestions": suggestions,
            "modal_interchange_options": {
                name: chord.name
                for name, chord in self.berklee.modal_interchange_chords(key_root).items()
            },
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "engine": "HarmonyEngine",
            "traditions": ["芸大和声 (Geidai)", "Berklee Jazz Harmony"],
            "geidai_rules": [
                "連続5度/8度/1度 禁止",
                "並達5度/8度 (ソプラノ跳躍時) 禁止",
                "導音上行解決義務",
                "限定進行音解決 (Dom7 3rd↑, 7th↓)",
                "対斜禁止",
                "声部交差禁止",
            ],
            "berklee_techniques": [
                "Chord-scale theory",
                "ii-V-I progressions (major/minor)",
                "Tritone substitution",
                "Secondary dominants (V7/X)",
                "Modal interchange (parallel minor borrowing)",
                "Upper structure triads",
                "Reharmonization",
                "Available tensions analysis",
            ],
            "chord_qualities": len(ChordQuality),
            "scales": len(SCALES),
            "styles": ["lofi", "bossa", "standard", "modal", "blues"],
        }
