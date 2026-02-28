"""Temporal Translation Loss (R_temporal) for HTLF.

Measures information loss when translating across historical periods.

Theoretical foundations:
- Kuhn's Paradigm Theory: Scientific revolutions create incommensurable
  conceptual frameworks. Terms like "mass" mean fundamentally different things
  in Newtonian vs. Einsteinian physics. Translation across paradigm boundaries
  is not just difficult but structurally incomplete.
- Duhem-Quine Thesis (temporal application): A concept from era A cannot be
  isolated from its era's web of beliefs and tested against era B's framework.
  The entire paradigm shifts, not individual propositions.
- Barthes' "Death of the Author" / Text arbitrariness: Once a text leaves its
  temporal context, its meaning is reconstituted by each new era's interpretive
  community. The "same" text (e.g., Shakespeare's sonnets) carries different
  meanings in 1600, 1900, and 2025. This is not a bug but a structural feature
  of textuality.

Design:
  R_temporal captures THREE distinct phenomena:
  1. Paradigmatic incommensurability (Kuhn): concepts that don't map across eras
  2. Semantic drift (Barthes): meaning that shifts over time within the "same" language
  3. Contextual web decay (Duhem-Quine): background knowledge that's lost/changed

  Like R_cultural, R_temporal includes an indeterminacy measure.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from . import rust_bridge as rb


@dataclass(slots=True)
class TemporalLossResult:
    """Temporal translation loss with paradigmatic incommensurability."""
    loss_estimate: float            # Best estimate of temporal loss [0,1]
    indeterminacy: float            # How underdetermined the loss is [0,1]
    paradigm_distance: float        # Kuhnian paradigmatic distance [0,1]
    semantic_drift: float           # Barthesian meaning drift [0,1]
    web_decay: float                # Duhem-Quine contextual web decay [0,1]
    incommensurable_concepts: list[str]  # Concepts that don't translate across eras
    era_source: str                 # Detected or specified source era
    era_target: str                 # Detected or specified target era
    backend: str


# Era detection patterns
_ERA_MARKERS: dict[str, list[str]] = {
    "ancient": [
        r"\b(aristotle|plato|socrates|euclid|ptolemy|galen|hippocrates)\b",
        r"\b(ancient|classical|antiquity|hellenistic|roman empire)\b",
        r"\b(rhetoric|syllogism|four elements|celestial sphere|humou?rs)\b",
    ],
    "medieval": [
        r"\b(aquinas|augustine|scholastic|medieval|feudal|alchemy)\b",
        r"\b(trivium|quadrivium|great chain of being|cathedral|monastery)\b",
    ],
    "early_modern": [
        r"\b(descartes|newton|galileo|copernicus|bacon|hobbes|locke)\b",
        r"\b(enlightenment|mechanical philosophy|clockwork universe)\b",
        r"\b(phlogiston|aether|caloric|corpuscle|natural philosophy)\b",
    ],
    "modern_19c": [
        r"\b(darwin|maxwell|boltzmann|helmholtz|faraday)\b",
        r"\b(thermodynamics|electromagnetism|evolution|industrial)\b",
        r"\b(vitalism|luminiferous|absolute space|determinism)\b",
    ],
    "early_20c": [
        r"\b(einstein|bohr|heisenberg|schrödinger|planck|curie)\b",
        r"\b(relativity|quantum mechanics|uncertainty principle)\b",
        r"\b(logical positivism|vienna circle|verificationism)\b",
    ],
    "late_20c": [
        r"\b(kuhn|feyerabend|lakatos|popper|quine|derrida|foucault)\b",
        r"\b(postmodern|deconstruction|paradigm shift|chaos theory)\b",
        r"\b(information theory|cybernetics|systems theory)\b",
    ],
    "contemporary": [
        r"\b(deep learning|transformer|GPT|CRISPR|mRNA|blockchain)\b",
        r"\b(climate change|anthropocene|post-truth|misinformation)\b",
        r"\b(neural network|machine learning|artificial intelligence|LLM)\b",
    ],
}

# Paradigmatic incommensurability: concept pairs that changed meaning across eras
_PARADIGM_SHIFTS: list[dict[str, Any]] = [
    {
        "concept": "mass",
        "eras": ["early_modern", "early_20c"],
        "description": "Newtonian absolute mass → relativistic mass-energy equivalence",
    },
    {
        "concept": "atom",
        "eras": ["ancient", "early_20c"],
        "description": "Democritean indivisible particle → quantum probability cloud",
    },
    {
        "concept": "species",
        "eras": ["medieval", "modern_19c"],
        "description": "Fixed divine creation → mutable product of natural selection",
    },
    {
        "concept": "space",
        "eras": ["early_modern", "early_20c"],
        "description": "Newtonian absolute container → Einsteinian dynamic geometry",
    },
    {
        "concept": "cause",
        "eras": ["ancient", "early_modern"],
        "description": "Aristotelian four causes → Humean constant conjunction",
    },
    {
        "concept": "information",
        "eras": ["early_modern", "late_20c"],
        "description": "Semantic content → Shannon's entropy (content-independent)",
    },
    {
        "concept": "gene",
        "eras": ["modern_19c", "contemporary"],
        "description": "Mendelian discrete factor → regulatory network node",
    },
    {
        "concept": "computation",
        "eras": ["early_modern", "contemporary"],
        "description": "Human calculation → universal Turing machine → neural network",
    },
    {
        "concept": "music",
        "eras": ["ancient", "contemporary"],
        "description": "Pythagorean cosmic harmony → culturally constructed sound organization",
    },
    {
        "concept": "art",
        "eras": ["medieval", "late_20c"],
        "description": "Divine mimesis → institutional theory / anything-goes",
    },
]

# Semantic drift markers: words whose meaning shifted significantly
_DRIFT_TERMS: dict[str, list[tuple[str, str, float]]] = {
    # term: [(era1_meaning, era2_meaning, drift_magnitude), ...]
    "nice": [("foolish/ignorant (medieval)", "pleasant (modern)", 0.9)],
    "awful": [("full of awe (original)", "terrible (modern)", 0.85)],
    "paradigm": [("example/pattern (Kuhn pre-1962)", "dominant framework (post-Kuhn)", 0.7)],
    "theory": [("contemplation (Greek theoria)", "empirically testable framework (modern)", 0.6)],
    "virtual": [("having virtue/power (medieval)", "computer-simulated (modern)", 0.8)],
    "decimate": [("kill one in ten (Roman)", "destroy large portion (modern)", 0.7)],
    "algorithm": [("al-Khwarizmi's arithmetic (medieval)", "computational procedure (modern)", 0.5)],
    "cell": [("small room (Hooke 1665)", "fundamental unit of life (modern)", 0.6)],
    "energy": [("Aristotelian energeia/actuality", "physics: capacity to do work", 0.7)],
    "revolution": [("celestial revolution (Copernicus)", "political/paradigmatic upheaval", 0.65)],
}

# Era ordering for distance computation
_ERA_ORDER = ["ancient", "medieval", "early_modern", "modern_19c", 
              "early_20c", "late_20c", "contemporary"]


def _detect_era(text: str) -> tuple[str, float]:
    """Detect the most likely historical era of the text."""
    text_lower = text.lower()
    era_scores: dict[str, float] = {}
    
    for era, patterns in _ERA_MARKERS.items():
        hits = 0
        for pat in patterns:
            hits += len(re.findall(pat, text_lower, re.IGNORECASE))
        if hits > 0:
            era_scores[era] = hits
    
    if not era_scores:
        return ("contemporary", 0.3)  # Default with low confidence
    
    best_era = max(era_scores, key=lambda k: era_scores[k])
    total = sum(era_scores.values())
    confidence = era_scores[best_era] / total if total > 0 else 0.0
    
    return (best_era, min(1.0, confidence))


def _paradigm_distance(era_source: str, era_target: str) -> float:
    """Compute Kuhnian paradigmatic distance between eras.
    
    Not simply chronological distance — paradigm shifts create
    discontinuous jumps in conceptual frameworks.
    """
    if era_source == era_target:
        return 0.0
    
    try:
        idx_s = _ERA_ORDER.index(era_source)
        idx_t = _ERA_ORDER.index(era_target)
    except ValueError:
        return 0.3  # Unknown era pair
    
    # Base chronological distance
    chrono_dist = abs(idx_s - idx_t) / max(1, len(_ERA_ORDER) - 1)
    
    # Major paradigm shift amplifiers
    shift_pairs = {
        frozenset({"ancient", "early_modern"}): 0.15,      # Scientific revolution
        frozenset({"early_modern", "early_20c"}): 0.20,    # Relativity/quantum
        frozenset({"modern_19c", "early_20c"}): 0.15,      # Physics revolution
        frozenset({"late_20c", "contemporary"}): 0.10,     # Digital/AI revolution
        frozenset({"medieval", "early_modern"}): 0.15,     # Enlightenment
    }
    
    pair = frozenset({era_source, era_target})
    shift_amp = 0.0
    # Check if the path crosses any major shift boundaries
    min_idx, max_idx = min(idx_s, idx_t), max(idx_s, idx_t)
    for shift_pair, amp in shift_pairs.items():
        shift_eras = list(shift_pair)
        try:
            shift_indices = [_ERA_ORDER.index(e) for e in shift_eras]
            si_min, si_max = min(shift_indices), max(shift_indices)
            if min_idx <= si_min and si_max <= max_idx:
                shift_amp += amp
        except ValueError:
            continue
    
    return min(1.0, chrono_dist + shift_amp)


def _detect_incommensurable_concepts(source_text: str, target_text: str,
                                      era_source: str, era_target: str) -> list[str]:
    """Find concepts that underwent paradigm shifts between the source and target eras."""
    incomm = []
    combined_text = (source_text + " " + target_text).lower()
    
    for shift in _PARADIGM_SHIFTS:
        concept = shift["concept"]
        shift_eras = shift["eras"]
        
        # Check if concept appears in text
        if concept.lower() in combined_text:
            # Check if the era pair spans this paradigm shift
            try:
                src_idx = _ERA_ORDER.index(era_source)
                tgt_idx = _ERA_ORDER.index(era_target)
                shift_indices = [_ERA_ORDER.index(e) for e in shift_eras if e in _ERA_ORDER]
                
                if shift_indices:
                    min_shift = min(shift_indices)
                    max_shift = max(shift_indices)
                    min_pair = min(src_idx, tgt_idx)
                    max_pair = max(src_idx, tgt_idx)
                    
                    if min_pair <= min_shift and max_shift <= max_pair:
                        incomm.append(f"{concept}: {shift['description']}")
            except ValueError:
                continue
    
    return incomm


def _compute_semantic_drift(source_text: str, target_text: str) -> float:
    """Measure Barthesian semantic drift — how much word meanings have shifted.
    
    Barthes' insight: the text is not a container of fixed meaning but a
    tissue of quotations, drawn from innumerable centres of culture.
    Each reading reconstitutes meaning. Over time, this reconstitution
    diverges from any "original" intent.
    """
    combined = (source_text + " " + target_text).lower()
    total_drift = 0.0
    drift_count = 0
    
    for term, drifts in _DRIFT_TERMS.items():
        if term.lower() in combined:
            for _, _, magnitude in drifts:
                total_drift += magnitude
                drift_count += 1
    
    if drift_count == 0:
        return 0.0
    
    # Average drift of detected terms, scaled
    return min(1.0, (total_drift / drift_count) * min(1.0, drift_count / 3.0))


def _compute_web_decay(paradigm_distance: float, 
                        incommensurable_count: int,
                        semantic_drift: float) -> float:
    """Compute Duhem-Quine contextual web decay.
    
    The web of beliefs that gives meaning to any individual concept
    decays as temporal distance increases. This is not simply forgetting —
    it's the structural dissolution of the interpretive context.
    
    Duhem-Quine: you can't test (or translate) a single proposition in
    isolation. The entire auxiliary web must come along. Over time,
    that web degrades.
    """
    return min(1.0,
        0.40 * paradigm_distance +
        0.30 * min(1.0, incommensurable_count / 4.0) +
        0.30 * semantic_drift
    )


def compute_temporal_loss(source_text: str, target_text: str,
                           source_era: str | None = None,
                           target_era: str | None = None) -> TemporalLossResult:
    """Compute temporal translation loss with paradigmatic incommensurability.
    
    Returns both a loss estimate and an indeterminacy measure.
    The indeterminacy reflects Quine's insight that translation across
    paradigm boundaries is underdetermined — there are multiple equally
    valid ways to map concepts across eras, each with different loss profiles.
    """
    # Detect eras if not specified
    if source_era is None:
        source_era, _ = _detect_era(source_text)
    if target_era is None:
        target_era, _ = _detect_era(target_text)
    
    # Kuhnian paradigmatic distance (Rust-accelerated)
    p_distance, n_shifts = rb.rust_paradigm_distance(source_era, target_era)
    
    # Incommensurable concepts
    incomm = _detect_incommensurable_concepts(
        source_text, target_text, source_era, target_era
    )
    
    # Barthesian semantic drift
    drift = _compute_semantic_drift(source_text, target_text)
    
    # Loss/indeterminacy/web_decay via Rust (or Python fallback)
    loss_estimate, indeterminacy, web = rb.rust_compute_temporal_loss(
        p_distance, len(incomm), drift
    )
    
    return TemporalLossResult(
        loss_estimate=round(loss_estimate, 4),
        indeterminacy=round(indeterminacy, 4),
        paradigm_distance=round(p_distance, 4),
        semantic_drift=round(drift, 4),
        web_decay=round(web, 4),
        incommensurable_concepts=incomm,
        era_source=source_era,
        era_target=target_era,
        backend="rust" if rb.RUST_AVAILABLE else "heuristic",
    )
