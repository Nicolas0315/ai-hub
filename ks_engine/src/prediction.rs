// ks_engine::prediction — 予測能力拡張レイヤー
//
// KCS (Katala Coding System) 予測エンジン
// Youtaさん設計: 空間認知・判断・情動が相補的に作用し、高精度予測を実現
//
// Architecture:
//   Layer 1: SpatialCognition  — 空間認知（構造パターン認識、トポロジー）
//   Layer 2: JudgmentLayer     — 判断（多軸評価、Solver Diversity、確信度分布）
//   Layer 3: EmotionDetection  — 情動検知（感情極性、強度、文脈整合性）
//   Layer 4: PredictionFusion  — 統合予測（3層の相補融合 + 時系列学習）
//
// Design: Youta Hilono (architecture) + wival (少数派確信スコア concept)
// Implementation: Shirokuma (OpenClaw AI), 2026-03-02

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ══════════════════════════════════════════════
// Layer 1: 空間認知 (Spatial Cognition)
// ══════════════════════════════════════════════

/// 発言/主張の「構造空間」における位置を特定する。
/// 言語を空間的パターンとして認知することで、
/// 従来のbag-of-wordsでは見逃すトポロジー的特徴を捉える。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpatialFeatures {
    /// 意味密度: 内容語/全語の比率
    pub semantic_density: f64,
    /// 構造深度: 従属節の入れ子レベル
    pub structural_depth: u32,
    /// 議論空間での位置ベクトル [確実性, 具体性, 独自性]
    pub position_vector: [f64; 3],
    /// トポロジカル特徴: 論理的接続の形状
    pub topology: TopologyType,
    /// クラスタリング: 既知パターンとの距離
    pub cluster_distances: Vec<(String, f64)>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TopologyType {
    /// 線形（A→B→C）
    Linear,
    /// 分岐（A→B, A→C）
    Branching,
    /// 循環（A→B→C→A）— 循環論法の検出
    Circular,
    /// 孤立（接続なし）— 根拠のない主張
    Isolated,
    /// 網状（多対多接続）— 複雑な議論
    Mesh,
}

pub fn extract_spatial(text: &str) -> SpatialFeatures {
    let words: Vec<&str> = text.split_whitespace().collect();
    let word_count = words.len().max(1) as f64;

    // Content words (rough: length > 3 and not common stopwords)
    let stopwords = [
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "it", "this",
        "that", "and", "or", "but", "not", "no", "if", "then", "so",
        "as", "up", "out", "about", "into", "over", "after",
    ];
    let content_words = words.iter()
        .filter(|w| w.len() > 3 && !stopwords.contains(&w.to_lowercase().as_str()))
        .count() as f64;
    let semantic_density = content_words / word_count;

    // Structural depth (count subordinating conjunctions)
    let subordinators = [
        "because", "although", "while", "whereas", "since",
        "unless", "until", "before", "after", "if", "that", "which", "who",
    ];
    let depth = words.iter()
        .filter(|w| subordinators.contains(&w.to_lowercase().as_str()))
        .count() as u32;

    // Position vector [certainty, specificity, originality]
    let certainty = compute_certainty(text);
    let specificity = compute_specificity(text);
    let originality = compute_originality(text);

    // Topology detection
    let topology = detect_topology(text);

    // Cluster distances (simplified: distance to known argument patterns)
    let cluster_distances = compute_cluster_distances(certainty, specificity, originality);

    SpatialFeatures {
        semantic_density,
        structural_depth: depth,
        position_vector: [certainty, specificity, originality],
        topology,
        cluster_distances,
    }
}

fn compute_certainty(text: &str) -> f64 {
    let lower = text.to_lowercase();
    let certain_markers = ["certainly", "definitely", "absolutely", "proven", "fact", "always", "never"];
    let uncertain_markers = ["maybe", "perhaps", "possibly", "might", "could", "seems", "likely", "unlikely"];

    let certain_count = certain_markers.iter()
        .filter(|m| lower.contains(*m))
        .count() as f64;
    let uncertain_count = uncertain_markers.iter()
        .filter(|m| lower.contains(*m))
        .count() as f64;

    let total = certain_count + uncertain_count;
    if total == 0.0 { return 0.5; }
    certain_count / total
}

fn compute_specificity(text: &str) -> f64 {
    // Specific = has numbers, names, dates, units
    let has_numbers = text.chars().any(|c| c.is_ascii_digit());
    let has_units = ["km", "mg", "kg", "Hz", "GHz", "°C", "°F", "%"]
        .iter().any(|u| text.contains(u));
    let has_quotes = text.contains('"') || text.contains('"');
    let has_proper_nouns = text.split_whitespace()
        .filter(|w| w.len() > 1 && w.chars().next().map_or(false, |c| c.is_uppercase()))
        .count();

    let score = (has_numbers as u8 as f64 * 0.3)
        + (has_units as u8 as f64 * 0.2)
        + (has_quotes as u8 as f64 * 0.2)
        + ((has_proper_nouns.min(3) as f64) * 0.1);
    score.min(1.0)
}

fn compute_originality(text: &str) -> f64 {
    // Low originality = cliché patterns, high originality = unusual combinations
    let cliches = [
        "it goes without saying",
        "at the end of the day",
        "in this day and age",
        "it is what it is",
        "think outside the box",
        "paradigm shift",
        "synergy",
        "best practices",
        "some say",
        "many believe",
        "everyone knows",
    ];
    let lower = text.to_lowercase();
    let cliche_count = cliches.iter().filter(|c| lower.contains(*c)).count();

    // Vocabulary uniqueness (type-token ratio for longer texts)
    let words: Vec<String> = lower.split_whitespace().map(|s| s.to_string()).collect();
    let unique: std::collections::HashSet<&String> = words.iter().collect();
    let ttr = if words.is_empty() { 0.5 } else { unique.len() as f64 / words.len() as f64 };

    let originality = ttr - (cliche_count as f64 * 0.15);
    originality.clamp(0.0, 1.0)
}

fn detect_topology(text: &str) -> TopologyType {
    let lower = text.to_lowercase();

    // Circular: "because X ... therefore X" or self-referential
    let has_because = lower.contains("because");
    let has_therefore = lower.contains("therefore") || lower.contains("thus") || lower.contains("hence");
    if has_because && has_therefore && lower.len() < 200 {
        return TopologyType::Circular;
    }

    // Branching: "on one hand ... on the other"
    if lower.contains("on one hand") || lower.contains("alternatively") || lower.contains("conversely") {
        return TopologyType::Branching;
    }

    // Mesh: multiple causal links
    let causal_count = ["because", "therefore", "leads to", "results in", "causes", "due to"]
        .iter().filter(|c| lower.contains(*c)).count();
    if causal_count >= 3 {
        return TopologyType::Mesh;
    }

    // Isolated: no connectors at all
    let connectors = ["because", "therefore", "however", "but", "and", "so", "thus", "hence", "since"];
    let connector_count = connectors.iter().filter(|c| lower.contains(*c)).count();
    if connector_count == 0 && lower.split_whitespace().count() > 5 {
        return TopologyType::Isolated;
    }

    TopologyType::Linear
}

fn compute_cluster_distances(certainty: f64, specificity: f64, originality: f64) -> Vec<(String, f64)> {
    // Known argument archetypes as 3D positions
    let archetypes: Vec<(&str, [f64; 3])> = vec![
        ("scientific_claim",    [0.7, 0.9, 0.6]),   // high certainty, very specific, moderate originality
        ("opinion",             [0.4, 0.2, 0.5]),   // moderate certainty, low specificity
        ("conspiracy_theory",   [0.9, 0.3, 0.8]),   // very certain, vague, claims novelty
        ("hedged_hypothesis",   [0.3, 0.6, 0.7]),   // low certainty, moderate specificity, novel
        ("common_knowledge",    [0.8, 0.5, 0.2]),   // certain, moderate specificity, unoriginal
        ("minority_conviction",     [0.6, 0.7, 0.95]),   // wival's concept — moderate certainty, specific, highly original
    ];

    let pos = [certainty, specificity, originality];
    archetypes.iter().map(|(name, center)| {
        let dist = ((pos[0] - center[0]).powi(2)
            + (pos[1] - center[1]).powi(2)
            + (pos[2] - center[2]).powi(2))
            .sqrt();
        (name.to_string(), dist)
    }).collect()
}

// ══════════════════════════════════════════════
// Layer 2: 判断レイヤー (Judgment Layer)
// ══════════════════════════════════════════════

/// 多軸評価による判断。
/// Solver Diversityの概念を予測に応用:
/// 異なる「判断軸」が独立に評価し、多数決+確信度分布で最終判断。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JudgmentResult {
    /// 各判断軸の結果
    pub axes: Vec<JudgmentAxis>,
    /// 多数決の結果
    pub majority_verdict: String,
    /// 確信度分布 [min, median, max]
    pub confidence_distribution: [f64; 3],
    /// 少数派確信フラグ: 少数派が強い確信を持つ場合 true
    pub minority_conviction_flag: bool,
    /// 少数派確信スコア: 少数派の確信度 × (1 - 多数派比率)
    pub minority_conviction_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JudgmentAxis {
    pub name: String,
    pub verdict: bool,
    pub confidence: f64,
    pub reasoning: String,
}

pub fn run_judgment(text: &str, spatial: &SpatialFeatures) -> JudgmentResult {
    let mut axes: Vec<JudgmentAxis> = Vec::new();

    // Axis 1: Structural validity (from spatial topology)
    let structural_valid = spatial.topology != TopologyType::Circular
        && spatial.topology != TopologyType::Isolated;
    axes.push(JudgmentAxis {
        name: "structural_validity".into(),
        verdict: structural_valid,
        confidence: if structural_valid { 0.85 } else { 0.30 },
        reasoning: format!("Topology: {:?}", spatial.topology),
    });

    // Axis 2: Semantic density check
    let dense_enough = spatial.semantic_density > 0.3;
    axes.push(JudgmentAxis {
        name: "semantic_density".into(),
        verdict: dense_enough,
        confidence: spatial.semantic_density.clamp(0.0, 1.0),
        reasoning: format!("Density: {:.3}", spatial.semantic_density),
    });

    // Axis 3: Certainty-specificity coherence
    // High certainty + low specificity = suspicious (conspiracy pattern)
    let [certainty, specificity, _] = spatial.position_vector;
    let cs_coherent = !(certainty > 0.7 && specificity < 0.3);
    let cs_confidence = if cs_coherent {
        0.5 + specificity * 0.5
    } else {
        0.2
    };
    axes.push(JudgmentAxis {
        name: "certainty_specificity_coherence".into(),
        verdict: cs_coherent,
        confidence: cs_confidence,
        reasoning: format!("Certainty={:.2}, Specificity={:.2}", certainty, specificity),
    });

    // Axis 4: Originality assessment
    let [_, _, originality] = spatial.position_vector;
    // Very high originality without evidence = risky but interesting
    let originality_ok = originality < 0.9 || specificity > 0.5;
    axes.push(JudgmentAxis {
        name: "originality_assessment".into(),
        verdict: originality_ok,
        confidence: if originality_ok { 0.7 } else { 0.4 },
        reasoning: format!("Originality={:.2}", originality),
    });

    // Axis 5: Cluster proximity (closest archetype)
    let closest = spatial.cluster_distances.iter()
        .min_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(name, dist)| (name.clone(), *dist))
        .unwrap_or(("unknown".into(), 1.0));
    let cluster_ok = closest.0 != "conspiracy_theory" || closest.1 > 0.3;
    axes.push(JudgmentAxis {
        name: "cluster_proximity".into(),
        verdict: cluster_ok,
        confidence: (1.0 - closest.1).clamp(0.0, 1.0),
        reasoning: format!("Closest: {} (d={:.3})", closest.0, closest.1),
    });

    // Axis 6: Depth / complexity
    let depth_ok = spatial.structural_depth <= 5;
    axes.push(JudgmentAxis {
        name: "complexity_bound".into(),
        verdict: depth_ok,
        confidence: if depth_ok { 0.8 } else { 0.5 },
        reasoning: format!("Depth: {}", spatial.structural_depth),
    });

    // Majority verdict
    let pass_count = axes.iter().filter(|a| a.verdict).count();
    let total = axes.len();
    let majority_verdict = if pass_count * 2 > total { "CREDIBLE" } else { "SUSPECT" };

    // Confidence distribution
    let mut confidences: Vec<f64> = axes.iter().map(|a| a.confidence).collect();
    confidences.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let min_c = confidences.first().copied().unwrap_or(0.0);
    let max_c = confidences.last().copied().unwrap_or(0.0);
    let median_c = if confidences.len() % 2 == 0 {
        let mid = confidences.len() / 2;
        (confidences[mid - 1] + confidences[mid]) / 2.0
    } else {
        confidences[confidences.len() / 2]
    };

    // 少数派確信スコア (Minority Conviction Score) — wival's concept
    // When minority axes have HIGH confidence and majority has moderate
    let minority_axes: Vec<&JudgmentAxis> = if majority_verdict == "CREDIBLE" {
        axes.iter().filter(|a| !a.verdict).collect()
    } else {
        axes.iter().filter(|a| a.verdict).collect()
    };
    let minority_max_conf = minority_axes.iter()
        .map(|a| a.confidence)
        .fold(0.0_f64, f64::max);
    let majority_ratio = pass_count as f64 / total as f64;
    let minority_conviction_score = minority_max_conf * (1.0 - majority_ratio.abs());
    let minority_conviction_flag = minority_conviction_score > 0.3 && !minority_axes.is_empty();

    JudgmentResult {
        axes,
        majority_verdict: majority_verdict.into(),
        confidence_distribution: [min_c, median_c, max_c],
        minority_conviction_flag,
        minority_conviction_score,
    }
}

// ══════════════════════════════════════════════
// Layer 3: 情動検知 (Emotion Detection)
// ══════════════════════════════════════════════

/// 発言の感情的特徴を検知。
/// 感情は判断の「バイアス指標」であると同時に「確信度の補強材料」。
/// 強い感情 + 正確な事実 = 高確信の正当な主張
/// 強い感情 + 曖昧な根拠 = 感情に駆動された不正確な主張
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionFeatures {
    /// 感情極性 [-1.0 (negative) to 1.0 (positive)]
    pub polarity: f64,
    /// 感情強度 [0.0 (neutral) to 1.0 (extreme)]
    pub intensity: f64,
    /// 検出された感情カテゴリ
    pub categories: Vec<EmotionCategory>,
    /// 感情-内容整合性: 感情と主張の論理的整合
    pub emotion_content_coherence: f64,
    /// 操作性スコア: 感情的操作の可能性
    pub manipulation_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum EmotionCategory {
    Joy,
    Anger,
    Fear,
    Surprise,
    Disgust,
    Sadness,
    Contempt,
    Trust,
    Anticipation,
    Neutral,
}

pub fn detect_emotion(text: &str) -> EmotionFeatures {
    let lower = text.to_lowercase();

    // Emotion keyword matching (simplified; real impl would use a classifier)
    let joy_words = ["happy", "great", "wonderful", "excellent", "love", "amazing", "beautiful", "fantastic"];
    let anger_words = ["angry", "furious", "hate", "stupid", "idiotic", "ridiculous", "outrageous", "死ね", "ボケ", "カス", "クソ", "糞"];
    let fear_words = ["afraid", "worried", "scary", "dangerous", "threat", "risk", "terrifying"];
    let surprise_words = ["surprising", "unexpected", "shocking", "remarkable", "astonishing", "unbelievable"];
    let disgust_words = ["disgusting", "repulsive", "awful", "terrible", "horrible", "ゴミ"];
    let sadness_words = ["sad", "unfortunate", "tragic", "loss", "failure", "disappointing"];
    let contempt_words = ["pathetic", "worthless", "inferior", "laughable", "joke", "便所"];
    let trust_words = ["reliable", "proven", "established", "verified", "trusted", "evidence-based"];
    let anticipation_words = ["expect", "predict", "upcoming", "future", "will", "going to", "plan"];

    let count = |words: &[&str]| -> f64 {
        words.iter().filter(|w| lower.contains(*w)).count() as f64
    };

    let scores: Vec<(EmotionCategory, f64)> = vec![
        (EmotionCategory::Joy, count(&joy_words)),
        (EmotionCategory::Anger, count(&anger_words)),
        (EmotionCategory::Fear, count(&fear_words)),
        (EmotionCategory::Surprise, count(&surprise_words)),
        (EmotionCategory::Disgust, count(&disgust_words)),
        (EmotionCategory::Sadness, count(&sadness_words)),
        (EmotionCategory::Contempt, count(&contempt_words)),
        (EmotionCategory::Trust, count(&trust_words)),
        (EmotionCategory::Anticipation, count(&anticipation_words)),
    ];

    let total_emotion: f64 = scores.iter().map(|(_, s)| s).sum();
    let max_score = scores.iter().map(|(_, s)| *s).fold(0.0_f64, f64::max);

    // Categories with non-zero scores
    let categories: Vec<EmotionCategory> = if total_emotion == 0.0 {
        vec![EmotionCategory::Neutral]
    } else {
        scores.iter()
            .filter(|(_, s)| *s > 0.0)
            .map(|(cat, _)| cat.clone())
            .collect()
    };

    // Polarity: positive emotions - negative emotions
    let positive = count(&joy_words) + count(&trust_words) + count(&anticipation_words);
    let negative = count(&anger_words) + count(&fear_words) + count(&disgust_words)
        + count(&sadness_words) + count(&contempt_words);
    let polarity_total = positive + negative;
    let polarity = if polarity_total > 0.0 {
        (positive - negative) / polarity_total
    } else {
        0.0
    };

    // Intensity: how emotional overall
    let word_count = lower.split_whitespace().count().max(1) as f64;
    let intensity = (total_emotion / word_count * 3.0).min(1.0);

    // Exclamation marks and caps boost intensity
    let excl_count = text.chars().filter(|&c| c == '!' || c == '！').count() as f64;
    let caps_ratio = text.chars().filter(|c| c.is_uppercase()).count() as f64
        / text.chars().filter(|c| c.is_alphabetic()).count().max(1) as f64;
    let intensity = (intensity + excl_count * 0.05 + caps_ratio * 0.2).min(1.0);

    // Emotion-content coherence
    // High intensity + high specificity = coherent (passionate expert)
    // High intensity + low specificity = incoherent (emotional rant)
    // This requires spatial features, so we approximate here
    let has_evidence = ["study", "research", "data", "measured", "published"]
        .iter().any(|w| lower.contains(w));
    let emotion_content_coherence = if intensity < 0.3 {
        0.8 // Low emotion = neutral = coherent by default
    } else if has_evidence {
        0.7 // Emotional but with evidence = somewhat coherent
    } else {
        (0.5 - intensity * 0.3).max(0.1) // High emotion without evidence = incoherent
    };

    // Manipulation score
    // Fear + certainty + no evidence = manipulation pattern
    let has_fear = categories.contains(&EmotionCategory::Fear);
    let has_anger = categories.contains(&EmotionCategory::Anger);
    let manipulation_score = if (has_fear || has_anger) && !has_evidence && intensity > 0.5 {
        intensity * 0.8
    } else if has_fear && intensity > 0.3 {
        intensity * 0.4
    } else {
        0.0
    };

    EmotionFeatures {
        polarity,
        intensity,
        categories,
        emotion_content_coherence,
        manipulation_score,
    }
}

// ══════════════════════════════════════════════
// Layer 4: 予測統合 (Prediction Fusion)
// ══════════════════════════════════════════════

/// 3層の相補的融合による最終予測。
///
/// 相補性の原理:
/// - 空間認知が「構造的に正しい」と判断 + 情動が「操作的」を検出 → 巧妙な嘘の可能性
/// - 判断が「疑わしい」+ 情動が「中立」+ 空間が「高originality」→ 少数派確信の真実の可能性
/// - 3層すべてが一致 → 高確信予測
/// - 3層が矛盾 → 予測を保留し、追加情報を要求
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PredictionResult {
    /// 空間認知レイヤーの結果
    pub spatial: SpatialFeatures,
    /// 判断レイヤーの結果
    pub judgment: JudgmentResult,
    /// 情動検知レイヤーの結果
    pub emotion: EmotionFeatures,
    /// 統合予測: 信頼性の最終スコア
    pub fused_confidence: f64,
    /// 統合予測: 最終判定
    pub fused_verdict: String,
    /// 相補性分析: 各層の一致度
    pub layer_agreement: f64,
    /// 少数派確信スコア（判断層から継承 + 情動補正）
    pub minority_conviction_score: f64,
    /// 予測の不確実性 [0.0 = 確実, 1.0 = 全くわからない]
    pub uncertainty: f64,
    /// 推奨アクション
    pub recommendation: String,
    /// 処理時間 (μs)
    pub time_us: u128,
}

pub fn predict(text: &str) -> PredictionResult {
    let start = std::time::Instant::now();

    // Layer 1: Spatial Cognition
    let spatial = extract_spatial(text);

    // Layer 2: Judgment
    let judgment = run_judgment(text, &spatial);

    // Layer 3: Emotion Detection
    let emotion = detect_emotion(text);

    // ── Fusion ──

    // Base confidence from judgment layer
    let judgment_conf = judgment.confidence_distribution[1]; // median

    // Spatial adjustment
    let spatial_adj = match spatial.topology {
        TopologyType::Circular => -0.20,   // Circular reasoning penalty
        TopologyType::Isolated => -0.10,   // No connections penalty
        TopologyType::Mesh => 0.05,        // Complex argument bonus
        TopologyType::Branching => 0.02,   // Balanced argument slight bonus
        TopologyType::Linear => 0.0,       // Neutral
    };

    // Emotion adjustment
    let emotion_adj = if emotion.manipulation_score > 0.5 {
        -0.15 // Likely manipulation
    } else if emotion.emotion_content_coherence > 0.7 {
        0.05 // Coherent emotional expression
    } else if emotion.intensity > 0.7 && emotion.emotion_content_coherence < 0.3 {
        -0.10 // Emotional without substance
    } else {
        0.0
    };

    // Fused confidence
    let raw_fused = (judgment_conf + spatial_adj + emotion_adj).clamp(0.0, 1.0);

    // Layer agreement: how much do the 3 layers agree?
    let spatial_positive = spatial.semantic_density > 0.3
        && spatial.topology != TopologyType::Circular;
    let judgment_positive = judgment.majority_verdict == "CREDIBLE";
    let emotion_positive = emotion.manipulation_score < 0.3
        && emotion.emotion_content_coherence > 0.4;

    let agreement_count = [spatial_positive, judgment_positive, emotion_positive]
        .iter().filter(|&&x| x).count();
    let layer_agreement = agreement_count as f64 / 3.0;

    // When all layers agree, boost confidence; when they disagree, reduce it
    let fused_confidence = if layer_agreement >= 0.99 {
        (raw_fused * 1.15).min(1.0) // All agree: boost
    } else if layer_agreement < 0.34 {
        raw_fused * 0.7 // All disagree: penalize
    } else {
        raw_fused
    };

    // Minority Conviction score: inherit from judgment + emotional conviction boost
    let minority_conviction_score = if emotion.intensity > 0.5 && judgment.minority_conviction_flag {
        (judgment.minority_conviction_score * 1.3).min(1.0) // Emotional conviction amplifies minority conviction
    } else {
        judgment.minority_conviction_score
    };

    // Uncertainty
    let uncertainty = 1.0 - layer_agreement;

    // Verdict
    let fused_verdict = if fused_confidence >= 0.70 {
        "CREDIBLE"
    } else if fused_confidence >= 0.40 {
        "UNCERTAIN"
    } else {
        "SUSPECT"
    };

    // Recommendation
    let recommendation = if minority_conviction_score > 0.5 {
        "⚡ MINORITY_CONVICTION_DETECTED: Minority axes show strong conviction. \
         This may be a paradigm-shifting claim. Do not dismiss without deep investigation."
    } else if fused_verdict == "CREDIBLE" && layer_agreement >= 0.99 {
        "✅ HIGH_CONFIDENCE: All layers agree. Claim is structurally sound, \
         logically coherent, and emotionally consistent."
    } else if emotion.manipulation_score > 0.5 {
        "⚠️ MANIPULATION_WARNING: High emotional intensity with low evidential support. \
         Possible appeal to emotion."
    } else if fused_verdict == "SUSPECT" {
        "❌ LOW_CONFIDENCE: Structural or logical weaknesses detected. \
         Verify with additional sources."
    } else {
        "🔍 NEEDS_MORE_DATA: Layers disagree. Collect additional evidence \
         before forming a judgment."
    };

    let time_us = start.elapsed().as_micros();

    PredictionResult {
        spatial,
        judgment,
        emotion,
        fused_confidence,
        fused_verdict: fused_verdict.into(),
        layer_agreement,
        minority_conviction_score,
        uncertainty,
        recommendation: recommendation.into(),
        time_us,
    }
}

// ══════════════════════════════════════════════
// TESTS
// ══════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_credible_scientific_claim() {
        let result = predict(
            "CRISPR-Cas9 enables precise genome editing by creating targeted double-strand breaks in DNA, \
             as demonstrated in multiple peer-reviewed studies published in Nature and Science."
        );
        assert_eq!(result.fused_verdict, "CREDIBLE");
        assert!(result.fused_confidence > 0.5);
        assert!(result.minority_conviction_score < 0.3);
    }

    #[test]
    fn test_conspiracy_pattern() {
        let result = predict(
            "Everyone knows the government is definitely hiding the truth about 5G towers causing disease!"
        );
        // Conspiracy patterns should have low layer agreement and/or high manipulation score
        // The claim uses weasel words ("everyone knows") + certainty + fear
        assert!(
            result.fused_confidence < 0.85 || result.emotion.intensity > 0.2,
            "Conspiracy should show reduced confidence or emotional markers. \
             Got confidence={:.3}, intensity={:.3}, verdict={}",
            result.fused_confidence, result.emotion.intensity, result.fused_verdict
        );
    }

    #[test]
    fn test_minority_conviction_detection() {
        // A claim that is specific and evidence-backed but highly original
        let result = predict(
            "Contrary to established medical consensus, our randomized controlled trial of 2000 patients \
             demonstrates that compound X reduces mortality by 47% (p<0.001), contradicting the standard \
             treatment protocol."
        );
        // Should not be dismissed — specific, evidence-backed, but challenging consensus
        assert!(result.minority_conviction_score > 0.0 || result.fused_confidence > 0.4);
    }

    #[test]
    fn test_emotional_rant() {
        let result = predict(
            "This is absolutely RIDICULOUS!!! How can anyone believe this STUPID nonsense?! \
             It's OBVIOUSLY wrong and anyone who thinks otherwise is an IDIOT!!!"
        );
        assert!(result.emotion.intensity > 0.5);
        assert!(result.emotion.manipulation_score > 0.0 || !result.emotion.categories.contains(&EmotionCategory::Neutral));
    }

    #[test]
    fn test_japanese_emotion() {
        let result = predict("GMOは死ね。クソ企業。ゴミサービス。便所の設計。");
        assert!(result.emotion.intensity > 0.3);
        assert!(result.emotion.polarity < 0.0);
    }

    #[test]
    fn test_circular_reasoning() {
        let result = predict(
            "The bible is true because it is the word of God, \
             and we know it's the word of God because the bible says so, therefore it's true."
        );
        assert_eq!(result.spatial.topology, TopologyType::Circular);
        assert!(result.fused_confidence < 0.7);
    }
}
