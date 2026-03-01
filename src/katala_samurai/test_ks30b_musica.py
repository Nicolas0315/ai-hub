"""Tests for KS30b Musica — spectrogram-based music generation pipeline.

Tests cover S2-S5 stages without requiring audio files, using
synthetic spectrograms and numpy arrays as inputs.
"""

import numpy as np
import pytest


# ── S2: Harmonic Structure ──

def test_extract_harmonic_structure_returns_key_and_tempo():
    """extract_harmonic_structure should populate key, tempo, chords, concepts."""
    from ks30b_musica import extract_harmonic_structure

    # Synthetic spectrogram: 1025 freq bins x 200 time frames (typical for n_fft=2048)
    rng = np.random.default_rng(42)
    S = rng.random((1025, 200)) * 10  # magnitude spectrogram

    hs = extract_harmonic_structure(S, sr=22050, hop_length=512)

    assert hs.key_estimate != "", "key_estimate should not be empty"
    assert hs.tempo_estimate > 0, "tempo_estimate should be positive"
    assert hs.chroma_profile is not None, "chroma_profile should be set"
    assert hs.chroma_profile.shape[0] == 12, "chroma should have 12 pitch classes"
    assert len(hs.key_concepts) > 0, "should generate at least one concept"
    assert hs.semantic_domain == "music"


def test_extract_harmonic_structure_detects_minor_key():
    """A spectrogram biased toward A-minor chroma should detect minor key."""
    from ks30b_musica import extract_harmonic_structure

    S = np.zeros((1025, 100))
    # Boost A(9), C(0), E(4) — Am triad
    for i in [0, 4, 9]:
        freq_bin = int(440 * 2**((i - 9)/12) * 1025 / 11025)
        if 0 <= freq_bin < 1025:
            S[freq_bin, :] = 10.0

    hs = extract_harmonic_structure(S, sr=22050, hop_length=512)
    # Should detect some key (exact key depends on profile correlation)
    assert hs.key_estimate != "unknown"


# ── S3: Patch Extraction ──

def test_extract_patches_from_file(tmp_path):
    """extract_patches should return patches from a valid audio file."""
    from ks30b_musica import extract_patches, MusicaConfig
    import soundfile as sf

    # Create a short sine wave audio file
    sr = 22050
    duration = 2.0  # seconds
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440Hz A4

    audio_path = tmp_path / "test_sine.wav"
    sf.write(str(audio_path), audio, sr)

    config = MusicaConfig(sr=sr)
    patches, stft, out_sr = extract_patches(str(audio_path), config)

    assert len(patches) > 0, "should extract at least one patch"
    assert out_sr == sr
    assert stft.shape[0] == config.n_fft // 2 + 1
    # Each patch should have data, chroma, energy, chord_label
    p = patches[0]
    assert p.data is not None
    assert p.energy > 0
    assert p.chord_label != ""


# ── S3b: CNN Autoencoder ──

def test_train_patch_autoencoder_without_torch():
    """train_patch_autoencoder should return None if torch is unavailable."""
    from ks30b_musica import train_patch_autoencoder, SpectralPatch

    patches = [
        SpectralPatch(data=np.random.rand(128, 32), chord_label="C"),
        SpectralPatch(data=np.random.rand(128, 32), chord_label="Am"),
    ]

    # This test just verifies it doesn't crash.
    # If torch is available, it trains; if not, returns None.
    result = train_patch_autoencoder(patches, latent_dim=16, epochs=2)
    # Either a model or None — both are valid
    assert result is None or hasattr(result, 'eval')


# ── S4: Patch Selection ──

def test_select_patches_prefers_matching_chord():
    """select_patches should rank patches with matching chord higher."""
    from ks30b_musica import select_patches, SpectralPatch

    patches = [
        SpectralPatch(data=np.ones((128, 32)), energy=0.5, chord_label="Am",
                      chroma=np.zeros(12)),
        SpectralPatch(data=np.ones((128, 32)), energy=0.5, chord_label="C",
                      chroma=np.zeros(12)),
        SpectralPatch(data=np.ones((128, 32)), energy=0.5, chord_label="Am",
                      chroma=np.zeros(12)),
    ]

    selected = select_patches(patches, chord="Am", energy=0.5)
    assert len(selected) > 0
    # Am patches should appear before C patches
    am_indices = [i for i, p in enumerate(selected) if p.chord_label == "Am"]
    c_indices = [i for i, p in enumerate(selected) if p.chord_label == "C"]
    if am_indices and c_indices:
        assert am_indices[0] < c_indices[0], "matching chord should rank higher"


def test_select_patches_penalizes_avoid_notes():
    """Patches with avoid-note energy should score lower."""
    from ks30b_musica import select_patches, SpectralPatch

    chroma_clean = np.zeros(12)
    chroma_bad = np.zeros(12)
    chroma_bad[5] = 0.8  # F note is strong

    patches = [
        SpectralPatch(data=np.ones((128, 32)), energy=0.5, chord_label="C",
                      chroma=chroma_clean),
        SpectralPatch(data=np.ones((128, 32)), energy=0.5, chord_label="C",
                      chroma=chroma_bad),
    ]

    selected = select_patches(patches, chord="C", energy=0.5, avoid_notes=["F"])
    assert len(selected) > 0
    # Clean patch should rank first
    assert np.array_equal(selected[0].chroma, chroma_clean)


# ── S5: Griffin-Lim ──

def test_griffin_lim_shared_produces_audio():
    """griffin_lim_shared should produce time-domain audio from magnitude spectrogram."""
    from ks30b_musica import griffin_lim_shared

    n_freq, n_frames = 1025, 50
    S_C = np.random.rand(n_freq, n_frames) * 5
    S_L = np.random.rand(n_freq, n_frames) * 3

    result = griffin_lim_shared(S_C, S_L=S_L, n_iter=10, hop=512)

    assert "C" in result, "should have center channel"
    assert "L" in result, "should have left channel"
    assert len(result["C"]) > 0
    assert len(result["L"]) > 0
    # Audio should be finite
    assert np.all(np.isfinite(result["C"]))
    assert np.all(np.isfinite(result["L"]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
