//! Temporal consistency solver — checks date/time logic

use super::Solver;
use crate::SolverResult;
use regex::Regex;

pub struct TemporalSolver;

impl Solver for TemporalSolver {
    fn name(&self) -> &str { "temporal_consistency" }

    fn verify(&self, claim: &str, _evidence: &[&str]) -> SolverResult {
        let years: Vec<i32> = extract_years(claim);

        // Check for future dates stated as past facts
        let current_year = 2026;
        let future_as_past = years.iter().any(|&y| y > current_year)
            && (claim.contains("した") || claim.contains("だった") 
                || claim.contains("was") || claim.contains("occurred")
                || claim.contains("happened"));

        if future_as_past {
            return SolverResult {
                solver_name: self.name().to_string(),
                passed: false,
                confidence: 0.9,
                reason: format!("Future year referenced as past event: {:?}", years),
            };
        }

        // Check for impossible date sequences (before > after)
        if years.len() >= 2 {
            for window in years.windows(2) {
                if let [a, b] = window {
                    // If claim implies a happened before b but a > b
                    if a > b && (claim.contains("before") || claim.contains("前に") || claim.contains("→")) {
                        return SolverResult {
                            solver_name: self.name().to_string(),
                            passed: false,
                            confidence: 0.85,
                            reason: format!("Temporal sequence violation: {} before {}", a, b),
                        };
                    }
                }
            }
        }

        SolverResult {
            solver_name: self.name().to_string(),
            passed: true,
            confidence: if years.is_empty() { 0.3 } else { 0.7 },
            reason: if years.is_empty() { 
                "No temporal claims detected".to_string() 
            } else { 
                format!("Temporal consistency OK for years: {:?}", years) 
            },
        }
    }
}

fn extract_years(text: &str) -> Vec<i32> {
    let re = Regex::new(r"\b(1[89]\d{2}|20[0-9]{2})\b").unwrap();
    re.find_iter(text)
        .filter_map(|m| m.as_str().parse::<i32>().ok())
        .collect()
}
