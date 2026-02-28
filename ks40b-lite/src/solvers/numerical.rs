//! Numerical verification solver — checks mathematical claims and ranges

use super::Solver;
use crate::SolverResult;
use regex::Regex;

pub struct NumericalSolver;

impl Solver for NumericalSolver {
    fn name(&self) -> &str { "numerical_verification" }

    fn verify(&self, claim: &str, evidence: &[&str]) -> SolverResult {
        // Try to extract and verify arithmetic expressions
        let re = Regex::new(r"(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)").unwrap();

        if let Some(caps) = re.captures(claim) {
            let a: f64 = caps[1].parse().unwrap_or(0.0);
            let op = &caps[2];
            let b: f64 = caps[3].parse().unwrap_or(0.0);
            let claimed: f64 = caps[4].parse().unwrap_or(f64::NAN);

            let actual = match op {
                "+" => a + b,
                "-" => a - b,
                "*" => a * b,
                "/" => if b != 0.0 { a / b } else { f64::NAN },
                _ => f64::NAN,
            };

            if actual.is_nan() || claimed.is_nan() {
                return SolverResult {
                    solver_name: self.name().to_string(),
                    passed: false,
                    confidence: 0.8,
                    reason: "Invalid arithmetic expression".to_string(),
                };
            }

            let correct = (actual - claimed).abs() < 1e-9;
            return SolverResult {
                solver_name: self.name().to_string(),
                passed: correct,
                confidence: if correct { 1.0 } else { 0.0 },
                reason: format!("{} {} {} = {} (claimed: {})", a, op, b, actual, claimed),
            };
        }

        // Check for numerical claims against evidence
        if !evidence.is_empty() {
            let claim_numbers = extract_numbers(claim);
            let evidence_numbers: Vec<f64> = evidence.iter()
                .flat_map(|e| extract_numbers(e))
                .collect();

            if !claim_numbers.is_empty() && !evidence_numbers.is_empty() {
                // Check if claimed numbers appear in evidence
                let matched = claim_numbers.iter()
                    .filter(|cn| evidence_numbers.iter().any(|en: &f64| (en - *cn).abs() < 0.01))
                    .count();

                let match_rate = matched as f64 / claim_numbers.len() as f64;
                return SolverResult {
                    solver_name: self.name().to_string(),
                    passed: match_rate > 0.5,
                    confidence: match_rate,
                    reason: format!("{}/{} numbers verified against evidence", matched, claim_numbers.len()),
                };
            }
        }

        SolverResult {
            solver_name: self.name().to_string(),
            passed: true,
            confidence: 0.3,
            reason: "No numerical claims to verify".to_string(),
        }
    }
}

fn extract_numbers(text: &str) -> Vec<f64> {
    let re = Regex::new(r"\d+(?:\.\d+)?").unwrap();
    re.find_iter(text)
        .filter_map(|m| m.as_str().parse::<f64>().ok())
        .collect()
}
