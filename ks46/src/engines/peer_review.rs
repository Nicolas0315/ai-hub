//! Peer Review Engine — PhD-level critique generation

use crate::{SolverResult, SemanticData, Critique, PeerReviewResult};

const MIN_EVIDENCE: usize = 3;
const WEAK_AGREEMENT: f64 = 0.6;
const LOW_CONFIDENCE: f64 = 0.4;

pub struct PeerReviewEngine;

impl PeerReviewEngine {
    pub fn new() -> Self { Self }

    pub fn review(
        &self,
        claim: &str,
        solver_results: &[SolverResult],
        semantic: &SemanticData,
        evidence: &[&str],
        confidence: f64,
        verdict: &str,
    ) -> PeerReviewResult {
        let mut critiques = Vec::new();

        // Methodology
        if evidence.len() < MIN_EVIDENCE {
            critiques.push(Critique {
                category: "methodology".into(),
                severity: "major".into(),
                description: format!("エビデンス不足: {}件のみ。最低{}件の独立した証拠源が必要",
                    evidence.len(), MIN_EVIDENCE),
                confidence: 0.8,
            });
        }

        let has_numbers = claim.chars().any(|c| c.is_ascii_digit());
        if !has_numbers {
            critiques.push(Critique {
                category: "methodology".into(),
                severity: "major".into(),
                description: "定量的根拠の欠如: 数値・統計が含まれていない".into(),
                confidence: 0.7,
            });
        }

        let passed = solver_results.iter().filter(|r| r.passed).count();
        let total = solver_results.len();
        let agreement = if total > 0 { passed as f64 / total as f64 } else { 0.0 };
        if agreement < WEAK_AGREEMENT && total > 0 {
            critiques.push(Critique {
                category: "methodology".into(),
                severity: "critical".into(),
                description: format!("ソルバー合意率が低い ({}/{} = {:.0}%)",
                    passed, total, agreement * 100.0),
                confidence: 0.85,
            });
        }

        if confidence < LOW_CONFIDENCE {
            critiques.push(Critique {
                category: "methodology".into(),
                severity: "critical".into(),
                description: format!("検証信頼度が低い (conf={:.3})", confidence),
                confidence: 0.9,
            });
        }

        // Logic
        let causal_markers = ["ため", "よって", "したがって", "because", "therefore"];
        let has_causal = causal_markers.iter().any(|m| claim.contains(m));
        if has_causal && !semantic.relations.iter().any(|r| r.contains("causal") || r.contains("implies")) {
            critiques.push(Critique {
                category: "logic".into(),
                severity: "major".into(),
                description: "因果関係の主張があるが因果メカニズムが未提示".into(),
                confidence: 0.75,
            });
        }

        let universal = ["すべて", "全て", "必ず", "常に", "all", "every", "always", "never"];
        if universal.iter().any(|m| claim.contains(m)) {
            critiques.push(Critique {
                category: "logic".into(),
                severity: "major".into(),
                description: "全称命題: 単一の反例で反証可能".into(),
                confidence: 0.7,
            });
        }

        // Novelty
        let known = [("地球は太陽", "既知の天文学的事実"), ("水は100度", "基礎物理学"),
            ("E=mc", "質量エネルギー等価"), ("地球は平ら", "反証済み")];
        for (pat, desc) in known {
            if claim.contains(pat) {
                critiques.push(Critique {
                    category: "novelty".into(),
                    severity: "minor".into(),
                    description: format!("既知: {}", desc),
                    confidence: 0.85,
                });
                break;
            }
        }

        // Reproducibility
        let method_kw = ["方法", "手順", "実験", "method", "procedure", "experiment", "実装"];
        let has_method = method_kw.iter().any(|m| claim.contains(m))
            || evidence.iter().any(|e| method_kw.iter().any(|m| e.contains(m)));
        if !has_method {
            critiques.push(Critique {
                category: "reproducibility".into(),
                severity: "major".into(),
                description: "方法・手順の記述が不足。再現に必要な情報が必要".into(),
                confidence: 0.65,
            });
        }

        // Scores
        let method_score = category_score(&critiques, "methodology");
        let logic_score = category_score(&critiques, "logic");
        let novelty_score = category_score(&critiques, "novelty");
        let repro_score = category_score(&critiques, "reproducibility");
        let overall = method_score * 0.3 + logic_score * 0.3 + novelty_score * 0.2 + repro_score * 0.2;

        let decision = if overall >= 0.7 { "Accept with minor revisions" }
            else if overall >= 0.5 { "Major revision required" }
            else if overall >= 0.3 { "Reject and resubmit" }
            else { "Reject" };

        let critical_count = critiques.iter().filter(|c| c.severity == "critical").count();
        let critique_count = critiques.len();
        let critiques_json = serde_json::to_string(&critiques).unwrap_or_default();

        PeerReviewResult {
            critiques_json,
            critique_count,
            critical_count,
            methodology_score: method_score,
            logic_score,
            novelty_score,
            reproducibility_score: repro_score,
            overall_score: overall,
            review_text: format!("Decision: {} (score={:.3})", decision, overall),
        }
    }
}

fn category_score(critiques: &[Critique], category: &str) -> f64 {
    let cat_critiques: Vec<&Critique> = critiques.iter()
        .filter(|c| c.category == category && c.severity != "suggestion")
        .collect();
    if cat_critiques.is_empty() { return 0.8; }
    let penalty: f64 = cat_critiques.iter().map(|c| {
        let sev = match c.severity.as_str() {
            "critical" => 0.30,
            "major" => 0.15,
            "minor" => 0.05,
            _ => 0.0,
        };
        sev * c.confidence
    }).sum();
    (1.0 - penalty).max(0.0).min(1.0)
}
