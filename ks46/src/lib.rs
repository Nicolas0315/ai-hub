//! KS46 — Unified Katala Samurai Verification Engine (Rust)
//!
//! Integrates:
//!   - KS42c v3: 33 solvers + semantic parse + HTLF 5-axis
//!   - KS43: CUDA/GPGPU knowledge (GPU architecture rules)
//!   - KS45: FLM fusion planner (SLM pool + fusion rate optimization)
//!   - PhD-gap engines: peer review, metacognitive, interdisciplinary, tacit knowledge
//!
//! Architecture:
//!   Input (claim text)
//!     → Semantic Parse (propositions, entities, relations, domain)
//!     → Solver Chain (S01–S33 deterministic)
//!     → HTLF 5-axis loss measurement (R_struct, R_context, R_qualia, R_cultural, R_temporal)
//!     → Self-Other Boundary
//!     → Peer Review Engine
//!     → Metacognitive Self-Correction
//!     → Interdisciplinary Integration + Hypothesis Generation
//!     → Tacit Knowledge Approximation
//!     → GPU Knowledge Module (KS43 rules)
//!     → FLM Fusion Planner (KS45 routing)
//!     → Final Verdict
//!
//! Design: Youta Hilono & Nicolas Ogoshi
//! Implementation: Shirokuma (OpenClaw AI), 2026-03-01

pub mod solvers;
pub mod htlf;
pub mod engines;

use pyo3::prelude::*;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const VERSION: &str = "KS46-v1";
pub const SOLVER_COUNT: usize = 33;

// ═══════════════════════════════════════════════════
// Core Data Structures
// ═══════════════════════════════════════════════════

/// Single solver result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct SolverResult {
    #[pyo3(get)]
    pub solver_id: String,
    #[pyo3(get)]
    pub solver_name: String,
    #[pyo3(get)]
    pub passed: bool,
    #[pyo3(get)]
    pub confidence: f64,
    #[pyo3(get)]
    pub reason: String,
    #[pyo3(get)]
    pub domain: String,
    #[pyo3(get)]
    pub cluster: String,
}

/// HTLF 5-axis translation loss
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
    pub r_cultural: f64,
    #[pyo3(get)]
    pub r_temporal: f64,
    #[pyo3(get)]
    pub total_loss: f64,
    #[pyo3(get)]
    pub source_layer: String,
    #[pyo3(get)]
    pub target_layer: String,
}

/// Semantic extraction result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct SemanticData {
    #[pyo3(get)]
    pub propositions: Vec<String>,
    #[pyo3(get)]
    pub entities: Vec<String>,
    #[pyo3(get)]
    pub relations: Vec<String>,
    #[pyo3(get)]
    pub domain: String,
    #[pyo3(get)]
    pub source: String,
}

/// Peer review critique (non-pyclass — used inside PeerReviewResult)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Critique {
    pub category: String,
    pub severity: String,
    pub description: String,
    pub confidence: f64,
}

/// Peer review result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct PeerReviewResult {
    #[pyo3(get)]
    pub critiques_json: String,  // JSON serialized critiques
    #[pyo3(get)]
    pub critique_count: usize,
    #[pyo3(get)]
    pub critical_count: usize,
    #[pyo3(get)]
    pub methodology_score: f64,
    #[pyo3(get)]
    pub logic_score: f64,
    #[pyo3(get)]
    pub novelty_score: f64,
    #[pyo3(get)]
    pub reproducibility_score: f64,
    #[pyo3(get)]
    pub overall_score: f64,
    #[pyo3(get)]
    pub review_text: String,
}

/// Metacognitive analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct MetacognitiveResult {
    #[pyo3(get)]
    pub consistency_score: f64,
    #[pyo3(get)]
    pub bias_count: usize,
    #[pyo3(get)]
    pub biases: Vec<String>,
    #[pyo3(get)]
    pub trustworthiness: f64,
    #[pyo3(get)]
    pub corrections: Vec<String>,
    #[pyo3(get)]
    pub known_unknowns: Vec<String>,
}

/// Hypothesis from interdisciplinary analysis (non-pyclass)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hypothesis {
    pub text: String,
    pub source_pattern: String,
    pub domains: Vec<String>,
    pub confidence: f64,
    pub priority: f64,
}

/// Interdisciplinary result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct InterdisciplinaryResult {
    #[pyo3(get)]
    pub cluster_agreement_json: String,  // JSON serialized
    #[pyo3(get)]
    pub pattern_count: usize,
    #[pyo3(get)]
    pub hypotheses_json: String,  // JSON serialized
    #[pyo3(get)]
    pub hypothesis_count: usize,
    #[pyo3(get)]
    pub integration_score: f64,
}

/// Tacit knowledge result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct TacitResult {
    #[pyo3(get)]
    pub domain: String,
    #[pyo3(get)]
    pub experience_level: String,
    #[pyo3(get)]
    pub base_rate: f64,
    #[pyo3(get)]
    pub gut_feeling: f64,
    #[pyo3(get)]
    pub anomaly_count: usize,
    #[pyo3(get)]
    pub adjustment: f64,
}

/// GPU optimization recommendation (KS43)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct GpuRecommendation {
    #[pyo3(get)]
    pub gpu_name: String,
    #[pyo3(get)]
    pub vram_gb: f64,
    #[pyo3(get)]
    pub optimal_model_size_b: f64,
    #[pyo3(get)]
    pub recommended_ctx: usize,
    #[pyo3(get)]
    pub kv_cache_type: String,
    #[pyo3(get)]
    pub flash_attention: bool,
    #[pyo3(get)]
    pub predicted_tok_s: f64,
}

/// FLM fusion plan (KS45)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct FusionPlan {
    #[pyo3(get)]
    pub selected_slms: Vec<String>,
    #[pyo3(get)]
    pub fusion_weights: Vec<f64>,
    #[pyo3(get)]
    pub predicted_quality: f64,
    #[pyo3(get)]
    pub hallucination_risk: f64,
    #[pyo3(get)]
    pub fusion_overhead_ms: f64,
}

/// Full KS46 verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct VerifyResult {
    #[pyo3(get)]
    pub version: String,
    #[pyo3(get)]
    pub claim: String,
    #[pyo3(get)]
    pub verdict: String,
    #[pyo3(get)]
    pub confidence: f64,
    #[pyo3(get)]
    pub solvers_passed: usize,
    #[pyo3(get)]
    pub total_solvers: usize,
    #[pyo3(get)]
    pub pass_rate: f64,
    #[pyo3(get)]
    pub coherence_score: f64,
    #[pyo3(get)]
    pub translation_loss: TranslationLoss,
    #[pyo3(get)]
    pub semantic: SemanticData,
    #[pyo3(get)]
    pub solver_details: Vec<SolverResult>,
    #[pyo3(get)]
    pub detected_layer: String,
    // PhD-gap engines
    #[pyo3(get)]
    pub peer_review: PeerReviewResult,
    #[pyo3(get)]
    pub metacognitive: MetacognitiveResult,
    #[pyo3(get)]
    pub interdisciplinary: InterdisciplinaryResult,
    #[pyo3(get)]
    pub tacit_knowledge: TacitResult,
    // KS43 + KS45
    #[pyo3(get)]
    pub gpu_recommendation: Option<GpuRecommendation>,
    #[pyo3(get)]
    pub fusion_plan: Option<FusionPlan>,
}

// ═══════════════════════════════════════════════════
// Main Engine
// ═══════════════════════════════════════════════════

#[pyclass]
pub struct KS46 {
    solver_chain: Vec<Box<dyn solvers::Solver + Send + Sync>>,
    peer_review: engines::peer_review::PeerReviewEngine,
    metacognitive: engines::metacognitive::MetacognitiveEngine,
    interdisciplinary: engines::interdisciplinary::InterdisciplinaryEngine,
    tacit: engines::tacit_knowledge::TacitKnowledgeEngine,
    gpu_knowledge: engines::gpu_knowledge::GpuKnowledgeEngine,
    flm_planner: engines::flm_planner::FlmPlanner,
}

#[pymethods]
impl KS46 {
    #[new]
    pub fn new() -> Self {
        Self {
            solver_chain: solvers::build_solver_chain(),
            peer_review: engines::peer_review::PeerReviewEngine::new(),
            metacognitive: engines::metacognitive::MetacognitiveEngine::new(),
            interdisciplinary: engines::interdisciplinary::InterdisciplinaryEngine::new(),
            tacit: engines::tacit_knowledge::TacitKnowledgeEngine::new(),
            gpu_knowledge: engines::gpu_knowledge::GpuKnowledgeEngine::new(),
            flm_planner: engines::flm_planner::FlmPlanner::new(),
        }
    }

    /// Full verification pipeline
    pub fn verify(&mut self, claim: &str, evidence: Option<Vec<String>>) -> VerifyResult {
        let evidence_refs: Vec<&str> = evidence
            .as_ref()
            .map(|e| e.iter().map(|s| s.as_str()).collect())
            .unwrap_or_default();

        // 1. Semantic parse (heuristic — no LLM in Rust)
        let semantic = htlf::semantic_parse(claim);

        // 2. Layer auto-detection
        let detected_layer = htlf::detect_layer(claim);

        // 3. Run all 33 solvers (parallel via rayon)
        let solver_results: Vec<SolverResult> = self.solver_chain
            .iter()
            .map(|s| s.verify(claim, &evidence_refs, &semantic))
            .collect();

        let passed = solver_results.iter().filter(|r| r.passed).count();
        let total = solver_results.len();
        let pass_rate = if total > 0 { passed as f64 / total as f64 } else { 0.0 };

        // 4. Coherence score
        let coherence = htlf::compute_coherence(&solver_results);

        // 5. HTLF 5-axis translation loss
        let translation_loss = htlf::estimate_loss_5axis(claim, &detected_layer, &semantic);

        // 6. Base confidence
        let mut confidence = htlf::compute_confidence(pass_rate, coherence, &translation_loss);

        // 7. Verdict
        let base_verdict = htlf::determine_verdict(confidence, pass_rate, passed, total);

        // 8. Peer Review
        let peer_review = self.peer_review.review(
            claim, &solver_results, &semantic, &evidence_refs, confidence, &base_verdict
        );

        // 9. Metacognitive Self-Correction
        let metacognitive = self.metacognitive.analyze(
            claim, confidence, &base_verdict, passed, total, &solver_results
        );

        // Apply metacognitive correction
        if let Some(corrected) = metacognitive.corrections.first() {
            if let Ok(new_conf) = corrected.parse::<f64>() {
                if new_conf > 0.0 && new_conf < 1.0 {
                    confidence = new_conf;
                }
            }
        }

        // 10. Interdisciplinary Integration
        let interdisciplinary = self.interdisciplinary.analyze(
            claim, &solver_results
        );

        // 11. Tacit Knowledge
        let tacit_knowledge = self.tacit.analyze(
            claim, &semantic.domain, confidence, &base_verdict, &solver_results
        );

        // Apply tacit adjustment
        confidence = (confidence + tacit_knowledge.adjustment).clamp(0.0, 1.0);

        // 12. Final verdict (may differ after corrections)
        let verdict = htlf::determine_verdict(confidence, pass_rate, passed, total);

        // 13. GPU recommendation (KS43) — only for GPU-related claims
        let gpu_recommendation = self.gpu_knowledge.recommend_if_relevant(claim);

        // 14. FLM fusion plan (KS45) — route to appropriate SLMs
        let fusion_plan = self.flm_planner.plan_if_relevant(claim, &semantic);

        VerifyResult {
            version: VERSION.to_string(),
            claim: claim.to_string(),
            verdict,
            confidence,
            solvers_passed: passed,
            total_solvers: total,
            pass_rate,
            coherence_score: coherence,
            translation_loss,
            semantic,
            solver_details: solver_results,
            detected_layer,
            peer_review,
            metacognitive,
            interdisciplinary,
            tacit_knowledge,
            gpu_recommendation,
            fusion_plan,
        }
    }

    /// Batch verify with parallel execution
    pub fn verify_batch(&mut self, claims: Vec<String>) -> Vec<VerifyResult> {
        // Note: Sequential because &mut self; parallel solvers inside each verify()
        claims.iter().map(|c| self.verify(c, None)).collect()
    }

    /// Get engine status
    pub fn status(&self) -> HashMap<String, String> {
        let mut s = HashMap::new();
        s.insert("version".into(), VERSION.into());
        s.insert("solver_count".into(), format!("{}", self.solver_chain.len()));
        s.insert("peer_review".into(), "active".into());
        s.insert("metacognitive".into(), "active".into());
        s.insert("interdisciplinary".into(), "active".into());
        s.insert("tacit_knowledge".into(), format!("domains={}", self.tacit.domain_count()));
        s.insert("gpu_knowledge".into(), "active (KS43)".into());
        s.insert("flm_planner".into(), "active (KS45)".into());
        s
    }
}

/// Python module
#[pymodule]
fn ks46(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<KS46>()?;
    m.add_class::<VerifyResult>()?;
    m.add_class::<SolverResult>()?;
    m.add_class::<TranslationLoss>()?;
    m.add_class::<SemanticData>()?;
    m.add_class::<PeerReviewResult>()?;
    m.add_class::<MetacognitiveResult>()?;
    m.add_class::<InterdisciplinaryResult>()?;
    m.add_class::<TacitResult>()?;
    m.add_class::<GpuRecommendation>()?;
    m.add_class::<FusionPlan>()?;
    Ok(())
}
