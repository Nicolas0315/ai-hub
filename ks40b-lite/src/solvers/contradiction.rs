//! Contradiction detection solver — finds conflicts between claim and evidence

use super::Solver;
use crate::SolverResult;

pub struct ContradictionSolver;

impl Solver for ContradictionSolver {
    fn name(&self) -> &str { "contradiction_detection" }

    fn verify(&self, claim: &str, evidence: &[&str]) -> SolverResult {
        if evidence.is_empty() {
            return SolverResult {
                solver_name: self.name().to_string(),
                passed: true,
                confidence: 0.3,
                reason: "No evidence to check against".to_string(),
            };
        }

        let claim_lower = claim.to_lowercase();
        let mut contradictions = Vec::new();

        // Negation patterns
        let negation_pairs = [
            ("is", "is not"), ("are", "are not"), ("was", "was not"),
            ("can", "cannot"), ("will", "will not"), ("has", "has not"),
            ("である", "ではない"), ("する", "しない"), ("ある", "ない"),
            ("増加", "減少"), ("上昇", "下降"), ("成功", "失敗"),
            ("increase", "decrease"), ("rise", "fall"), ("growth", "decline"),
        ];

        for ev in evidence {
            let ev_lower = ev.to_lowercase();
            for (pos, neg) in &negation_pairs {
                let claim_has_pos = claim_lower.contains(pos);
                let claim_has_neg = claim_lower.contains(neg);
                let ev_has_pos = ev_lower.contains(pos);
                let ev_has_neg = ev_lower.contains(neg);

                if (claim_has_pos && ev_has_neg) || (claim_has_neg && ev_has_pos) {
                    contradictions.push(format!("Claim '{}' vs evidence '{}' on {}/{}", 
                        &claim[..claim.len().min(40)], &ev[..ev.len().min(40)], pos, neg));
                }
            }
        }

        if contradictions.is_empty() {
            SolverResult {
                solver_name: self.name().to_string(),
                passed: true,
                confidence: 0.6,
                reason: "No contradictions found with evidence".to_string(),
            }
        } else {
            SolverResult {
                solver_name: self.name().to_string(),
                passed: false,
                confidence: 0.8,
                reason: format!("{} contradiction(s): {}", contradictions.len(), contradictions[0]),
            }
        }
    }
}
