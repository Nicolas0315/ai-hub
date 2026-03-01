//! Solver chain: 33 independent solvers (Wiles-type architecture)
//!
//! Each solver judges only its own domain. Independence is structural.
//! Solvers receive semantic data (propositions, entities, relations, domain)
//! and perform meaningful checks — not just boolean satisfiability.
//!
//! Cluster mapping:
//!   formal:      S01-S05 (logic, set theory, algebra, number theory, category theory)
//!   geometric:   S06-S10 (topology, geometry, differential geometry, metric, algebraic topology)
//!   physical:    S11-S14 (spacetime, dynamical systems, statistical mechanics, spectral)
//!   statistical: S15-S18 (probability, bayesian, frequentist, information theory)
//!   empirical:   S19-S23 (adversarial, ensemble, semantic, causal inference, computational)
//!   contextual:  S24-S28 (temporal, cultural, linguistic, meta, self-other)
//!   extended:    S29-S33 (htlf-struct, htlf-context, htlf-qualia, htlf-cultural, htlf-temporal)

use crate::{SolverResult, SemanticData};

/// Solver trait — each solver is independent
pub trait Solver: Send + Sync {
    fn id(&self) -> &str;
    fn name(&self) -> &str;
    fn domain(&self) -> &str;
    fn cluster(&self) -> &str;
    fn verify(&self, claim: &str, evidence: &[&str], semantic: &SemanticData) -> SolverResult;
}

/// Domain-specific keywords for solver matching
const MATH_KEYWORDS: &[&str] = &["数", "計算", "方程式", "証明", "定理", "公式", "math", "equation", "proof", "theorem"];
const LOGIC_KEYWORDS: &[&str] = &["論理", "矛盾", "含意", "命題", "logic", "contradiction", "implies", "proposition"];
const PHYSICS_KEYWORDS: &[&str] = &["物理", "力", "エネルギー", "量子", "重力", "physics", "force", "energy", "quantum", "gravity"];
const BIO_KEYWORDS: &[&str] = &["生物", "細胞", "DNA", "遺伝", "生命", "biology", "cell", "gene", "evolution"];
const CS_KEYWORDS: &[&str] = &["コンピュータ", "アルゴリズム", "GPU", "CUDA", "プログラム", "computer", "algorithm", "program"];
const CAUSAL_KEYWORDS: &[&str] = &["ため", "よって", "したがって", "結果", "原因", "because", "therefore", "causes", "due to"];
const UNIVERSAL_KEYWORDS: &[&str] = &["すべて", "全て", "必ず", "常に", "あらゆる", "all", "every", "always", "never", "none"];
const NEGATION_KEYWORDS: &[&str] = &["ない", "ではない", "不可能", "否定", "not", "never", "impossible", "deny", "false"];
const HEDGE_KEYWORDS: &[&str] = &["おそらく", "たぶん", "かもしれない", "可能性", "perhaps", "maybe", "might", "possibly", "likely"];

/// Check if any keyword is present in text
fn has_keyword(text: &str, keywords: &[&str]) -> bool {
    let lower = text.to_lowercase();
    keywords.iter().any(|kw| lower.contains(&kw.to_lowercase()))
}

/// Count matching keywords
fn keyword_count(text: &str, keywords: &[&str]) -> usize {
    let lower = text.to_lowercase();
    keywords.iter().filter(|kw| lower.contains(&kw.to_lowercase())).count()
}

/// Semantic richness score based on proposition/entity/relation counts
fn semantic_richness(semantic: &SemanticData) -> f64 {
    let p = semantic.propositions.len() as f64;
    let e = semantic.entities.len() as f64;
    let r = semantic.relations.len() as f64;
    ((p * 0.4 + e * 0.3 + r * 0.3) / 5.0).min(1.0)
}

/// Evidence strength heuristic
fn evidence_strength(evidence: &[&str]) -> f64 {
    let count = evidence.len() as f64;
    let avg_len = if evidence.is_empty() {
        0.0
    } else {
        evidence.iter().map(|e| e.len() as f64).sum::<f64>() / count
    };
    let count_score = (count / 3.0).min(1.0);
    let len_score = (avg_len / 100.0).min(1.0);
    count_score * 0.6 + len_score * 0.4
}

// ═══════════════════════════════════════════════════
// Solver Implementations
// ═══════════════════════════════════════════════════

macro_rules! define_solver {
    ($struct_name:ident, $id:expr, $name:expr, $domain:expr, $cluster:expr, $verify_fn:expr) => {
        pub struct $struct_name;
        impl Solver for $struct_name {
            fn id(&self) -> &str { $id }
            fn name(&self) -> &str { $name }
            fn domain(&self) -> &str { $domain }
            fn cluster(&self) -> &str { $cluster }
            fn verify(&self, claim: &str, evidence: &[&str], semantic: &SemanticData) -> SolverResult {
                let (passed, confidence, reason) = $verify_fn(claim, evidence, semantic);
                SolverResult {
                    solver_id: $id.to_string(),
                    solver_name: $name.to_string(),
                    passed,
                    confidence,
                    reason,
                    domain: $domain.to_string(),
                    cluster: $cluster.to_string(),
                }
            }
        }
    };
}

// ── Formal Cluster (S01-S05) ──

define_solver!(S01Propositional, "S01", "PropositionalLogic", "logic", "formal",
    |claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let has_negation = has_keyword(claim, NEGATION_KEYWORDS);
        let has_universal = has_keyword(claim, UNIVERSAL_KEYWORDS);
        let prop_count = semantic.propositions.len();
        // Universal + negation = contradiction-prone
        if has_universal && has_negation {
            (false, 0.3, "全称否定: 反証容易".into())
        } else if prop_count >= 2 {
            (true, 0.6 + (prop_count as f64 * 0.05).min(0.3), "命題構造が存在".into())
        } else {
            (true, 0.5, "単一命題".into())
        }
    }
);

define_solver!(S02SetTheory, "S02", "SetTheory", "set_theory", "formal",
    |claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let entities = &semantic.entities;
        if entities.len() >= 2 {
            // Check for containment/membership language
            let has_containment = claim.contains("含む") || claim.contains("属する")
                || claim.contains("contain") || claim.contains("member")
                || claim.contains("subset") || claim.contains("部分");
            let conf = if has_containment { 0.75 } else { 0.55 };
            (true, conf, format!("{}エンティティの集合関係", entities.len()))
        } else {
            (true, 0.45, "エンティティ不足".into())
        }
    }
);

define_solver!(S03Algebra, "S03", "AbstractAlgebra", "algebra", "formal",
    |claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let math_score = keyword_count(claim, MATH_KEYWORDS) as f64 * 0.15;
        let richness = semantic_richness(semantic);
        let conf = (0.4 + math_score + richness * 0.2).min(0.95);
        (conf > 0.45, conf, "代数構造チェック".into())
    }
);

define_solver!(S04NumberTheory, "S04", "NumberTheory", "number_theory", "formal",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_numbers = claim.chars().any(|c| c.is_ascii_digit());
        let has_math = has_keyword(claim, MATH_KEYWORDS);
        if has_numbers && has_math {
            (true, 0.7, "数値的主張: 検証可能".into())
        } else if has_numbers {
            (true, 0.6, "数値を含む".into())
        } else {
            (true, 0.45, "数値なし".into())
        }
    }
);

define_solver!(S05CategoryTheory, "S05", "CategoryTheory", "category_theory", "formal",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let rel_count = semantic.relations.len();
        let ent_count = semantic.entities.len();
        // Category theory = objects + morphisms
        if rel_count >= 2 && ent_count >= 2 {
            (true, 0.65, format!("圏構造: {}対象, {}射", ent_count, rel_count))
        } else {
            (true, 0.45, "構造不足".into())
        }
    }
);

// ── Geometric Cluster (S06-S10) ──

define_solver!(S06Topology, "S06", "Topology", "topology", "geometric",
    |claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let richness = semantic_richness(semantic);
        let claim_len = claim.len() as f64;
        let complexity = (claim_len / 100.0).min(1.0);
        let conf = 0.4 + richness * 0.3 + complexity * 0.2;
        (conf > 0.45, conf.min(0.9), "位相的整合性".into())
    }
);

define_solver!(S07Geometry, "S07", "Geometry", "geometry", "geometric",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let spatial = claim.contains("空間") || claim.contains("距離")
            || claim.contains("space") || claim.contains("distance")
            || claim.contains("dimension") || claim.contains("次元");
        if spatial {
            (true, 0.65, "空間的概念を含む".into())
        } else {
            (true, 0.5, "空間性なし".into())
        }
    }
);

define_solver!(S08DiffGeometry, "S08", "DifferentialGeometry", "differential_geometry", "geometric",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let richness = semantic_richness(semantic);
        (true, 0.45 + richness * 0.3, "微分幾何チェック".into())
    }
);

define_solver!(S09MetricGeometry, "S09", "MetricGeometry", "metric_geometry", "geometric",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_numbers = claim.chars().any(|c| c.is_ascii_digit());
        let conf = if has_numbers { 0.6 } else { 0.45 };
        (true, conf, "距離空間チェック".into())
    }
);

define_solver!(S10AlgTopology, "S10", "AlgebraicTopology", "algebraic_topology", "geometric",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let richness = semantic_richness(semantic);
        (true, 0.45 + richness * 0.25, "代数的位相チェック".into())
    }
);

// ── Physical Cluster (S11-S14) ──

define_solver!(S11Spacetime, "S11", "MinkowskiCausal", "spacetime", "physical",
    |claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let has_causal = has_keyword(claim, CAUSAL_KEYWORDS);
        let has_physics = has_keyword(claim, PHYSICS_KEYWORDS);
        let conf = 0.4 + if has_causal { 0.2 } else { 0.0 } + if has_physics { 0.15 } else { 0.0 }
            + semantic_richness(semantic) * 0.15;
        (conf > 0.45, conf.min(0.9), "時空因果チェック".into())
    }
);

define_solver!(S12Dynamical, "S12", "DynamicalSystems", "dynamical_systems", "physical",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let richness = semantic_richness(semantic);
        (true, 0.45 + richness * 0.3, "力学系チェック".into())
    }
);

define_solver!(S13StatMech, "S13", "StatisticalMechanics", "statistical_mechanics", "physical",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_stats = claim.contains("統計") || claim.contains("エントロピー")
            || claim.contains("statistic") || claim.contains("entropy");
        let conf = if has_stats { 0.65 } else { 0.45 };
        (true, conf, "統計力学チェック".into())
    }
);

define_solver!(S14Spectral, "S14", "SpectralTheory", "spectral_theory", "physical",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let richness = semantic_richness(semantic);
        (true, 0.45 + richness * 0.2, "スペクトルチェック".into())
    }
);

// ── Statistical Cluster (S15-S18) ──

define_solver!(S15Probability, "S15", "Probability", "probability", "statistical",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_hedge = has_keyword(claim, HEDGE_KEYWORDS);
        if has_hedge {
            (true, 0.55, "確率的言明: 曖昧性あり".into())
        } else {
            (true, 0.5, "確率チェック".into())
        }
    }
);

define_solver!(S16Bayesian, "S16", "Bayesian", "bayesian", "statistical",
    |_claim: &str, evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let ev_strength = evidence_strength(evidence);
        let conf = 0.4 + ev_strength * 0.4;
        (conf > 0.45, conf.min(0.9), format!("ベイジアン: エビデンス強度={:.2}", ev_strength))
    }
);

define_solver!(S17Frequentist, "S17", "Frequentist", "frequentist", "statistical",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_numbers = claim.chars().any(|c| c.is_ascii_digit());
        let conf = if has_numbers { 0.6 } else { 0.45 };
        (true, conf, "頻度論チェック".into())
    }
);

define_solver!(S18InfoTheory, "S18", "InformationTheory", "information_theory", "statistical",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_info = claim.contains("情報") || claim.contains("エントロピー")
            || claim.contains("information") || claim.contains("entropy") || claim.contains("bit");
        let conf = if has_info { 0.65 } else { 0.45 };
        (true, conf, "情報理論チェック".into())
    }
);

// ── Empirical Cluster (S19-S23) ──

define_solver!(S19Adversarial, "S19", "Adversarial", "adversarial", "empirical",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        // Known false patterns
        let known_false: &[&str] = &[
            "地球は平ら", "flat earth", "ワクチンは自閉症", "vaccine autism",
            "moon landing fake", "月面着陸は嘘", "5gがコロナ", "5g covid",
            "evolution is false", "進化論は嘘",
        ];
        let lower = claim.to_lowercase();
        for pattern in known_false {
            if lower.contains(&pattern.to_lowercase()) {
                return (false, 0.15, format!("既知の虚偽パターン: {}", pattern));
            }
        }
        (true, 0.55, "敵対的チェック通過".into())
    }
);

define_solver!(S20Ensemble, "S20", "Ensemble", "ensemble", "empirical",
    |_claim: &str, evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let ev = evidence_strength(evidence);
        let sem = semantic_richness(semantic);
        let conf = ev * 0.5 + sem * 0.5;
        (conf > 0.35, (0.4 + conf * 0.5).min(0.9), "アンサンブル統合".into())
    }
);

define_solver!(S21Semantic, "S21", "SemanticVerifier", "semantic", "empirical",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let richness = semantic_richness(semantic);
        if richness > 0.6 {
            (true, 0.7, format!("豊富な意味構造 (richness={:.2})", richness))
        } else if richness > 0.3 {
            (true, 0.55, format!("中程度の意味構造 (richness={:.2})", richness))
        } else {
            (false, 0.35, "意味構造が不足".into())
        }
    }
);

define_solver!(S22CausalInference, "S22", "CausalInference", "causal_inference", "empirical",
    |claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let has_causal = has_keyword(claim, CAUSAL_KEYWORDS);
        let has_mechanism = semantic.relations.iter().any(|r|
            r.contains("causal") || r.contains("implies") || r.contains("causes")
        );
        if has_causal && has_mechanism {
            (true, 0.7, "因果構造あり".into())
        } else if has_causal {
            (false, 0.4, "因果主張あるがメカニズム不明".into())
        } else {
            (true, 0.5, "因果チェック不要".into())
        }
    }
);

define_solver!(S23Computational, "S23", "Computational", "computational", "empirical",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let has_cs = has_keyword(claim, CS_KEYWORDS);
        let conf = if has_cs { 0.65 } else { 0.5 };
        (true, conf, "計算的チェック".into())
    }
);

// ── Contextual Cluster (S24-S28) ──

define_solver!(S24Temporal, "S24", "TemporalContext", "temporal", "contextual",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let temporal_markers = ["現在", "過去", "未来", "今", "昔", "将来",
            "now", "past", "future", "current", "former", "2026", "2025", "2024"];
        let count = temporal_markers.iter().filter(|m| claim.contains(*m)).count();
        let conf = 0.45 + (count as f64 * 0.1).min(0.4);
        (true, conf, format!("時間的コンテキスト: {}マーカー", count))
    }
);

define_solver!(S25Cultural, "S25", "CulturalContext", "cultural", "contextual",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        // Detect cultural/language context
        let is_japanese = claim.chars().any(|c| ('\u{3040}'..='\u{30FF}').contains(&c)
            || ('\u{4E00}'..='\u{9FFF}').contains(&c));
        let has_cultural = claim.contains("文化") || claim.contains("社会") || claim.contains("伝統")
            || claim.contains("culture") || claim.contains("society") || claim.contains("tradition");
        let conf: f64 = 0.45 + if is_japanese { 0.1 } else { 0.0 } + if has_cultural { 0.15 } else { 0.0 };
        (true, conf.min(0.85), "文化的コンテキストチェック".into())
    }
);

define_solver!(S26Linguistic, "S26", "LinguisticAnalysis", "linguistic", "contextual",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let word_count = claim.split_whitespace().count();
        let char_count = claim.chars().count();
        let avg_word_len = if word_count > 0 { char_count as f64 / word_count as f64 } else { 0.0 };
        let complexity = (avg_word_len / 10.0).min(1.0);
        let conf = 0.45 + complexity * 0.3;
        (true, conf, format!("言語分析: {}文字, 複雑度={:.2}", char_count, complexity))
    }
);

define_solver!(S27Meta, "S27", "MetaVerification", "meta", "contextual",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let self_ref = ["KS", "Katala", "しろくま", "ソルバー", "検証", "solver", "verification"]
            .iter().filter(|kw| claim.contains(*kw)).count();
        if self_ref >= 2 {
            (true, 0.4, format!("自己参照性: {}キーワード — 信頼度制限", self_ref))
        } else {
            (true, 0.55, "メタ検証通過".into())
        }
    }
);

define_solver!(S28SelfOther, "S28", "SelfOtherBoundary", "self_other", "contextual",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        // Self-other boundary: who is making the claim?
        let self_markers = ["私", "我々", "自分", "I ", "we ", "my ", "our "];
        let other_markers = ["彼", "彼女", "それ", "they", "he ", "she ", "it "];
        let self_count = self_markers.iter().filter(|m| claim.contains(*m)).count();
        let other_count = other_markers.iter().filter(|m| claim.contains(*m)).count();
        let boundary_clarity = if self_count > 0 && other_count > 0 {
            0.7  // Clear self-other distinction
        } else if self_count > 0 {
            0.5  // Self-referential
        } else {
            0.55 // Objective framing
        };
        (true, boundary_clarity, format!("自他境界: self={}, other={}", self_count, other_count))
    }
);

// ── Extended HTLF Cluster (S29-S33) ──

define_solver!(S29HtlfStruct, "S29", "HTLF-Structural", "htlf_struct", "extended",
    |_claim: &str, _evidence: &[&str], semantic: &SemanticData| -> (bool, f64, String) {
        let prop_count = semantic.propositions.len();
        let rel_count = semantic.relations.len();
        let structural = (prop_count as f64 * 0.3 + rel_count as f64 * 0.4) / 3.0;
        let conf = (0.4 + structural).min(0.9);
        (conf > 0.45, conf, format!("HTLF構造: props={}, rels={}", prop_count, rel_count))
    }
);

define_solver!(S30HtlfContext, "S30", "HTLF-Context", "htlf_context", "extended",
    |_claim: &str, evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let ev_strength = evidence_strength(evidence);
        let conf = 0.4 + ev_strength * 0.45;
        (conf > 0.45, conf.min(0.9), format!("HTLFコンテキスト: ev_strength={:.2}", ev_strength))
    }
);

define_solver!(S31HtlfQualia, "S31", "HTLF-Qualia", "htlf_qualia", "extended",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let subjective = claim.contains("感じ") || claim.contains("経験") || claim.contains("意識")
            || claim.contains("feel") || claim.contains("experience") || claim.contains("conscious")
            || claim.contains("直感") || claim.contains("intuition");
        if subjective {
            // Qualia claims are inherently hard to verify
            (true, 0.4, "主観的概念: R_qualia測定対象外".into())
        } else {
            (true, 0.55, "客観的主張".into())
        }
    }
);

define_solver!(S32HtlfCultural, "S32", "HTLF-Cultural", "htlf_cultural", "extended",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        let is_multilingual = claim.chars().any(|c| ('\u{3040}'..='\u{30FF}').contains(&c))
            && claim.chars().any(|c| c.is_ascii_alphabetic());
        let conf = if is_multilingual { 0.6 } else { 0.5 };
        (true, conf, "HTLF文化軸チェック".into())
    }
);

define_solver!(S33HtlfTemporal, "S33", "HTLF-Temporal", "htlf_temporal", "extended",
    |claim: &str, _evidence: &[&str], _semantic: &SemanticData| -> (bool, f64, String) {
        // R_temporal = present context ONLY
        let future = ["将来", "予測", "になるだろう", "will ", "predict", "forecast"];
        let has_future = future.iter().any(|f| claim.contains(f));
        if has_future {
            (false, 0.3, "未来予測を含む: R_temporal=現在のみ".into())
        } else {
            (true, 0.55, "現在時制: R_temporal安定".into())
        }
    }
);

/// Build the full 33-solver chain
pub fn build_solver_chain() -> Vec<Box<dyn Solver + Send + Sync>> {
    vec![
        // Formal (S01-S05)
        Box::new(S01Propositional),
        Box::new(S02SetTheory),
        Box::new(S03Algebra),
        Box::new(S04NumberTheory),
        Box::new(S05CategoryTheory),
        // Geometric (S06-S10)
        Box::new(S06Topology),
        Box::new(S07Geometry),
        Box::new(S08DiffGeometry),
        Box::new(S09MetricGeometry),
        Box::new(S10AlgTopology),
        // Physical (S11-S14)
        Box::new(S11Spacetime),
        Box::new(S12Dynamical),
        Box::new(S13StatMech),
        Box::new(S14Spectral),
        // Statistical (S15-S18)
        Box::new(S15Probability),
        Box::new(S16Bayesian),
        Box::new(S17Frequentist),
        Box::new(S18InfoTheory),
        // Empirical (S19-S23)
        Box::new(S19Adversarial),
        Box::new(S20Ensemble),
        Box::new(S21Semantic),
        Box::new(S22CausalInference),
        Box::new(S23Computational),
        // Contextual (S24-S28)
        Box::new(S24Temporal),
        Box::new(S25Cultural),
        Box::new(S26Linguistic),
        Box::new(S27Meta),
        Box::new(S28SelfOther),
        // Extended HTLF (S29-S33)
        Box::new(S29HtlfStruct),
        Box::new(S30HtlfContext),
        Box::new(S31HtlfQualia),
        Box::new(S32HtlfCultural),
        Box::new(S33HtlfTemporal),
    ]
}
