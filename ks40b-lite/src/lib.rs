//! KS40b-lite: Standalone verification engine for OpenClaw self-maintenance
//!
//! Design: Youta Hilono + Shirokuma (OpenClaw AI)
//! Architecture: Rust core (deterministic solvers) + Python/LLM bridge (reasoning solvers)
//!
//! Rust handles: formal logic, numerical verification, contradiction detection,
//!               coherence network, HTLF 3-axis computation, layer auto-detection
//! LLM handles:  semantic reasoning, context judgment, R_qualia evaluation, final verdict

mod solvers;
mod htlf;
mod reason_space;

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

/// Result from a single solver
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct SolverResult {
    #[pyo3(get)]
    pub solver_name: String,
    #[pyo3(get)]
    pub passed: bool,
    #[pyo3(get)]
    pub confidence: f64,
    #[pyo3(get)]
    pub reason: String,
}

/// Result from the full verification pipeline
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct VerifyResult {
    #[pyo3(get)]
    pub claim: String,
    #[pyo3(get)]
    pub solvers_passed: usize,
    #[pyo3(get)]
    pub total_solvers: usize,
    #[pyo3(get)]
    pub pass_rate: f64,
    #[pyo3(get)]
    pub coherence_score: f64,
    #[pyo3(get)]
    pub needs_llm_review: bool,
    #[pyo3(get)]
    pub translation_loss: TranslationLoss,
    #[pyo3(get)]
    pub solver_details: Vec<SolverResult>,
    #[pyo3(get)]
    pub detected_layer: String,
}

/// HTLF translation loss measurement
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct TranslationLoss {
    #[pyo3(get)]
    pub r_struct: f64,
    #[pyo3(get)]
    pub r_context: f64,
    #[pyo3(get)]
    pub r_qualia: f64,
    #[pyo3(get)]
    pub total_loss: f64,
    #[pyo3(get)]
    pub source_layer: String,
    #[pyo3(get)]
    pub target_layer: String,
}

/// Main verification engine
#[pyclass]
pub struct KS40bLite {
    solvers: Vec<Box<dyn solvers::Solver>>,
}

#[pymethods]
impl KS40bLite {
    #[new]
    pub fn new() -> Self {
        Self {
            solvers: solvers::build_solver_chain(),
        }
    }

    /// Fast deterministic scan — returns results + flag for LLM review
    pub fn verify(&self, claim: &str, evidence: Option<Vec<String>>, source_text: Option<&str>) -> VerifyResult {
        let evidence_refs: Vec<&str> = evidence
            .as_ref()
            .map(|e| e.iter().map(|s| s.as_str()).collect())
            .unwrap_or_default();

        // 1. Layer auto-detection
        let target_layer = htlf::detect_layer(claim);
        let source_layer = source_text.map(htlf::detect_layer).unwrap_or_else(|| "natural_language".to_string());

        // 2. Run all deterministic solvers
        let mut results: Vec<SolverResult> = Vec::new();
        for solver in &self.solvers {
            results.push(solver.verify(claim, &evidence_refs));
        }

        let passed = results.iter().filter(|r| r.passed).count();
        let total = results.len();
        let pass_rate = if total > 0 { passed as f64 / total as f64 } else { 0.0 };

        // 3. Coherence check
        let coherence = reason_space::compute_coherence(&results);

        // 4. HTLF translation loss
        let translation_loss = htlf::estimate_loss(&source_layer, &target_layer);

        // 5. Determine if LLM review is needed
        // Ambiguous zone: not clearly passing or failing
        let needs_llm = pass_rate > 0.3 && pass_rate < 0.8;

        VerifyResult {
            claim: claim.to_string(),
            solvers_passed: passed,
            total_solvers: total,
            pass_rate,
            coherence_score: coherence,
            needs_llm_review: needs_llm,
            translation_loss,
            solver_details: results,
            detected_layer: target_layer,
        }
    }

    /// Batch verify multiple claims
    pub fn verify_batch(&self, claims: Vec<String>) -> Vec<VerifyResult> {
        claims.iter().map(|c| self.verify(c, None, None)).collect()
    }
}

/// Python module
#[pymodule]
fn ks40b_lite(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<KS40bLite>()?;
    m.add_class::<VerifyResult>()?;
    m.add_class::<SolverResult>()?;
    m.add_class::<TranslationLoss>()?;
    Ok(())
}
