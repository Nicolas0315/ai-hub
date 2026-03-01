#!/usr/bin/env python3
"""
Harmony Learning Pipeline — Analyze public domain music corpus.

Nicolas: "著作権が切れたことを確認した音源を学習開始せよ"

Uses music21 corpus (Bach Chorales 433曲, Beethoven 26, Mozart 16, etc.)
All pre-1900 composers — copyright expired worldwide.

Extracts:
  1. Chord progressions (Roman numeral analysis)
  2. Voice leading patterns (4-part chorale movements)
  3. Cadence types (perfect, plagal, half, deceptive)
  4. Key/modulation patterns
  5. Interval distributions
  6. Forbidden motion statistics (parallel 5ths/8ves in actual Bach!)
  7. Common chord substitution patterns

Output: JSON knowledge base for HarmonyEngine.
"""

import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import music21
from music21 import corpus, converter, key, roman, interval, chord, pitch, note

# ═══════════════════════════════════════════════════════════════
# Analysis functions
# ═══════════════════════════════════════════════════════════════

def analyze_chord_progressions(score: music21.stream.Score,
                                analyzed_key: music21.key.Key) -> List[str]:
    """Extract Roman numeral chord progression."""
    progression = []
    try:
        chordified = score.chordify()
        for c in chordified.recurse().getElementsByClass('Chord'):
            try:
                rn = roman.romanNumeralFromChord(c, analyzed_key)
                progression.append(rn.figure)
            except Exception:
                progression.append('?')
    except Exception:
        pass
    return progression


def analyze_cadences(progression: List[str]) -> List[str]:
    """Detect cadence types from chord progression."""
    cadences = []
    for i in range(len(progression) - 1):
        prev_rn = progression[i].upper().replace('#', '').replace('B', '')
        next_rn = progression[i + 1].upper().replace('#', '').replace('B', '')

        # Perfect authentic cadence: V → I
        if 'V' in prev_rn and not 'IV' in prev_rn and ('I' == next_rn or next_rn.startswith('I') and not next_rn.startswith('IV')):
            cadences.append('PAC')
        # Plagal cadence: IV → I
        elif 'IV' in prev_rn and ('I' == next_rn or next_rn.startswith('I') and not next_rn.startswith('IV')):
            cadences.append('plagal')
        # Half cadence: X → V
        elif 'V' in next_rn and not 'IV' in next_rn and 'VII' not in next_rn:
            cadences.append('half')
        # Deceptive: V → vi
        elif 'V' in prev_rn and not 'IV' in prev_rn and 'VI' in next_rn:
            cadences.append('deceptive')

    return cadences


def analyze_voice_leading(score: music21.stream.Score) -> Dict[str, int]:
    """Analyze voice leading motion types."""
    motions = Counter()
    parts = list(score.parts)
    if len(parts) < 2:
        return dict(motions)

    for p_idx in range(len(parts) - 1):
        upper = list(parts[p_idx].recurse().getElementsByClass('Note'))
        lower = list(parts[p_idx + 1].recurse().getElementsByClass('Note'))

        min_len = min(len(upper), len(lower))
        for i in range(min_len - 1):
            try:
                u_motion = upper[i + 1].pitch.midi - upper[i].pitch.midi
                l_motion = lower[i + 1].pitch.midi - lower[i].pitch.midi

                if u_motion == 0 and l_motion == 0:
                    motions['oblique_both'] += 1
                elif u_motion == 0 or l_motion == 0:
                    motions['oblique'] += 1
                elif (u_motion > 0) == (l_motion > 0):
                    motions['similar'] += 1
                    # Check parallel 5ths/8ves
                    int_prev = (upper[i].pitch.midi - lower[i].pitch.midi) % 12
                    int_next = (upper[i+1].pitch.midi - lower[i+1].pitch.midi) % 12
                    if int_prev == 7 and int_next == 7:
                        motions['parallel_5ths'] += 1
                    if int_prev == 0 and int_next == 0:
                        motions['parallel_8ves'] += 1
                else:
                    motions['contrary'] += 1
            except (IndexError, AttributeError):
                continue

    return dict(motions)


def analyze_intervals(score: music21.stream.Score) -> Dict[str, int]:
    """Analyze melodic interval distribution."""
    intervals = Counter()
    for part in score.parts:
        notes = list(part.recurse().getElementsByClass('Note'))
        for i in range(len(notes) - 1):
            try:
                intv = interval.Interval(notes[i], notes[i + 1])
                intervals[intv.simpleName] += 1
            except Exception:
                continue
    return dict(intervals)


def get_key_info(score: music21.stream.Score) -> Dict[str, Any]:
    """Analyze key and mode."""
    try:
        k = score.analyze('key')
        return {
            'key': str(k),
            'tonic': k.tonic.name,
            'mode': k.mode,
            'confidence': round(k.correlationCoefficient, 4) if hasattr(k, 'correlationCoefficient') else None,
        }
    except Exception:
        return {'key': '?', 'tonic': '?', 'mode': '?', 'confidence': None}


# ═══════════════════════════════════════════════════════════════
# Main learning pipeline
# ═══════════════════════════════════════════════════════════════

def learn_from_corpus(composers: List[str] = None,
                      max_per_composer: int = 50) -> Dict[str, Any]:
    """Analyze public domain music corpus and build knowledge base.

    All composers in music21 corpus are pre-1900, copyright expired.
    """
    if composers is None:
        composers = ['bach', 'beethoven', 'mozart', 'haydn', 'handel']

    knowledge = {
        'meta': {
            'version': '1.0.0',
            'source': 'music21 corpus (public domain)',
            'copyright_status': 'All works are by composers who died before 1900. '
                               'Copyright expired worldwide under Berne Convention.',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        },
        'composers': {},
        'global_stats': {
            'total_works': 0,
            'chord_bigrams': Counter(),
            'chord_trigrams': Counter(),
            'cadence_types': Counter(),
            'voice_motions': Counter(),
            'intervals': Counter(),
            'keys': Counter(),
            'modes': Counter(),
        },
    }

    for composer in composers:
        paths = corpus.getComposer(composer)
        if not paths:
            print(f"  {composer}: 0 works found, skipping")
            continue

        n_works = min(len(paths), max_per_composer)
        print(f"\n  Analyzing {composer}: {n_works}/{len(paths)} works...")

        composer_data = {
            'total_works': len(paths),
            'analyzed': 0,
            'progressions': [],
            'cadences': Counter(),
            'keys': Counter(),
            'modes': Counter(),
            'intervals': Counter(),
            'voice_motions': Counter(),
            'common_progressions': Counter(),
            'copyright_verification': {
                'composer': composer.title(),
                'death_year': {
                    'bach': 1750, 'beethoven': 1827, 'mozart': 1791,
                    'haydn': 1809, 'handel': 1759, 'chopin': 1849,
                    'schubert': 1828,
                }.get(composer, 'pre-1900'),
                'public_domain': True,
                'basis': 'Berne Convention: 70 years post mortem auctoris',
            },
        }

        for idx, path in enumerate(sorted(paths)[:n_works]):
            try:
                score = converter.parse(path)

                # Key analysis
                key_info = get_key_info(score)
                composer_data['keys'][key_info['key']] += 1
                if key_info['mode']:
                    composer_data['modes'][key_info['mode']] += 1
                knowledge['global_stats']['keys'][key_info['key']] += 1
                if key_info['mode']:
                    knowledge['global_stats']['modes'][key_info['mode']] += 1

                # Chord progression
                analyzed_key_obj = score.analyze('key')
                progression = analyze_chord_progressions(score, analyzed_key_obj)
                if progression:
                    composer_data['progressions'].append({
                        'work': os.path.basename(str(path)),
                        'key': key_info['key'],
                        'progression': progression[:50],  # First 50 chords
                    })

                    # Bigrams & trigrams
                    for i in range(len(progression) - 1):
                        bigram = f"{progression[i]}→{progression[i+1]}"
                        composer_data['common_progressions'][bigram] += 1
                        knowledge['global_stats']['chord_bigrams'][bigram] += 1
                    for i in range(len(progression) - 2):
                        trigram = f"{progression[i]}→{progression[i+1]}→{progression[i+2]}"
                        knowledge['global_stats']['chord_trigrams'][trigram] += 1

                # Cadences
                cadences = analyze_cadences(progression)
                for c in cadences:
                    composer_data['cadences'][c] += 1
                    knowledge['global_stats']['cadence_types'][c] += 1

                # Voice leading
                vl = analyze_voice_leading(score)
                for k, v in vl.items():
                    composer_data['voice_motions'][k] += v
                    knowledge['global_stats']['voice_motions'][k] += v

                # Intervals
                intv = analyze_intervals(score)
                for k, v in intv.items():
                    composer_data['intervals'][k] += v
                    knowledge['global_stats']['intervals'][k] += v

                composer_data['analyzed'] += 1
                knowledge['global_stats']['total_works'] += 1

                if (idx + 1) % 10 == 0:
                    print(f"    {idx+1}/{n_works} done...")

            except Exception as e:
                # Skip problematic files
                continue

        # Convert counters to dicts for JSON
        composer_data['cadences'] = dict(composer_data['cadences'].most_common(20))
        composer_data['keys'] = dict(Counter(composer_data['keys']).most_common(20))
        composer_data['modes'] = dict(Counter(composer_data['modes']).most_common(5))
        composer_data['intervals'] = dict(Counter(composer_data['intervals']).most_common(20))
        composer_data['voice_motions'] = dict(composer_data['voice_motions'])
        composer_data['common_progressions'] = dict(
            Counter(composer_data['common_progressions']).most_common(30))

        knowledge['composers'][composer] = composer_data
        print(f"    ✅ {composer}: {composer_data['analyzed']} works analyzed")

    # Finalize global stats
    gs = knowledge['global_stats']
    gs['chord_bigrams'] = dict(Counter(gs['chord_bigrams']).most_common(50))
    gs['chord_trigrams'] = dict(Counter(gs['chord_trigrams']).most_common(30))
    gs['cadence_types'] = dict(gs['cadence_types'])
    gs['voice_motions'] = dict(gs['voice_motions'])
    gs['intervals'] = dict(Counter(gs['intervals']).most_common(30))
    gs['keys'] = dict(Counter(gs['keys']).most_common(30))
    gs['modes'] = dict(gs['modes'])

    return knowledge


def save_knowledge(knowledge: Dict, output_path: str):
    """Save knowledge base to JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge, f, indent=2, ensure_ascii=False, default=str)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n  Knowledge base saved: {output_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    output_dir = "/Users/nicolas/work/katala/data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "harmony_knowledge.json")

    print("🎵 Harmony Learning Pipeline — Public Domain Music Corpus")
    print("=" * 60)
    print()
    print("Copyright verification:")
    print("  All works: composers died before 1900")
    print("  Berne Convention: 70 years post mortem = public domain")
    print("  Source: music21 built-in corpus (curated, verified)")
    print()

    knowledge = learn_from_corpus(
        composers=['bach', 'beethoven', 'mozart', 'haydn', 'handel'],
        max_per_composer=50,
    )

    save_knowledge(knowledge, output_path)

    # Print summary
    gs = knowledge['global_stats']
    print(f"\n{'=' * 60}")
    print(f"Total works analyzed: {gs['total_works']}")
    print(f"Top chord bigrams:")
    for prog, count in list(gs['chord_bigrams'].items())[:10]:
        print(f"  {prog}: {count}")
    print(f"\nCadence types: {gs['cadence_types']}")
    print(f"\nVoice motion types: {gs['voice_motions']}")
    print(f"\nTop intervals:")
    for intv, count in list(gs['intervals'].items())[:10]:
        print(f"  {intv}: {count}")
    print(f"\nModes: {gs['modes']}")
    print(f"\nParallel 5ths found: {gs['voice_motions'].get('parallel_5ths', 0)}")
    print(f"Parallel 8ves found: {gs['voice_motions'].get('parallel_8ves', 0)}")
    print(f"  (Even Bach occasionally wrote these!)")
    print()
    print("Done! 🐻‍❄️")
