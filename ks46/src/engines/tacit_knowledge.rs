//! Tacit Knowledge Approximation — heuristic domain experience

use crate::{SolverResult, TacitResult};
use std::collections::HashMap;

struct DomainProfile {
    observation_count: usize,
    verified_count: usize,
    confidence_sum: f64,
}

pub struct TacitKnowledgeEngine {
    profiles: HashMap<String, DomainProfile>,
}

impl TacitKnowledgeEngine {
    pub fn new() -> Self { Self { profiles: HashMap::new() } }

    pub fn domain_count(&self) -> usize { self.profiles.len() }

    pub fn analyze(
        &mut self,
        _claim: &str,
        domain: &str,
        confidence: f64,
        verdict: &str,
        solver_results: &[SolverResult],
    ) -> TacitResult {
        let profile = self.profiles.entry(domain.to_string())
            .or_insert(DomainProfile { observation_count: 0, verified_count: 0, confidence_sum: 0.0 });

        let base_rate = if profile.observation_count > 0 {
            profile.verified_count as f64 / profile.observation_count as f64
        } else { 0.5 };

        let experience_level = match profile.observation_count {
            0..=9 => "unfamiliar",
            10..=29 => "novice",
            30..=99 => "intermediate",
            _ => "expert",
        }.to_string();

        // Anomaly detection
        let mut anomaly_count = 0;
        if profile.observation_count >= 5 {
            let avg_conf = profile.confidence_sum / profile.observation_count as f64;
            if (confidence - avg_conf).abs() > 0.15 {
                anomaly_count += 1;
            }
        }

        // Solver variance check
        if solver_results.len() >= 5 {
            let confs: Vec<f64> = solver_results.iter().map(|r| r.confidence).collect();
            let mean = confs.iter().sum::<f64>() / confs.len() as f64;
            let var = confs.iter().map(|c| (c - mean).powi(2)).sum::<f64>() / confs.len() as f64;
            if var < 0.001 {
                anomaly_count += 1;  // All identical = suspicious
            }
        }

        // Gut feeling
        let passed = solver_results.iter().filter(|r| r.passed).count() as f64;
        let total = solver_results.len().max(1) as f64;
        let solver_ratio = passed / total;
        let anomaly_penalty = anomaly_count as f64 * 0.1;
        let gut_feeling = (base_rate * 0.2 + confidence * 0.3 + solver_ratio * 0.3 + (0.7 - anomaly_penalty) * 0.2)
            .clamp(0.0, 1.0);

        // Adjustment
        let shrinkage = (base_rate - confidence) * 0.1;
        let anomaly_adj = -(anomaly_count as f64) * 0.02;
        let gut_adj = (gut_feeling - confidence) * 0.05;
        let adjustment = shrinkage + anomaly_adj + gut_adj;

        // Update profile
        profile.observation_count += 1;
        if verdict == "VERIFIED" { profile.verified_count += 1; }
        profile.confidence_sum += confidence;

        TacitResult {
            domain: domain.to_string(),
            experience_level,
            base_rate,
            gut_feeling,
            anomaly_count,
            adjustment,
        }
    }
}
