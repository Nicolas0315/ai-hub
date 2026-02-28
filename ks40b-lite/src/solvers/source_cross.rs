//! Source cross-verification solver — checks if claim is supported by multiple evidence sources

use super::Solver;
use crate::SolverResult;

pub struct SourceCrossSolver;

impl Solver for SourceCrossSolver {
    fn name(&self) -> &str { "source_cross_verification" }

    fn verify(&self, claim: &str, evidence: &[&str]) -> SolverResult {
        if evidence.is_empty() {
            return SolverResult {
                solver_name: self.name().to_string(),
                passed: true,
                confidence: 0.2,
                reason: "No evidence sources provided".to_string(),
            };
        }

        // Simple keyword overlap scoring
        let claim_words: Vec<&str> = claim.split_whitespace()
            .filter(|w| w.len() > 2)
            .collect();

        if claim_words.is_empty() {
            return SolverResult {
                solver_name: self.name().to_string(),
                passed: true,
                confidence: 0.3,
                reason: "Claim too short for cross-verification".to_string(),
            };
        }

        let mut supporting_sources = 0;
        for ev in evidence {
            let ev_lower = ev.to_lowercase();
            let overlap = claim_words.iter()
                .filter(|w| ev_lower.contains(&w.to_lowercase()))
                .count();
            let overlap_rate = overlap as f64 / claim_words.len() as f64;
            if overlap_rate > 0.3 {
                supporting_sources += 1;
            }
        }

        let support_rate = supporting_sources as f64 / evidence.len() as f64;
        SolverResult {
            solver_name: self.name().to_string(),
            passed: support_rate > 0.3,
            confidence: support_rate.min(1.0),
            reason: format!("{}/{} sources support the claim", supporting_sources, evidence.len()),
        }
    }
}
