//! FLM Fusion Planner (KS45) — multi-SLM routing and fusion

use crate::{SemanticData, FusionPlan};

const MAX_ACTIVE_SLMS: usize = 3;
const MIN_WEIGHT: f64 = 0.05;
const MAX_WEIGHT: f64 = 0.80;

/// Virtual SLM profile
struct SlmProfile {
    name: &'static str,
    domain: &'static str,
    params_b: f64,
    specialization: f64,
    factual_score: f64,
}

const SLM_POOL: &[SlmProfile] = &[
    SlmProfile { name: "general-1.5b", domain: "general", params_b: 1.5, specialization: 0.60, factual_score: 0.75 },
    SlmProfile { name: "math-1.5b", domain: "mathematics", params_b: 1.5, specialization: 0.90, factual_score: 0.88 },
    SlmProfile { name: "medical-1.5b", domain: "medicine", params_b: 1.5, specialization: 0.85, factual_score: 0.90 },
    SlmProfile { name: "code-1.5b", domain: "computer_science", params_b: 1.5, specialization: 0.88, factual_score: 0.82 },
    SlmProfile { name: "science-1.5b", domain: "physics", params_b: 1.5, specialization: 0.85, factual_score: 0.86 },
    SlmProfile { name: "language-1.5b", domain: "linguistics", params_b: 1.5, specialization: 0.80, factual_score: 0.78 },
    SlmProfile { name: "philosophy-1.5b", domain: "philosophy", params_b: 1.5, specialization: 0.75, factual_score: 0.72 },
    SlmProfile { name: "biology-1.5b", domain: "biology", params_b: 1.5, specialization: 0.85, factual_score: 0.87 },
];

pub struct FlmPlanner;

impl FlmPlanner {
    pub fn new() -> Self { Self }

    pub fn plan_if_relevant(&self, _claim: &str, semantic: &SemanticData) -> Option<FusionPlan> {
        // Score each SLM for this claim's domain
        let mut scored: Vec<(&SlmProfile, f64)> = SLM_POOL.iter()
            .map(|slm| {
                let domain_match = if slm.domain == semantic.domain { 1.0 }
                    else if slm.domain == "general" { 0.4 }
                    else { 0.2 };
                let score = domain_match * 0.5 + slm.specialization * 0.3 + slm.factual_score * 0.2;
                (slm, score)
            })
            .collect();

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Select top N SLMs
        let selected: Vec<&SlmProfile> = scored.iter()
            .take(MAX_ACTIVE_SLMS)
            .map(|(slm, _)| *slm)
            .collect();

        if selected.is_empty() { return None; }

        // Compute fusion weights (softmax-like)
        let top_scores: Vec<f64> = scored.iter().take(MAX_ACTIVE_SLMS).map(|(_, s)| *s).collect();
        let max_score = top_scores.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let exp_scores: Vec<f64> = top_scores.iter().map(|s| (s - max_score).exp()).collect();
        let sum_exp: f64 = exp_scores.iter().sum();
        let weights: Vec<f64> = exp_scores.iter()
            .map(|e| (e / sum_exp).clamp(MIN_WEIGHT, MAX_WEIGHT))
            .collect();

        // Predicted quality
        let quality: f64 = selected.iter().zip(weights.iter())
            .map(|(slm, w)| slm.factual_score * w)
            .sum::<f64>();

        // Hallucination risk (lower with more specialists)
        let specialist_count = selected.iter()
            .filter(|s| s.domain == semantic.domain)
            .count();
        let hallucination_risk = if specialist_count > 0 { 0.03 } else { 0.08 };

        Some(FusionPlan {
            selected_slms: selected.iter().map(|s| s.name.to_string()).collect(),
            fusion_weights: weights,
            predicted_quality: quality,
            hallucination_risk,
            fusion_overhead_ms: selected.len() as f64 * 12.0,  // ~12ms per SLM
        })
    }
}
