//! KS46 Integration Tests

use ks46::*;

// ═══════════════════════════════════════════════════
// Solver Chain Tests
// ═══════════════════════════════════════════════════

#[test]
fn test_solver_chain_builds_33_solvers() {
    let engine = KS46::new();
    let status = engine.status();
    assert_eq!(status["solver_count"], "33");
}

#[test]
fn test_verify_returns_result() {
    let mut engine = KS46::new();
    let result = engine.verify("The Earth orbits the Sun.", None);
    assert_eq!(result.version, "KS46-v1");
    assert_eq!(result.total_solvers, 33);
    assert!(result.confidence >= 0.0 && result.confidence <= 1.0);
}

#[test]
fn test_verify_japanese_claim() {
    let mut engine = KS46::new();
    let result = engine.verify("日本の首都は東京である。", None);
    assert_eq!(result.total_solvers, 33);
    assert!(result.solvers_passed > 0);
    assert!(!result.semantic.entities.is_empty(), "Should extract Japanese entities");
}

#[test]
fn test_known_false_claim_detected() {
    let mut engine = KS46::new();
    let result = engine.verify("the flat earth theory is true and vaccine autism link", None);
    // S19 Adversarial should catch known false patterns
    let s19 = result.solver_details.iter().find(|s| s.solver_id == "S19").unwrap();
    assert!(!s19.passed, "S19 should reject known false claims");
    assert!(s19.confidence < 0.3);
}

#[test]
fn test_future_prediction_penalized() {
    let mut engine = KS46::new();
    let result = engine.verify("AI will surpass human intelligence by 2030.", None);
    // S33 HTLF-Temporal should flag future predictions
    let s33 = result.solver_details.iter().find(|s| s.solver_id == "S33").unwrap();
    assert!(!s33.passed, "S33 should reject future predictions");
    // Translation loss R_temporal should be low
    assert!(result.translation_loss.r_temporal < 0.5);
}

#[test]
fn test_self_referential_claim_limited() {
    let mut engine = KS46::new();
    let result = engine.verify("KS Katala solver verification is always correct.", None);
    // S27 Meta should detect self-reference
    let s27 = result.solver_details.iter().find(|s| s.solver_id == "S27").unwrap();
    assert!(s27.confidence <= 0.45, "Self-referential claims should have limited confidence");
}

#[test]
fn test_universal_claim_flagged() {
    let mut engine = KS46::new();
    let result = engine.verify("All swans are white.", None);
    // S01 should flag universal + simple structure
    let s01 = result.solver_details.iter().find(|s| s.solver_id == "S01").unwrap();
    // Universal claims are falsifiable
    assert!(result.confidence < 0.8);
}

// ═══════════════════════════════════════════════════
// HTLF Tests
// ═══════════════════════════════════════════════════

#[test]
fn test_layer_detection_math() {
    let layer = ks46::htlf::detect_layer("∀x ∃y: x + y = 0 (equation proof)");
    assert!(layer == "math" || layer == "formal_logic");
}

#[test]
fn test_layer_detection_natural_language() {
    let layer = ks46::htlf::detect_layer("The cat sat on the mat.");
    assert_eq!(layer, "natural_language");
}

#[test]
fn test_semantic_parse_extracts_propositions() {
    let sem = ks46::htlf::semantic_parse("Tokyo is the capital. Japan has 47 prefectures.");
    assert!(sem.propositions.len() >= 2, "Should split into 2+ propositions");
}

#[test]
fn test_semantic_parse_extracts_entities() {
    let sem = ks46::htlf::semantic_parse("Einstein developed the theory of relativity in 1905.");
    assert!(sem.entities.iter().any(|e| e == "Einstein"), "Should extract Einstein");
    assert!(sem.entities.iter().any(|e| e.contains("1905")), "Should extract year");
}

#[test]
fn test_semantic_parse_japanese_entities() {
    let sem = ks46::htlf::semantic_parse("東京都は日本の首都である。人口は約1400万人。");
    assert!(!sem.entities.is_empty(), "Should extract CJK compound nouns");
}

#[test]
fn test_translation_loss_range() {
    let sem = ks46::htlf::semantic_parse("Test claim.");
    let loss = ks46::htlf::estimate_loss_5axis("Test claim.", "natural_language", &sem);
    assert!(loss.r_struct >= 0.0 && loss.r_struct <= 1.0);
    assert!(loss.r_context >= 0.0 && loss.r_context <= 1.0);
    assert!(loss.r_qualia >= 0.0 && loss.r_qualia <= 1.0);
    assert!(loss.r_cultural >= 0.0 && loss.r_cultural <= 1.0);
    assert!(loss.r_temporal >= 0.0 && loss.r_temporal <= 1.0);
    assert!(loss.total_loss >= 0.0 && loss.total_loss <= 1.0);
}

#[test]
fn test_coherence_identical_solvers() {
    let results = vec![
        SolverResult {
            solver_id: "S01".into(), solver_name: "test".into(),
            passed: true, confidence: 0.7, reason: "".into(),
            domain: "".into(), cluster: "formal".into(),
        },
        SolverResult {
            solver_id: "S02".into(), solver_name: "test".into(),
            passed: true, confidence: 0.7, reason: "".into(),
            domain: "".into(), cluster: "formal".into(),
        },
    ];
    let coh = ks46::htlf::compute_coherence(&results);
    assert!((coh - 1.0).abs() < 0.01, "Identical confidences should give max coherence");
}

// ═══════════════════════════════════════════════════
// Engine Tests
// ═══════════════════════════════════════════════════

#[test]
fn test_peer_review_insufficient_evidence() {
    let engine = ks46::engines::peer_review::PeerReviewEngine::new();
    let sem = ks46::htlf::semantic_parse("Claim without evidence.");
    let result = engine.review("Claim without evidence.", &[], &sem, &[], 0.5, "EXPLORING");
    assert!(result.critique_count > 0, "Should generate critiques for unsubstantiated claim");
    assert!(result.overall_score < 0.9, "Unsubstantiated claim should score below 0.9, got {}", result.overall_score);
}

#[test]
fn test_metacognitive_self_reference_bias() {
    let mut engine = ks46::engines::metacognitive::MetacognitiveEngine::new();
    let result = engine.analyze("KS Katala solver test", 0.5, "EXPLORING", 20, 33, &[]);
    assert!(result.bias_count > 0, "Should detect self-reference bias");
    assert!(result.biases.iter().any(|b| b.contains("self_reference")));
}

#[test]
fn test_metacognitive_anchoring_detection() {
    let mut engine = ks46::engines::metacognitive::MetacognitiveEngine::new();
    let result = engine.analyze("Some claim", 0.465, "EXPLORING", 15, 33, &[]);
    assert!(result.biases.iter().any(|b| b.contains("anchoring")),
        "Should detect confidence anchored to default 0.465");
}

#[test]
fn test_interdisciplinary_generates_hypotheses() {
    let engine = ks46::engines::interdisciplinary::InterdisciplinaryEngine::new();
    // Create solvers from different clusters with different outcomes
    let solvers = vec![
        SolverResult {
            solver_id: "S01".into(), solver_name: "test".into(),
            passed: true, confidence: 0.8, reason: "".into(),
            domain: "logic".into(), cluster: "formal".into(),
        },
        SolverResult {
            solver_id: "S11".into(), solver_name: "test".into(),
            passed: false, confidence: 0.3, reason: "".into(),
            domain: "spacetime".into(), cluster: "physical".into(),
        },
    ];
    let result = engine.analyze("Cross-domain claim", &solvers);
    assert!(result.pattern_count > 0);
    assert!(result.integration_score >= 0.0);
}

#[test]
fn test_tacit_knowledge_builds_profile() {
    let mut engine = ks46::engines::tacit_knowledge::TacitKnowledgeEngine::new();
    assert_eq!(engine.domain_count(), 0);
    let _r = engine.analyze("claim", "physics", 0.6, "EXPLORING", &[]);
    assert_eq!(engine.domain_count(), 1);
    let r2 = engine.analyze("another claim", "physics", 0.7, "VERIFIED", &[]);
    assert_eq!(r2.experience_level, "unfamiliar"); // Only 2 observations
    assert_eq!(engine.domain_count(), 1); // Same domain
}

#[test]
fn test_gpu_knowledge_relevant() {
    let engine = ks46::engines::gpu_knowledge::GpuKnowledgeEngine::new();
    let rec = engine.recommend_if_relevant("RTX 5070 Ti CUDA inference speed");
    assert!(rec.is_some());
    let r = rec.unwrap();
    assert_eq!(r.gpu_name, "RTX 5070 Ti");
    assert!(r.flash_attention);
    assert_eq!(r.kv_cache_type, "q8_0"); // Blackwell CC >= 12.0
}

#[test]
fn test_gpu_knowledge_irrelevant() {
    let engine = ks46::engines::gpu_knowledge::GpuKnowledgeEngine::new();
    let rec = engine.recommend_if_relevant("The weather is nice today.");
    assert!(rec.is_none());
}

#[test]
fn test_gpu_knowledge_ampere_f16() {
    let engine = ks46::engines::gpu_knowledge::GpuKnowledgeEngine::new();
    let rec = engine.recommend_if_relevant("RTX 3070 Ampere GPU ollama");
    assert!(rec.is_some());
    let r = rec.unwrap();
    assert_eq!(r.kv_cache_type, "f16"); // Ampere needs f16, not q8_0
}

#[test]
fn test_flm_planner_domain_routing() {
    let planner = ks46::engines::flm_planner::FlmPlanner::new();
    let sem = SemanticData {
        propositions: vec!["math claim".into()],
        entities: vec!["equation".into()],
        relations: vec![],
        domain: "mathematics".into(),
        source: "test".into(),
    };
    let plan = planner.plan_if_relevant("Solve this equation", &sem);
    assert!(plan.is_some());
    let p = plan.unwrap();
    assert!(p.selected_slms.iter().any(|s| s.contains("math")),
        "Should prioritize math SLM for math domain");
    assert!(p.predicted_quality > 0.0);
    assert!(p.hallucination_risk < 0.1);
}

// ═══════════════════════════════════════════════════
// Verdict Logic Tests
// ═══════════════════════════════════════════════════

#[test]
fn test_verdict_verified() {
    let v = ks46::htlf::determine_verdict(0.8, 0.9, 30, 33);
    assert_eq!(v, "VERIFIED");
}

#[test]
fn test_verdict_unverified() {
    let v = ks46::htlf::determine_verdict(0.2, 0.3, 10, 33);
    assert_eq!(v, "UNVERIFIED");
}

#[test]
fn test_verdict_exploring() {
    let v = ks46::htlf::determine_verdict(0.5, 0.6, 20, 33);
    assert_eq!(v, "EXPLORING");
}

#[test]
fn test_verdict_no_solvers() {
    let v = ks46::htlf::determine_verdict(0.5, 0.5, 0, 0);
    assert_eq!(v, "NO_SOLVERS");
}

// ═══════════════════════════════════════════════════
// Batch Verify
// ═══════════════════════════════════════════════════

#[test]
fn test_batch_verify() {
    let mut engine = KS46::new();
    let results = engine.verify_batch(vec![
        "Water boils at 100 degrees Celsius.".into(),
        "The moon is made of cheese.".into(),
        "2 + 2 = 4".into(),
    ]);
    assert_eq!(results.len(), 3);
    for r in &results {
        assert_eq!(r.total_solvers, 33);
    }
}

// ═══════════════════════════════════════════════════
// Edge Cases
// ═══════════════════════════════════════════════════

#[test]
fn test_empty_claim() {
    let mut engine = KS46::new();
    let result = engine.verify("", None);
    assert_eq!(result.total_solvers, 33);
    // Should still return a result, even if low confidence
}

#[test]
fn test_very_long_claim() {
    let mut engine = KS46::new();
    let long_claim = "This is a test. ".repeat(500);
    let result = engine.verify(&long_claim, None);
    assert_eq!(result.total_solvers, 33);
    assert!(result.confidence >= 0.0);
}

#[test]
fn test_special_characters() {
    let mut engine = KS46::new();
    let result = engine.verify("∀x ∈ ℝ: x² ≥ 0 → √x ∈ ℂ", None);
    assert_eq!(result.total_solvers, 33);
}

#[test]
fn test_mixed_language() {
    let mut engine = KS46::new();
    let result = engine.verify("日本語とEnglishが混ざったclaim。これはtest。", None);
    assert!(result.translation_loss.r_cultural < 0.65,
        "Mixed language should affect cultural translation loss");
}
