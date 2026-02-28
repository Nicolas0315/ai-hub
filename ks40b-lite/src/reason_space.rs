//! Reason Space — inter-solver coherence network
//! 
//! Checks whether solver results are mutually consistent.
//! Ported from Python reason_space.py (Sellars/Brandom space-of-reasons model).

use crate::SolverResult;

/// Compute coherence score from solver results
pub fn compute_coherence(results: &[SolverResult]) -> f64 {
    if results.len() < 2 {
        return 1.0;
    }

    let total = results.len();
    let passed = results.iter().filter(|r| r.passed).count();
    let failed = total - passed;

    // Conflict detection: high-confidence disagreements
    let high_conf_passed = results.iter()
        .filter(|r| r.passed && r.confidence > 0.7)
        .count();
    let high_conf_failed = results.iter()
        .filter(|r| !r.passed && r.confidence > 0.7)
        .count();

    // If strong solvers disagree with each other, coherence drops
    let conflict_penalty = if high_conf_passed > 0 && high_conf_failed > 0 {
        let conflict_ratio = high_conf_failed.min(high_conf_passed) as f64
            / (high_conf_passed + high_conf_failed) as f64;
        conflict_ratio * 0.5
    } else {
        0.0
    };

    // Low-confidence isolation penalty
    let low_conf = results.iter().filter(|r| r.confidence < 0.3).count();
    let isolation_penalty = (low_conf as f64 / total as f64) * 0.2;

    // Base coherence from agreement rate
    let agreement = if passed >= failed { passed } else { failed };
    let base_coherence = agreement as f64 / total as f64;

    (base_coherence - conflict_penalty - isolation_penalty).clamp(0.0, 1.0)
}
