//! Metacognitive Self-Correction — recursive verification of verification results

use crate::{SolverResult, MetacognitiveResult};

const ANCHORING_DEFAULT: f64 = 0.465;
const ANCHORING_THRESHOLD: f64 = 0.05;

pub struct MetacognitiveEngine {
    history: Vec<(String, f64)>,  // (verdict, confidence) history
}

impl MetacognitiveEngine {
    pub fn new() -> Self { Self { history: Vec::new() } }

    pub fn analyze(
        &mut self,
        claim: &str,
        confidence: f64,
        verdict: &str,
        passed: usize,
        total: usize,
        _solver_results: &[SolverResult],
    ) -> MetacognitiveResult {
        let mut biases = Vec::new();
        let mut corrections = Vec::new();
        let mut known_unknowns = Vec::new();

        // 1. Consistency check
        let pass_rate = if total > 0 { passed as f64 / total as f64 } else { 0.0 };
        let mut consistency = 1.0f64;
        if verdict == "VERIFIED" && confidence < 0.5 { consistency -= 0.3; }
        if verdict == "UNVERIFIED" && confidence > 0.7 { consistency -= 0.2; }
        if total > 0 {
            let expected = pass_rate;
            if (confidence - expected).abs() > 0.3 { consistency -= 0.2; }
        }
        consistency = consistency.max(0.0);

        // 2. Self-reference bias
        let self_ref_kw = ["KS", "Katala", "しろくま", "ソルバー", "検証", "solver"];
        let self_count = self_ref_kw.iter().filter(|kw| claim.contains(*kw)).count();
        if self_count >= 2 {
            biases.push(format!("self_reference: {}個のKS関連語 — ゲーデル的限界", self_count));
        }

        // 3. Anchoring bias
        if (confidence - ANCHORING_DEFAULT).abs() < ANCHORING_THRESHOLD {
            biases.push(format!("anchoring: conf={:.3}がデフォルト値{:.3}に近い", confidence, ANCHORING_DEFAULT));
        }

        // 4. Confirmation bias (history pattern)
        if self.history.len() >= 3 {
            let recent: Vec<&str> = self.history.iter().rev().take(5).map(|(v, _)| v.as_str()).collect();
            if recent.iter().all(|v| *v == recent[0]) {
                biases.push(format!("confirmation: 直近{}件がすべて{}", recent.len(), recent[0]));
            }
        }

        // 5. Known unknowns
        known_unknowns.push("外部データベースとの照合が未実施".into());
        known_unknowns.push("ソルバー判定理由の自然言語説明が未生成".into());
        if total > 0 && (total - passed) > 0 {
            known_unknowns.push(format!("{}個のソルバーが不一致 — 原因未特定", total - passed));
        }

        // 6. Corrections
        let mut trustworthiness = consistency;
        if !biases.is_empty() {
            let bias_penalty = biases.len() as f64 * 0.1;
            trustworthiness = (trustworthiness - bias_penalty).max(0.0);

            if consistency < 0.7 && confidence > 0.5 {
                let corrected = confidence * consistency;
                corrections.push(format!("{:.4}", corrected.max(0.2)));
            }
        }
        trustworthiness = (trustworthiness - known_unknowns.len() as f64 * 0.05).max(0.0);

        // Record
        self.history.push((verdict.to_string(), confidence));
        if self.history.len() > 100 { self.history.drain(..50); }

        MetacognitiveResult {
            consistency_score: consistency,
            bias_count: biases.len(),
            biases,
            trustworthiness,
            corrections,
            known_unknowns,
        }
    }
}
