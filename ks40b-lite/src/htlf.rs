//! HTLF (Holographic Translation Loss Framework) — Rust implementation
//!
//! 3-axis model: R_struct × R_context × R_qualia
//! 5 layers: math / formal_language / natural_language / music / creative
//!
//! Design: Youta Hilono (2026-02-28)

use crate::TranslationLoss;
use regex::Regex;

/// Detect which symbolic layer a text belongs to
pub fn detect_layer(text: &str) -> String {
    let scores = [
        ("math", score_math(text)),
        ("formal_language", score_formal(text)),
        ("music", score_music(text)),
        ("creative", score_creative(text)),
        ("natural_language", 0.1), // default fallback
    ];

    scores.iter()
        .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(layer, _)| layer.to_string())
        .unwrap_or_else(|| "natural_language".to_string())
}

fn score_math(text: &str) -> f64 {
    let patterns = [r"[∑∫∀∃∈⊂⊆]", r"\btheorem\b", r"\blemma\b", r"\bproof\b",
                    r"\d+\s*[+\-*/=<>≤≥]\s*\d+", r"\bQ\.E\.D\b"];
    count_matches(text, &patterns) as f64 * 0.3
}

fn score_formal(text: &str) -> f64 {
    let patterns = [r"```", r"\bdef\s+", r"\bclass\s+", r"\breturn\b",
                    r"\bimport\b", r"\bSELECT\b", r"\bFROM\b", r"fn\s+\w+"];
    count_matches(text, &patterns) as f64 * 0.3
}

fn score_music(text: &str) -> f64 {
    let patterns = [r"(?i)\b(chord|tempo|melody|harmony|rhythm|crescendo|timbre|BPM)\b"];
    count_matches(text, &patterns) as f64 * 0.5
}

fn score_creative(text: &str) -> f64 {
    let patterns = [r"(?i)\b(color|texture|composition|canvas|aesthetic|brushstroke|installation)\b"];
    count_matches(text, &patterns) as f64 * 0.5
}

fn count_matches(text: &str, patterns: &[&str]) -> usize {
    patterns.iter()
        .filter(|p| Regex::new(p).map(|re| re.is_match(text)).unwrap_or(false))
        .count()
}

/// Estimate translation loss between two layers (no embedding model needed)
pub fn estimate_loss(source_layer: &str, target_layer: &str) -> TranslationLoss {
    let (r_struct, r_context, r_qualia) = match (source_layer, target_layer) {
        (s, t) if s == t => (0.95, 0.90, 0.80),
        // Known high-loss pairs (from HTLF research data)
        ("math", "natural_language") | ("natural_language", "math") => (0.26, 0.48, 0.15),
        ("formal_language", "natural_language") | ("natural_language", "formal_language") => (0.40, 0.55, 0.25),
        ("music", "natural_language") | ("natural_language", "music") => (0.15, 0.30, 0.60),
        ("creative", "natural_language") | ("natural_language", "creative") => (0.20, 0.35, 0.55),
        ("math", "formal_language") | ("formal_language", "math") => (0.70, 0.65, 0.30),
        ("music", "creative") | ("creative", "music") => (0.30, 0.40, 0.70),
        _ => (0.45, 0.35, 0.20),
    };

    let total_loss = 1.0 - (r_struct + r_context + r_qualia) / 3.0;

    TranslationLoss {
        r_struct,
        r_context,
        r_qualia,
        total_loss: total_loss.clamp(0.0, 1.0),
        source_layer: source_layer.to_string(),
        target_layer: target_layer.to_string(),
    }
}
