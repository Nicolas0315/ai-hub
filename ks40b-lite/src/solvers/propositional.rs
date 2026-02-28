//! Propositional logic solver — checks for logical self-contradiction in the claim itself

use super::Solver;
use crate::SolverResult;
use regex::Regex;

pub struct PropositionalSolver;

impl Solver for PropositionalSolver {
    fn name(&self) -> &str { "propositional_logic" }

    fn verify(&self, claim: &str, _evidence: &[&str]) -> SolverResult {
        let lower = claim.to_lowercase();

        // Check for direct self-contradictions
        let contradictions = [
            // "X is Y and X is not Y" patterns
            (r"is\s+(\w+)\s+and\s+is\s+not\s+\1", "direct self-contradiction"),
            (r"both\s+true\s+and\s+false", "logical impossibility"),
            (r"always\s+.*\s+never", "temporal contradiction"),
            // Japanese patterns
            ("であり.*ではない", "自己矛盾"),
            ("かつ.*ではない", "論理矛盾"),
            ("常に.*決して.*ない", "時間的矛盾"),
            ("全て.*一つも.*ない", "全称・存在矛盾"),
        ];

        for (pattern, reason) in &contradictions {
            if let Ok(re) = Regex::new(pattern) {
                if re.is_match(&lower) {
                    return SolverResult {
                        solver_name: self.name().to_string(),
                        passed: false,
                        confidence: 0.95,
                        reason: format!("Self-contradiction detected: {}", reason),
                    };
                }
            }
        }

        // Check for tautologies (always true, trivially)
        let tautologies = [
            r"^(true|1\s*=\s*1|2\s*\+\s*2\s*=\s*4)$",
        ];
        for pattern in &tautologies {
            if let Ok(re) = Regex::new(pattern) {
                if re.is_match(claim.trim()) {
                    return SolverResult {
                        solver_name: self.name().to_string(),
                        passed: true,
                        confidence: 1.0,
                        reason: "Tautology".to_string(),
                    };
                }
            }
        }

        // Default: no determination from propositional logic alone
        SolverResult {
            solver_name: self.name().to_string(),
            passed: true,  // Absence of contradiction = pass
            confidence: 0.5,
            reason: "No propositional contradiction detected".to_string(),
        }
    }
}
