"""Cultural Translation Loss (R_cultural) for HTLF.

Measures information loss when translating between cultural conceptual frameworks.

Theoretical foundations:
- Quine's Indeterminacy of Translation: No fact of the matter about "correct"
  translation between radically different conceptual schemes. Translation is
  underdetermined by all possible behavioral evidence.
- Duhem-Quine Thesis: Individual concepts cannot be tested in isolation;
  they form a holistic web of belief. Cultural context is this web.
- Barthes' Death of the Author: Meaning is not fixed by origin but
  reconstituted by the receiving cultural context.

Design:
  R_cultural is NOT a single score but a tuple: (loss_estimate, indeterminacy)
  - loss_estimate: best estimate of cultural information loss [0,1]
  - indeterminacy: Quinean indeterminacy range — how much the loss could vary
    under equally valid translation schemes [0,1]

  Total cultural loss = loss_estimate ± indeterminacy
  This captures Quine's insight that there is no unique "correct" measurement.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from . import rust_bridge as rb

_USE_RUST = rb.RUST_AVAILABLE


@dataclass(slots=True)
class CulturalLossResult:
    """Cultural translation loss with Quinean indeterminacy."""
    loss_estimate: float       # Best estimate of cultural loss [0,1]
    indeterminacy: float       # Width of indeterminacy range [0,1]
    cultural_distance: float   # Estimated distance between cultural frames [0,1]
    holistic_dependency: float # Duhem-Quine: how much meaning depends on cultural web [0,1]
    concept_gaps: list[str]    # Untranslatable cultural concepts detected
    backend: str               # "heuristic" | "llm"


# Cultural markers by broad category
_CULTURAL_MARKERS: dict[str, list[str]] = {
    "japanese": [
        r"\b(wa[bs]i|sabi|mono no aware|ikigai|shoganai|ganbaru|omotenashi)\b",
        r"[一-龯ぁ-んァ-ヴー]{2,}",  # CJK characters
        r"\b(sensei|senpai|kohai|san|sama|dono|chan|kun)\b",
        r"\b(bushido|zen|wabi|satori|mu|ma|en)\b",
    ],
    "western_academic": [
        r"\b(thesis|antithesis|synthesis|dialectic|hermeneutic|phenomenolog|epistemolog)\b",
        r"\b(cogito|a priori|a posteriori|tabula rasa|zeitgeist|weltanschauung)\b",
        r"\b(logos|ethos|pathos|telos|praxis|mimesis|catharsis)\b",
    ],
    "chinese": [
        r"\b(dao|tao|qi|chi|yin|yang|wuwei|wu wei|li|ren|de|xiao)\b",
        r"[一-龯]{2,}",
    ],
    "arabic_islamic": [
        r"\b(inshallah|mashallah|halal|haram|ummah|jihad|ijtihad|fiqh|sharia|tawhid)\b",
    ],
    "indigenous": [
        r"\b(dreamtime|songline|ubuntu|pachamama|buen vivir)\b",
    ],
    "scientific": [
        r"\b(paradigm|falsif|reproducib|peer.review|hypothesis|empiric|operationali[sz])\b",
    ],
    "musical": [
        r"\b(raga|maqam|gamelan|pentatonic|microtonal|twelve.tone|atonal|polyrhythm)\b",
    ],
}

# Concept gap indicators: terms that signal culturally-bound meaning
_GAP_MARKERS = [
    # Japanese aesthetic/philosophical (romaji + kanji/kana)
    (r"\b(wabi.?sabi|mono no aware|ma|en|musubi)\b", "Japanese aesthetic concept"),
    (r"(侘び寂び|わびさび|もののあはれ|物の哀れ|間|縁|結び|生き甲斐|いきがい)", "Japanese aesthetic concept"),
    (r"\b(amae|giri|ninjo|honne|tatemae)\b", "Japanese social concept"),
    (r"(甘え|義理|人情|本音|建前|おもてなし)", "Japanese social concept"),
    # Western philosophical
    (r"\b(Dasein|Gestell|différance|pharmakon|rhizome)\b", "Continental philosophy"),
    (r"\b(qualia|intentionality|supervenience|epiphenomen)\b", "Philosophy of mind"),
    # Musical system-specific
    (r"\b(shruti|raga|tala|maqam|dastgah)\b", "Non-Western music theory"),
    (r"\b(swing|groove|blue note|backbeat)\b", "African-American music concept"),
    # Scientific paradigm-specific
    (r"\b(phlogiston|aether|caloric|miasma)\b", "Superseded scientific concept"),
    (r"\b(dark energy|string landscape|multiverse)\b", "Speculative physics"),
]


def _detect_cultural_frame(text: str) -> dict[str, float]:
    """Detect cultural markers and return frame weights."""
    text_lower = text.lower()
    frame_scores: dict[str, float] = {}
    
    for frame, patterns in _CULTURAL_MARKERS.items():
        hits = 0
        for pat in patterns:
            hits += len(re.findall(pat, text_lower, re.IGNORECASE))
        if hits > 0:
            # Normalize by text length (per 1000 chars)
            frame_scores[frame] = min(1.0, hits / max(1, len(text) / 1000))
    
    return frame_scores


def _detect_concept_gaps(source_text: str, target_text: str) -> list[str]:
    """Find culturally-bound concepts present in source but absent in target."""
    gaps = []
    target_lower = target_text.lower()
    
    for pattern, label in _GAP_MARKERS:
        source_matches = re.findall(pattern, source_text, re.IGNORECASE)
        if source_matches:
            # Check if concept is preserved in target
            target_matches = re.findall(pattern, target_lower, re.IGNORECASE)
            if not target_matches:
                for m in source_matches:
                    term = m if isinstance(m, str) else m[0] if m else ""
                    if term:
                        gaps.append(f"{term} ({label})")
    
    return list(set(gaps))


def _cultural_frame_distance(source_frames: dict[str, float], 
                              target_frames: dict[str, float]) -> float:
    """Compute distance between two cultural frame distributions.
    
    Duhem-Quine insight: the distance is not between individual concepts
    but between entire webs of belief/cultural context.
    Uses Rust acceleration when available.
    """
    return rb.rust_cultural_frame_distance(
        list(source_frames.items()), list(target_frames.items())
    )


def _compute_holistic_dependency(source_text: str, concept_gaps: list[str],
                                  cultural_distance: float) -> float:
    """Measure how much meaning depends on the cultural web (Duhem-Quine).
    
    High holistic dependency = individual concepts can't be extracted from
    their cultural web without losing meaning. This is the insight from
    the Duhem-Quine thesis applied to cultural translation.
    """
    # Factors that increase holistic dependency:
    # 1. Number of untranslatable concepts
    gap_factor = min(1.0, len(concept_gaps) / 5.0) * 0.4
    
    # 2. Cultural distance (different webs = harder to extract)
    distance_factor = cultural_distance * 0.35
    
    # 3. Text density of cultural markers (more = more web-dependent)
    marker_count = 0
    for patterns in _CULTURAL_MARKERS.values():
        for pat in patterns:
            marker_count += len(re.findall(pat, source_text, re.IGNORECASE))
    density_factor = min(1.0, marker_count / max(1, len(source_text) / 500)) * 0.25
    
    return min(1.0, gap_factor + distance_factor + density_factor)


def _compute_indeterminacy(cultural_distance: float, holistic_dependency: float,
                            concept_gaps: list[str]) -> float:
    """Compute Quinean indeterminacy of translation.
    
    Quine's thesis: translation between radically different languages is
    underdetermined by all possible behavioral evidence. The indeterminacy
    increases with:
    - Cultural distance (more different = more possible translation manuals)
    - Holistic dependency (more web-dependent = more ways to carve up the web)
    - Concept gaps (untranslatable concepts = maximal indeterminacy for those)
    
    Returns: indeterminacy ∈ [0, 1], where 0 = fully determined, 1 = maximally indeterminate
    """
    # Base indeterminacy from cultural distance
    base = cultural_distance * 0.4
    
    # Holistic amplification (Duhem-Quine: more entangled = more underdetermined)
    holistic_amp = holistic_dependency * 0.35
    
    # Gap-driven indeterminacy (untranslatable concepts are maximally indeterminate)
    gap_amp = min(1.0, len(concept_gaps) / 3.0) * 0.25
    
    return min(1.0, base + holistic_amp + gap_amp)


def compute_cultural_loss(source_text: str, target_text: str) -> CulturalLossResult:
    """Compute cultural translation loss with Quinean indeterminacy.
    
    The key philosophical insight: we return BOTH a loss estimate AND
    an indeterminacy measure, because Quine showed that there is no
    unique correct translation — only manuals that are equally compatible
    with behavioral evidence.
    """
    source_frames = _detect_cultural_frame(source_text)
    target_frames = _detect_cultural_frame(target_text)
    
    cultural_distance = _cultural_frame_distance(source_frames, target_frames)
    concept_gaps = _detect_concept_gaps(source_text, target_text)
    # Count markers for Rust path
    marker_count = 0
    for patterns in _CULTURAL_MARKERS.values():
        for pat in patterns:
            marker_count += len(re.findall(pat, source_text, re.IGNORECASE))

    # Compute loss/indeterminacy/holistic via Rust (or Python fallback)
    loss_estimate, indeterminacy, holistic_dependency = rb.rust_compute_cultural_loss(
        cultural_distance, len(concept_gaps), len(source_text), marker_count
    )
    
    return CulturalLossResult(
        loss_estimate=round(loss_estimate, 4),
        indeterminacy=round(indeterminacy, 4),
        cultural_distance=round(cultural_distance, 4),
        holistic_dependency=round(holistic_dependency, 4),
        concept_gaps=concept_gaps,
        backend="rust" if _USE_RUST else "heuristic",
    )
