//! HTLF: Human Translation Loss Framework — 5-axis measurement
//!
//! Measures information loss when translating between representation layers:
//!   math ↔ formal_logic ↔ natural_language ↔ music ↔ creative
//!
//! Full graph model (not linear chain — per Youta's correction).
//! 20 directional pairs between 5 layers.

use crate::{SolverResult, SemanticData, TranslationLoss};
use std::collections::HashMap;

// ── Layer Detection ──

const MATH_MARKERS: &[&str] = &["∀", "∃", "∫", "Σ", "π", "√", "=", "≈", "+", "×", "equation", "方程式"];
const FORMAL_MARKERS: &[&str] = &["∧", "∨", "¬", "→", "⊢", "theorem", "lemma", "proof", "定理", "証明"];
const MUSIC_MARKERS: &[&str] = &["♪", "♫", "melody", "chord", "rhythm", "音", "旋律", "和音"];
const CREATIVE_MARKERS: &[&str] = &["poem", "story", "art", "metaphor", "詩", "物語", "芸術", "比喩"];

pub fn detect_layer(text: &str) -> String {
    let lower = text.to_lowercase();
    let scores = [
        ("math", MATH_MARKERS.iter().filter(|m| lower.contains(&m.to_lowercase())).count()),
        ("formal_logic", FORMAL_MARKERS.iter().filter(|m| lower.contains(&m.to_lowercase())).count()),
        ("music", MUSIC_MARKERS.iter().filter(|m| lower.contains(&m.to_lowercase())).count()),
        ("creative", CREATIVE_MARKERS.iter().filter(|m| lower.contains(&m.to_lowercase())).count()),
    ];
    scores.iter()
        .max_by_key(|(_, count)| *count)
        .and_then(|(layer, count)| if *count > 0 { Some(layer.to_string()) } else { None })
        .unwrap_or_else(|| "natural_language".to_string())
}

// ── Semantic Parse (heuristic, no LLM) ──

pub fn semantic_parse(claim: &str) -> SemanticData {
    let mut propositions = Vec::new();
    let mut entities = Vec::new();
    let mut relations = Vec::new();

    // Split into propositions by sentence-ending markers
    let delimiters = ['。', '.', '、', ',', '；', ';'];
    let mut current = String::new();
    for ch in claim.chars() {
        if delimiters.contains(&ch) {
            let trimmed = current.trim().to_string();
            if trimmed.len() > 3 {
                propositions.push(trimmed);
            }
            current.clear();
        } else {
            current.push(ch);
        }
    }
    let trimmed = current.trim().to_string();
    if trimmed.len() > 3 {
        propositions.push(trimmed);
    }

    // Extract entities (capitalized words, quoted terms, CJK nouns after particles)
    let words: Vec<&str> = claim.split_whitespace().collect();
    for word in &words {
        // Capitalized English words
        if word.len() > 1 && word.chars().next().map_or(false, |c| c.is_uppercase()) {
            entities.push(word.to_string());
        }
        // Numbers
        if word.chars().any(|c| c.is_ascii_digit()) && word.len() <= 20 {
            entities.push(word.to_string());
        }
    }

    // Extract CJK compound nouns (simplistic: 2+ kanji sequences)
    let mut kanji_run = String::new();
    for ch in claim.chars() {
        if ('\u{4E00}'..='\u{9FFF}').contains(&ch) {
            kanji_run.push(ch);
        } else {
            if kanji_run.chars().count() >= 2 {
                entities.push(kanji_run.clone());
            }
            kanji_run.clear();
        }
    }
    if kanji_run.chars().count() >= 2 {
        entities.push(kanji_run);
    }

    // Deduplicate entities
    entities.sort();
    entities.dedup();
    if entities.len() > 10 {
        entities.truncate(10);
    }

    // Extract relations from causal/logical markers
    let causal_pairs = [
        ("ため", "causal"), ("よって", "causal"), ("したがって", "implies"),
        ("because", "causal"), ("therefore", "implies"), ("causes", "causal"),
        ("結果", "result"), ("含む", "contains"), ("属する", "member_of"),
        ("is a", "is_a"), ("は", "subject_of"),
    ];
    for (marker, rel_type) in causal_pairs {
        if claim.contains(marker) {
            relations.push(rel_type.to_string());
        }
    }

    // Detect domain
    let domain = detect_domain(claim);

    SemanticData {
        propositions,
        entities,
        relations,
        domain,
        source: "heuristic_rust".to_string(),
    }
}

fn detect_domain(claim: &str) -> String {
    let lower = claim.to_lowercase();
    let domain_keywords: &[(&str, &[&str])] = &[
        ("physics", &["物理", "量子", "重力", "エネルギー", "physics", "quantum", "gravity"]),
        ("biology", &["生物", "細胞", "DNA", "遺伝", "biology", "cell", "gene"]),
        ("computer_science", &["コンピュータ", "GPU", "CUDA", "アルゴリズム", "computer", "algorithm", "AI"]),
        ("mathematics", &["数学", "定理", "証明", "math", "theorem", "proof"]),
        ("linguistics", &["言語", "翻訳", "文法", "language", "translation", "grammar"]),
        ("philosophy", &["哲学", "認識", "存在", "philosophy", "epistemology", "ontology"]),
    ];

    domain_keywords.iter()
        .max_by_key(|(_, kws)| kws.iter().filter(|kw| lower.contains(&kw.to_lowercase())).count())
        .and_then(|(domain, kws)| {
            if kws.iter().any(|kw| lower.contains(&kw.to_lowercase())) {
                Some(domain.to_string())
            } else {
                None
            }
        })
        .unwrap_or_else(|| "general".to_string())
}

// ── Coherence ──

pub fn compute_coherence(solver_results: &[SolverResult]) -> f64 {
    if solver_results.is_empty() {
        return 0.0;
    }
    let confidences: Vec<f64> = solver_results.iter().map(|r| r.confidence).collect();
    let mean = confidences.iter().sum::<f64>() / confidences.len() as f64;
    let variance = confidences.iter().map(|c| (c - mean).powi(2)).sum::<f64>() / confidences.len() as f64;
    // High coherence = low variance
    (1.0 - variance.sqrt() * 2.0).max(0.0).min(1.0)
}

// ── 5-Axis Translation Loss ──

pub fn estimate_loss_5axis(claim: &str, detected_layer: &str, semantic: &SemanticData) -> TranslationLoss {
    let prop_count = semantic.propositions.len() as f64;
    let ent_count = semantic.entities.len() as f64;
    let rel_count = semantic.relations.len() as f64;

    // R_struct: structural preservation (propositions + relations)
    let r_struct = ((prop_count * 0.4 + rel_count * 0.6) / 5.0).min(1.0);

    // R_context: contextual preservation (entities + evidence)
    let r_context = ((ent_count * 0.5 + prop_count * 0.3) / 5.0).min(1.0);

    // R_qualia: subjective experience preservation
    let subjective_markers = ["感じ", "経験", "意識", "直感", "feel", "experience", "conscious"];
    let qualia_present = subjective_markers.iter().any(|m| claim.contains(m));
    let r_qualia = if qualia_present { 0.3 } else { 0.7 };  // Hard to preserve if qualia involved

    // R_cultural: cross-cultural preservation
    let is_multilingual = claim.chars().any(|c| ('\u{3040}'..='\u{30FF}').contains(&c))
        && claim.chars().any(|c| c.is_ascii_alphabetic());
    let r_cultural = if is_multilingual { 0.5 } else { 0.65 };

    // R_temporal: temporal stability (present = stable)
    let future_markers = ["将来", "予測", "になるだろう", "will ", "predict", "forecast"];
    let has_future = future_markers.iter().any(|f| claim.contains(f));
    let r_temporal = if has_future { 0.3 } else { 0.75 };

    let total_loss = 1.0 - (r_struct * 0.25 + r_context * 0.25 + r_qualia * 0.2
        + r_cultural * 0.15 + r_temporal * 0.15);

    TranslationLoss {
        r_struct,
        r_context,
        r_qualia,
        r_cultural,
        r_temporal,
        total_loss,
        source_layer: "natural_language".to_string(),
        target_layer: detected_layer.to_string(),
    }
}

// ── Confidence & Verdict ──

pub fn compute_confidence(pass_rate: f64, coherence: f64, loss: &TranslationLoss) -> f64 {
    let base = pass_rate * 0.5 + coherence * 0.3 + (1.0 - loss.total_loss) * 0.2;
    base.clamp(0.0, 1.0)
}

pub fn determine_verdict(confidence: f64, pass_rate: f64, passed: usize, total: usize) -> String {
    if total == 0 {
        return "NO_SOLVERS".to_string();
    }
    if confidence >= 0.7 && pass_rate >= 0.8 {
        "VERIFIED".to_string()
    } else if confidence < 0.35 || pass_rate < 0.4 {
        "UNVERIFIED".to_string()
    } else {
        "EXPLORING".to_string()
    }
}
