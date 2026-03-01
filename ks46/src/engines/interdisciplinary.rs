//! Interdisciplinary Integration — cross-solver reasoning + hypothesis generation

use crate::{SolverResult, Hypothesis, InterdisciplinaryResult};
use std::collections::HashMap;

pub struct InterdisciplinaryEngine;

impl InterdisciplinaryEngine {
    pub fn new() -> Self { Self }

    pub fn analyze(&self, claim: &str, solver_results: &[SolverResult]) -> InterdisciplinaryResult {
        // Group by cluster
        let mut clusters: HashMap<String, Vec<&SolverResult>> = HashMap::new();
        for sr in solver_results {
            clusters.entry(sr.cluster.clone()).or_default().push(sr);
        }

        // Cluster agreement rates
        let mut cluster_agreement: HashMap<String, f64> = HashMap::new();
        for (cluster, results) in &clusters {
            let passed = results.iter().filter(|r| r.passed).count() as f64;
            let total = results.len() as f64;
            let rate = if total > 0.0 { passed / total } else { 0.0 };
            cluster_agreement.insert(cluster.clone(), (rate * 2.0 - 1.0).abs());
        }

        // Cross-cluster patterns
        let cluster_names: Vec<String> = clusters.keys().cloned().collect();
        let mut pattern_count = 0usize;
        let mut hypotheses = Vec::new();

        for i in 0..cluster_names.len() {
            for j in (i+1)..cluster_names.len() {
                let cl_a = &cluster_names[i];
                let cl_b = &cluster_names[j];
                let results_a = &clusters[cl_a];
                let results_b = &clusters[cl_b];

                let rate_a = results_a.iter().filter(|r| r.passed).count() as f64
                    / results_a.len().max(1) as f64;
                let rate_b = results_b.iter().filter(|r| r.passed).count() as f64
                    / results_b.len().max(1) as f64;
                let diff = (rate_a - rate_b).abs();

                pattern_count += 1;

                // Disagreement → hypothesis
                if diff > 0.3 {
                    let short_claim = if claim.len() > 50 { &claim[..50] } else { claim };
                    hypotheses.push(Hypothesis {
                        text: format!("「{}」に対して{}と{}が対立する原因は、前提条件のドメイン依存性にある",
                            short_claim, cl_a, cl_b),
                        source_pattern: format!("disagreement:{}×{}", cl_a, cl_b),
                        domains: vec![cl_a.clone(), cl_b.clone()],
                        confidence: diff * 0.6,
                        priority: diff * 0.6 * 0.3 + 0.7 * 0.3 + 0.8 * 0.4,
                    });
                }

                // Strong agreement → robustness
                if diff < 0.15 && rate_a > 0.6 {
                    hypotheses.push(Hypothesis {
                        text: format!("{}と{}の合意は構造的妥当性を示唆", cl_a, cl_b),
                        source_pattern: format!("agreement:{}×{}", cl_a, cl_b),
                        domains: vec![cl_a.clone(), cl_b.clone()],
                        confidence: (1.0 - diff) * 0.7,
                        priority: (1.0 - diff) * 0.3,
                    });
                }
            }
        }

        hypotheses.sort_by(|a, b| b.priority.partial_cmp(&a.priority).unwrap_or(std::cmp::Ordering::Equal));
        hypotheses.truncate(10);

        // Integration score
        let diversity = clusters.len() as f64 / 6.0;  // 6 possible clusters
        let pattern_score = (pattern_count as f64 * 0.1).min(1.0);
        let hyp_score = if hypotheses.is_empty() { 0.0 }
            else { hypotheses.iter().map(|h| h.priority).sum::<f64>() / hypotheses.len() as f64 };
        let integration_score = (diversity * 0.3 + pattern_score * 0.3 + hyp_score * 0.4).min(1.0);

        let hypothesis_count = hypotheses.len();
        InterdisciplinaryResult {
            cluster_agreement_json: serde_json::to_string(&cluster_agreement).unwrap_or_default(),
            pattern_count,
            hypotheses_json: serde_json::to_string(&hypotheses).unwrap_or_default(),
            hypothesis_count,
            integration_score,
        }
    }
}
