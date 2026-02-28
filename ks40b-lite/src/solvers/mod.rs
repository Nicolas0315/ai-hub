//! Deterministic solver chain — no LLM dependency
//!
//! Each solver implements a single verification axis.
//! Ported from Python KS29B→KS40b inheritance chain, flattened.

mod numerical;
mod contradiction;
mod temporal;
mod source_cross;
mod propositional;

use crate::SolverResult;

pub trait Solver: Send + Sync {
    fn name(&self) -> &str;
    fn verify(&self, claim: &str, evidence: &[&str]) -> SolverResult;
}

/// Build the full solver chain (deterministic only)
pub fn build_solver_chain() -> Vec<Box<dyn Solver>> {
    vec![
        Box::new(propositional::PropositionalSolver),
        Box::new(numerical::NumericalSolver),
        Box::new(contradiction::ContradictionSolver),
        Box::new(temporal::TemporalSolver),
        Box::new(source_cross::SourceCrossSolver),
    ]
}
