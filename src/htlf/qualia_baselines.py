"""Behavioral qualia baseline distributions from affective psychology literature.

All values are normalized to [0, 1] valence/arousal space.
Tuple format: (mean, std).
"""

from __future__ import annotations

# Russell circumplex model anchor (Russell, 1980) applied to music features.
# Means/stds are practical priors informed by music-emotion meta trends
# (e.g., Eerola & Vuoskoski, 2011; Juslin & Laukka, 2004).
MUSIC_BASELINES: dict[str, dict[str, tuple[float, float]]] = {
    "major_fast": {"valence": (0.70, 0.15), "arousal": (0.70, 0.12)},  # happy/excited cluster
    "major_slow": {"valence": (0.64, 0.14), "arousal": (0.42, 0.14)},  # calm-positive cluster
    "minor_fast": {"valence": (0.38, 0.18), "arousal": (0.66, 0.16)},  # tense/angry cluster
    "minor_slow": {"valence": (0.30, 0.18), "arousal": (0.30, 0.14)},  # sad/low-arousal cluster
    "dissonant": {"valence": (0.25, 0.20), "arousal": (0.65, 0.18)},  # tension/roughness findings
    "consonant": {"valence": (0.68, 0.14), "arousal": (0.48, 0.15)},  # pleasantness of consonance
    "resolution_v7_i": {"valence": (0.75, 0.12), "arousal": (0.40, 0.15)},  # expectancy resolution reward
    "staccato": {"valence": (0.50, 0.16), "arousal": (0.72, 0.14)},  # short IOI -> high activation
    "legato": {"valence": (0.58, 0.15), "arousal": (0.40, 0.14)},  # smooth contour -> lower activation
}

# Visual affect priors (Palmer et al., 2013 color-emotion associations;
# Line/contrast/arousal trends in empirical aesthetics reviews).
VISUAL_BASELINES: dict[str, dict[str, tuple[float, float]]] = {
    "warm_high_contrast": {"valence": (0.60, 0.15), "arousal": (0.70, 0.12)},
    "warm_low_contrast": {"valence": (0.62, 0.14), "arousal": (0.45, 0.15)},
    "cool_high_contrast": {"valence": (0.48, 0.18), "arousal": (0.62, 0.16)},
    "cool_low_contrast": {"valence": (0.50, 0.18), "arousal": (0.30, 0.15)},
    "dark_chaotic": {"valence": (0.30, 0.22), "arousal": (0.72, 0.18)},
    "minimalist": {"valence": (0.55, 0.20), "arousal": (0.28, 0.15)},
    "rothko_color_field": {"valence": (0.55, 0.25), "arousal": (0.50, 0.20)},  # broad dispersion noted in museum studies
}

# Juslin & Västfjäll (2008) BRECVEMA mechanisms (conceptual weighting adapted for priors).
EMOTION_MECHANISM_WEIGHTS: dict[str, float] = {
    "brain_stem_reflex": 0.15,  # sudden/loud sensory triggers
    "evaluative_conditioning": 0.10,  # learned associations
    "emotional_contagion": 0.20,  # mimicry of expression/timbre
    "visual_imagery": 0.15,  # induced imagery
    "episodic_memory": 0.15,  # autobiographical memory
    "musical_expectancy": 0.25,  # prediction/deviation dynamics
}


def merged_baseline_space() -> dict[str, dict[str, tuple[float, float]]]:
    """Return merged baseline dictionary for lookup."""
    merged: dict[str, dict[str, tuple[float, float]]] = {}
    merged.update(MUSIC_BASELINES)
    merged.update(VISUAL_BASELINES)
    return merged
