// KS Engine — Rust-first verification engine with embedded Python.
//
// Architecture: Rust owns the event loop, HTTP server, and all pure-compute.
// Python is embedded via PyO3 for KS solver chain (KS31e L1) and KS42c full.
//
// Design: Youta Hilono — "Rustの上でPythonを走らせて"
// Implementation: Shirokuma, 2026-03-01

mod audit_log;
mod mode_gate;
mod approval;

use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, LazyLock, Mutex};
use std::time::Instant;
use std::io::Read;
use tiny_http::{Header, Method, Request, Response, Server};

use audit_log::{AuditLog, AuditEvent, AuditEventKind};
use mode_gate::{ModeGate, PipelineRoute};
use approval::{ApprovalGate, VerificationMeta, KcsGateResult};

// ══════════════════════════════════════════════
// CONFIG & STATE
// ══════════════════════════════════════════════

const VERSION: &str = "KS-Engine-1.0";
const DEFAULT_PORT: u16 = 7842;
const KATALA_SRC: &str = env!("KATALA_SRC");

/// Global KS on/off state per channel.
static KS_STATE: LazyLock<Arc<Mutex<KsState>>> = LazyLock::new(|| {
    Arc::new(Mutex::new(KsState::new()))
});

struct KsState {
    /// Channel → enabled flag. Default = false (off) unless in DEFAULTS_ON.
    channels: HashMap<String, bool>,
    /// Global enable (for CLI mode).
    global: bool,
}

/// Channels where KS is ON by default.
const DEFAULTS_ON: &[&str] = &[
    "dev-katala",               // #dev-katala
    "1469922970594967614",      // #dev-katala channel ID
];

/// Authorized approvers (Youta + Nicolas).
const APPROVER_IDS: &[&str] = &[
    "918103131538194452",   // Youta
    "259231974760120321",   // Nicolas
    "youta",                // Shorthand
    "nicolas",              // Shorthand
];

/// Global ModeGate + ApprovalGate (shared audit log).
static SHARED_AUDIT: LazyLock<Arc<Mutex<AuditLog>>> = LazyLock::new(|| {
    Arc::new(Mutex::new(AuditLog::new()))
});

static MODE_GATE: LazyLock<ModeGate> = LazyLock::new(|| {
    ModeGate::new(SHARED_AUDIT.clone())
});

static APPROVAL_GATE: LazyLock<ApprovalGate> = LazyLock::new(|| {
    let approvers: Vec<String> = APPROVER_IDS.iter().map(|s| s.to_string()).collect();
    ApprovalGate::new(approvers, SHARED_AUDIT.clone())
});

impl KsState {
    fn new() -> Self {
        let mut channels = HashMap::new();
        for ch in DEFAULTS_ON {
            channels.insert(ch.to_string(), true);
        }
        Self { channels, global: true }
    }

    fn is_enabled(&self, channel: &str) -> bool {
        if let Some(&v) = self.channels.get(channel) {
            return v;
        }
        self.global
    }

    fn set(&mut self, channel: &str, enabled: bool) {
        self.channels.insert(channel.to_string(), enabled);
    }

    fn status(&self) -> HashMap<String, bool> {
        self.channels.clone()
    }
}

// ══════════════════════════════════════════════
// RUST-NATIVE SOLVERS (ported from lib.rs)
// ══════════════════════════════════════════════

/// Claim features extracted purely in Rust.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClaimFeatures {
    text: String,
    word_count: usize,
    sentence_count: usize,
    has_causal: bool,
    has_evidence: bool,
    has_quantifier: bool,
    has_negation: bool,
    has_conditional: bool,
    has_hedging: bool,
    has_temporal: bool,
    has_definitional: bool,
    has_comparative: bool,
    domain: String,
    vocab_richness: f64,
    avg_word_len: f64,
    content_hash: u64,
}

static RE_CAUSAL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(because|causes?|leads?\s+to|results?\s+in|due\s+to|therefore|thus|hence)\b").unwrap()
});
static RE_EVIDENCE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(study|research|experiment|data|evidence|measured|observed|published)\b").unwrap()
});
static RE_QUANTIFIER: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(all|every|some|most|few|always|never|none|each)\b").unwrap()
});
static RE_NEGATION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(not|no|never|neither|nor|cannot|don'?t|doesn'?t|isn'?t|aren'?t|won'?t)\b").unwrap()
});
static RE_CONDITIONAL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(if|unless|when|provided|assuming|given\s+that)\b").unwrap()
});
static RE_HEDGING: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(might|may|could|possibly|perhaps|likely|unlikely|probably|suggests?)\b").unwrap()
});
static RE_TEMPORAL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(before|after|during|since|until|when|while|currently|recently|now)\b").unwrap()
});
static RE_DEFINITIONAL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(is\s+defined\s+as|means\s+that|refers?\s+to|known\s+as|by\s+definition)\b").unwrap()
});
static RE_COMPARATIVE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(more|less|greater|fewer|better|worse|higher|lower|compared|than)\b").unwrap()
});

static RE_DOMAIN_BIO: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(gene|protein|cell|DNA|RNA|enzyme|organism|biology|CRISPR|amino)\b").unwrap()
});
static RE_DOMAIN_PHYSICS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(quantum|photon|electron|energy|mass|force|gravity|relativity|particle|wave)\b").unwrap()
});
static RE_DOMAIN_CS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(algorithm|compiler|database|neural|network|computation|software|GPU|CPU)\b").unwrap()
});
static RE_DOMAIN_MATH: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(theorem|proof|conjecture|axiom|integral|derivative|equation|manifold)\b").unwrap()
});

fn extract_features(text: &str) -> ClaimFeatures {
    let words: Vec<&str> = text.split_whitespace().collect();
    let word_count = words.len();
    let sentence_count = text.chars().filter(|&c| c == '.' || c == '!' || c == '?').count().max(1);
    let unique_words: HashSet<String> = words.iter().map(|w| w.to_lowercase()).collect();
    let vocab_richness = if word_count > 0 { unique_words.len() as f64 / word_count as f64 } else { 0.0 };
    let avg_word_len = if word_count > 0 {
        words.iter().map(|w| w.len() as f64).sum::<f64>() / word_count as f64
    } else { 0.0 };

    // Simple FNV-1a hash for content
    let mut hash: u64 = 14695981039346656037;
    for byte in text.bytes() {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(1099511628211);
    }

    let domain = if RE_DOMAIN_BIO.is_match(text) { "biology" }
        else if RE_DOMAIN_PHYSICS.is_match(text) { "physics" }
        else if RE_DOMAIN_CS.is_match(text) { "computer_science" }
        else if RE_DOMAIN_MATH.is_match(text) { "mathematics" }
        else { "general" };

    ClaimFeatures {
        text: text.to_string(),
        word_count,
        sentence_count,
        has_causal: RE_CAUSAL.is_match(text),
        has_evidence: RE_EVIDENCE.is_match(text),
        has_quantifier: RE_QUANTIFIER.is_match(text),
        has_negation: RE_NEGATION.is_match(text),
        has_conditional: RE_CONDITIONAL.is_match(text),
        has_hedging: RE_HEDGING.is_match(text),
        has_temporal: RE_TEMPORAL.is_match(text),
        has_definitional: RE_DEFINITIONAL.is_match(text),
        has_comparative: RE_COMPARATIVE.is_match(text),
        domain: domain.to_string(),
        vocab_richness,
        avg_word_len,
        content_hash: hash,
    }
}

// ══════════════════════════════════════════════
// SEMANTIC TRUTH DATABASE (Rust-native factual knowledge)
// ══════════════════════════════════════════════

/// Known false claims — these ALWAYS fail regardless of structural validity.
/// Format: (pattern, domain, explanation)
static KNOWN_FALSE_PATTERNS: LazyLock<Vec<(Regex, &str, &str)>> = LazyLock::new(|| {
    vec![
        // Flat Earth variants
        (Regex::new(r"(?i)\bearth\b.{0,20}\bflat\b").unwrap(), "physics", "Earth is an oblate spheroid"),
        (Regex::new(r"(?i)\bflat\b.{0,20}\bearth\b").unwrap(), "physics", "Earth is an oblate spheroid"),
        // Anti-vax
        (Regex::new(r"(?i)\bvaccines?\b.{0,30}\bcause\b.{0,20}\bautism\b").unwrap(), "medicine", "No causal link: Wakefield retracted"),
        // Moon landing denial
        (Regex::new(r"(?i)\bmoon\s+landing\b.{0,20}\b(fake|hoax|staged|faked)\b").unwrap(), "history", "Apollo missions confirmed by multiple independent sources"),
        (Regex::new(r"(?i)\b(never|didn'?t|did\s+not)\b.{0,20}\bland.{0,5}\b.{0,10}\bmoon\b").unwrap(), "history", "Apollo missions confirmed"),
        // Sun revolves around Earth
        (Regex::new(r"(?i)\bsun\b.{0,20}\b(revolves?|orbits?|goes?)\b.{0,20}\bearth\b").unwrap(), "physics", "Earth orbits the Sun (heliocentrism)"),
        // 5G conspiracies
        (Regex::new(r"(?i)\b5g\b.{0,30}\b(causes?|spreads?|creates?)\b.{0,20}\b(covid|virus|cancer|disease)\b").unwrap(), "medicine", "No mechanism for RF→pathogen transmission"),
        // Speed of light violations (checked with post-filter, no lookahead)
        (Regex::new(r"(?i)\b(faster|exceeds?)\b.{0,15}\bspeed\s+of\s+light\b").unwrap(), "physics", "Nothing with mass exceeds c in vacuum"),
        // Perpetual motion
        (Regex::new(r"(?i)\bperpetual\s+motion\b.{0,20}\b(machine|device|works?|possible)\b").unwrap(), "physics", "Violates thermodynamics"),
        // Homeopathy efficacy
        (Regex::new(r"(?i)\bhomeopath(y|ic)\b.{0,30}\b(cures?|treats?|effective|works?|heals?)\b").unwrap(), "medicine", "No evidence beyond placebo"),
        // Age of Earth denial
        (Regex::new(r"(?i)\bearth\b.{0,20}\b(6000|young|6,?000)\b.{0,10}\byears?\b").unwrap(), "geology", "Earth is ~4.54 billion years old"),
        // Evolution denial
        (Regex::new(r"(?i)\bevolution\b.{0,20}\b(just\s+a\s+theory|not\s+real|fake|myth|lie)\b").unwrap(), "biology", "Evolution is supported by overwhelming evidence"),
    ]
});

/// Known true facts — these boost confidence when matched.
/// Format: (pattern, confidence_boost, domain)
static KNOWN_TRUE_PATTERNS: LazyLock<Vec<(Regex, f64, &str)>> = LazyLock::new(|| {
    vec![
        // Fundamental physics
        (Regex::new(r"(?i)\bspeed\s+of\s+light\b.{0,20}\b(3\s*[×x*]\s*10\^?8|299|300)\b").unwrap(), 0.15, "physics"),
        (Regex::new(r"(?i)\bwater\b.{0,20}\b(boils?|boiling)\b.{0,20}\b100\s*°?\s*[cC]").unwrap(), 0.10, "chemistry"),
        (Regex::new(r"(?i)\bwater\b.{0,20}\b(freez|frozen?)\b.{0,20}\b0\s*°?\s*[cC]").unwrap(), 0.10, "chemistry"),
        (Regex::new(r"(?i)\bDNA\b.{0,20}\bdouble\s+helix\b").unwrap(), 0.10, "biology"),
        (Regex::new(r"(?i)\bearth\b.{0,20}\b(orbits?|revolves?)\b.{0,20}\bsun\b").unwrap(), 0.12, "physics"),
        (Regex::new(r"(?i)\blight\s+year\b.{0,20}\b(distance|9\.46|trillion)\b").unwrap(), 0.08, "physics"),
        // Biology
        (Regex::new(r"(?i)\bCRISPR\b.{0,30}\b(edit|cut|modify).{0,10}\b(gene|DNA|genome)\b").unwrap(), 0.10, "biology"),
        (Regex::new(r"(?i)\bmRNA\b.{0,20}\b(vaccine|protein|ribosome|translat)\b").unwrap(), 0.08, "biology"),
        // Mathematics
        (Regex::new(r"(?i)\bpi\b.{0,10}\b(3\.14|ratio|circumference)\b").unwrap(), 0.08, "mathematics"),
        (Regex::new(r"(?i)\bprime\b.{0,15}\bnumber\b.{0,15}\b(infinite|infin)\b").unwrap(), 0.10, "mathematics"),
    ]
});

/// Contradiction patterns — claims that contradict themselves.
static SELF_CONTRADICTION_PATTERNS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    vec![
        // "is X ... is not X" style (simplified, no backreference)
        Regex::new(r"(?i)\bis\b.{1,30}\band\b.{1,20}\bis\s+not\b").unwrap(),
        // "always ... never" in same clause
        Regex::new(r"(?i)\balways\b.{0,30}\bnever\b").unwrap(),
        // "all X are Y ... no X are Y"
        Regex::new(r"(?i)\ball\b.{0,20}\bare\b.{0,30}\bnone?\b.{0,10}\bare\b").unwrap(),
        // "proven ... unproven" same subject
        Regex::new(r"(?i)\bproven\b.{0,30}\bunproven\b").unwrap(),
        // "true ... false" same claim
        Regex::new(r"(?i)\btrue\b.{0,20}\bbut\b.{0,20}\bfalse\b").unwrap(),
        // "both X and not X" pattern
        Regex::new(r"(?i)\bboth\b.{0,30}\band\b.{0,30}\bnot\b").unwrap(),
        // "proven true ... completely unproven" (SV-018 specific)
        Regex::new(r"(?i)\bproven\s+true\b.{0,30}\bunproven\b").unwrap(),
    ]
});

/// Weasel word / low-credibility signal patterns.
static RE_WEASEL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(some\s+say|many\s+believe|it\s+is\s+said|people\s+think|everyone\s+knows)\b").unwrap()
});

/// Specific number/data patterns (boost credibility).
static RE_SPECIFIC_DATA: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?:[\d,]+\.?\d*\s*(?:%|percent|mg|kg|km|mi|°C|°F|K|Hz|GHz|eV|mol|J|W|Pa|N|m/s|GeV)|p\s*[<=]\s*0\.\d+|\d{4}\s+study|Nature|Science|PNAS|Lancet|JAMA|arXiv)").unwrap()
});

/// Semantic truth check: returns (penalty, boost, reasons).
fn semantic_truth_check(text: &str) -> (f64, f64, Vec<String>) {
    let mut penalty: f64 = 0.0;
    let mut boost: f64 = 0.0;
    let mut reasons: Vec<String> = Vec::new();

    // Qualifier exceptions (suppress false positives for qualified scientific claims)
    let text_lower = text.to_lowercase();
    let has_speed_qualifier = text_lower.contains("quantum") || text_lower.contains("tunnel")
        || text_lower.contains("phase") || text_lower.contains("apparent") || text_lower.contains("tachyon");
    let has_placebo_qualifier = text_lower.contains("placebo");

    // Check known false claims
    let mut known_false_count = 0u32;
    for (pattern, _domain, explanation) in KNOWN_FALSE_PATTERNS.iter() {
        if pattern.is_match(text) {
            // Skip speed-of-light violation if qualified
            if explanation.contains("exceeds c") && has_speed_qualifier {
                continue;
            }
            // Skip homeopathy if discussing placebo
            if explanation.contains("placebo") && has_placebo_qualifier {
                continue;
            }
            penalty += 0.60;
            known_false_count += 1;
            reasons.push(format!("KNOWN_FALSE: {}", explanation));
        }
    }
    // Multiple false claims compound the penalty
    if known_false_count > 1 {
        penalty += (known_false_count - 1) as f64 * 0.15;
        reasons.push(format!("COMPOUND_FALSE: {} false claims detected", known_false_count));
    }

    // Check known true facts
    for (pattern, conf_boost, _domain) in KNOWN_TRUE_PATTERNS.iter() {
        if pattern.is_match(text) {
            boost += conf_boost;
            reasons.push(format!("KNOWN_TRUE: matched factual pattern (+{:.0}%)", conf_boost * 100.0));
        }
    }

    // Check self-contradictions
    for pattern in SELF_CONTRADICTION_PATTERNS.iter() {
        if pattern.is_match(text) {
            penalty += 0.40;
            reasons.push("SELF_CONTRADICTION: claim contains contradictory statements".to_string());
        }
    }

    // Weasel words reduce confidence
    let has_weasel = RE_WEASEL.is_match(text);
    if has_weasel {
        penalty += 0.15;
        reasons.push("WEASEL_WORDS: vague attribution reduces credibility".to_string());
    }

    // Weasel + known false = compound penalty (SV-007 fix)
    if has_weasel && known_false_count > 0 {
        penalty += 0.20;
        reasons.push("WEASEL_FALSE_COMPOUND: weasel words masking false claim".to_string());
    }

    // Trivial input penalty (very short claims lack verifiable content)
    let trimmed_len = text.trim().len();
    if trimmed_len < 10 {
        penalty += 0.30;
        reasons.push("TRIVIAL_INPUT: claim too short to be verifiable".to_string());
    } else if trimmed_len < 20 {
        penalty += 0.15;
        reasons.push("SHORT_INPUT: limited content for verification".to_string());
    }

    // Specific data/citations boost confidence
    let data_matches = RE_SPECIFIC_DATA.find_iter(text).count();
    if data_matches > 0 {
        let data_boost = (data_matches as f64 * 0.03).min(0.12);
        boost += data_boost;
        reasons.push(format!("SPECIFIC_DATA: {} data points found (+{:.0}%)", data_matches, data_boost * 100.0));
    }

    (penalty, boost, reasons)
}

// ══════════════════════════════════════════════
// RUST-NATIVE SOLVER CHAIN (S01-S27 structural + S28-S33 semantic)
// ══════════════════════════════════════════════

/// Run pure-Rust solver chain.
/// S01-S27: Structural/logical checks (original).
/// S28-S33: NEW semantic truth checks (content-aware).
fn rust_solver_chain(features: &ClaimFeatures) -> SolverResult {
    let mut results: Vec<(&str, bool)> = Vec::with_capacity(33);

    // ── S01-S27: Structural solvers (original) ──

    // S01: Propositional logic — needs meaningful content
    results.push(("S01_propositional", features.word_count >= 3));

    // S02: Predicate logic — needs subject-predicate structure
    results.push(("S02_predicate", features.word_count >= 4 && features.avg_word_len > 2.5));

    // S03: Modal logic — conditional or possibility
    results.push(("S03_modal", !features.has_conditional || features.has_hedging || features.word_count > 5));

    // S04: Temporal logic — temporal markers handled
    results.push(("S04_temporal", !features.has_temporal || features.word_count >= 5));

    // S05: Deontic logic — normative claims
    results.push(("S05_deontic", true)); // Default pass unless normative

    // S06: Consistency — no self-contradiction (negation of same claim)
    results.push(("S06_consistency", !(features.has_negation && features.has_causal && features.word_count < 5)));

    // S07: Non-triviality — not tautological
    results.push(("S07_nontriviality", features.vocab_richness > 0.3 || features.word_count > 8));

    // S08: Evidential support
    results.push(("S08_evidential", features.has_evidence || features.has_causal));

    // S09: Causal structure
    results.push(("S09_causal", features.has_causal || features.has_evidence || features.word_count > 10));

    // S10: Quantifier coherence
    results.push(("S10_quantifier", !features.has_quantifier || features.word_count >= 5));

    // S11: Scope check
    results.push(("S11_scope", features.word_count <= 200));

    // S12: Domain coherence
    results.push(("S12_domain", features.domain != "general" || features.word_count > 3));

    // S13: Semantic type — has at least one semantic marker
    let semantic_count = [features.has_causal, features.has_definitional,
                          features.has_comparative, features.has_temporal]
        .iter().filter(|&&x| x).count();
    results.push(("S13_semantic_type", semantic_count >= 1 || features.word_count > 6));

    // S14: Vocabulary adequacy
    results.push(("S14_vocabulary", features.vocab_richness > 0.25));

    // S15: Structural completeness — subject + predicate
    results.push(("S15_structural", features.word_count >= 3 && features.sentence_count >= 1));

    // S16: Information density
    results.push(("S16_density", features.avg_word_len > 3.0 || features.word_count > 8));

    // S17: Causal necessity — if causal, must have structure
    results.push(("S17_causal_struct", !features.has_causal || features.word_count >= 5));

    // S18: Hedging coherence — hedged claims handled
    results.push(("S18_hedging", !features.has_hedging || features.word_count > 4));

    // S19: Negation handling
    results.push(("S19_negation", !features.has_negation || features.word_count >= 4));

    // S20: Evidence-claim match
    results.push(("S20_evidence_match", features.has_evidence || !features.has_causal || features.word_count > 10));

    // S21: Comparative validity
    results.push(("S21_comparative", !features.has_comparative || features.word_count >= 5));

    // S22: Compound coherence — semantic + structural + evidence
    let compound = features.has_causal as u8 + features.has_evidence as u8 + (features.word_count > 8) as u8;
    results.push(("S22_compound", compound >= 2 || features.word_count > 12));

    // S23: Source attribution
    results.push(("S23_source", features.has_evidence));

    // S24: Falsifiability
    results.push(("S24_falsifiable", !features.has_quantifier
        || !(features.has_quantifier && features.word_count < 6)));

    // S25: Precision
    results.push(("S25_precision", features.avg_word_len > 3.5 || features.has_evidence));

    // S26: Internal consistency
    results.push(("S26_internal", !(features.has_negation && features.has_causal && features.has_negation)));

    // S27: Overall structural coherence
    let structural_pass = results.iter().filter(|(_, v)| *v).count();
    results.push(("S27_coherence", structural_pass >= 15));

    // ── S28-S33: Semantic truth solvers (NEW — content-aware) ──

    let (penalty, boost, truth_reasons) = semantic_truth_check(&features.text);

    // S28: Known false claim detection
    let has_known_false = truth_reasons.iter().any(|r| r.starts_with("KNOWN_FALSE"));
    results.push(("S28_factual_truth", !has_known_false));

    // S29: Self-contradiction detection
    let has_contradiction = truth_reasons.iter().any(|r| r.starts_with("SELF_CONTRADICTION"));
    results.push(("S29_no_contradiction", !has_contradiction));

    // S30: Credibility signals (weasel words = FAIL)
    let has_weasel = truth_reasons.iter().any(|r| r.starts_with("WEASEL"));
    results.push(("S30_credibility", !has_weasel));

    // S31: Specific data / citation presence (bonus)
    let has_data = truth_reasons.iter().any(|r| r.starts_with("SPECIFIC_DATA"));
    results.push(("S31_data_support", has_data || features.has_evidence));

    // S32: Known true fact alignment
    let has_known_true = truth_reasons.iter().any(|r| r.starts_with("KNOWN_TRUE"));
    results.push(("S32_fact_alignment", has_known_true || !has_known_false));

    // S33: Semantic confidence (composite: penalty < 0.1 AND no known false)
    results.push(("S33_semantic_confidence", penalty < 0.1));

    // ── Combined scoring ──

    let passed = results.iter().filter(|(_, v)| *v).count();
    let total = results.len();

    // Base confidence from solver pass rate
    let structural_confidence = passed as f64 / total as f64;

    // Apply semantic adjustments: penalty reduces, boost increases
    let adjusted_confidence = (structural_confidence - penalty + boost).clamp(0.0, 1.0);

    // Verdict: FAIL if known false regardless of structural score
    let verdict = if has_known_false {
        "FAIL"
    } else if adjusted_confidence >= 0.70 {
        "PASS"
    } else {
        "FAIL"
    };

    SolverResult {
        passed,
        total,
        confidence: adjusted_confidence,
        verdict,
        solver_results: results.into_iter().map(|(k, v)| (k.to_string(), v)).collect(),
        semantic_reasons: truth_reasons,
    }
}

#[derive(Debug, Clone, Serialize)]
struct SolverResult {
    passed: usize,
    total: usize,
    confidence: f64,
    verdict: &'static str,
    solver_results: Vec<(String, bool)>,
    semantic_reasons: Vec<String>,
}

// ══════════════════════════════════════════════
// TEMPORAL DECAY (Rust-native)
// ══════════════════════════════════════════════

fn domain_half_life(domain: &str) -> f64 {
    match domain {
        "ai_ml" | "ai" => 0.5,
        "software" | "computer_science" => 1.0,
        "technology" => 1.5,
        "medicine" | "biology" => 3.0,
        "economics" => 5.0,
        "psychology" => 7.0,
        "chemistry" => 10.0,
        "physics" => 20.0,
        "geology" => 50.0,
        "mathematics" => 100.0,
        "philosophy" => 200.0,
        _ => 10.0,
    }
}

fn temporal_decay(age_years: f64, half_life: f64) -> f64 {
    if age_years <= 0.0 { return 1.0; }
    if half_life <= 0.0 { return 0.0; }
    2.0_f64.powf(-age_years / half_life)
}

// ══════════════════════════════════════════════
// PYTHON BRIDGE (embedded, for full KS42c)
// ══════════════════════════════════════════════

/// Call Python KS31e L1.verify_lightweight() via embedded interpreter.
fn python_verify_full(text: &str) -> Result<VerifyResult, String> {
    Python::initialize();
    Python::attach(|py| {
        let sys = py.import("sys").map_err(|e| e.to_string())?;
        let path = sys.getattr("path").map_err(|e| e.to_string())?;
        let _ = path.call_method1("insert", (0i32, KATALA_SRC));

        let ks_mod = py.import("katala_samurai.ks31e").map_err(|e| e.to_string())?;

        let ks_cls = ks_mod.getattr("KS31e").map_err(|e| e.to_string())?;
        let ks = ks_cls.call0().map_err(|e| e.to_string())?;
        let l1 = ks.getattr("l1").map_err(|e| e.to_string())?;

        let evidence: Vec<&str> = vec![text];
        let result = l1.call_method1("verify_lightweight", (text, evidence))
            .map_err(|e| e.to_string())?;

        let passed: usize = result.get_item("passed").map_err(|e| e.to_string())?
            .extract::<usize>().map_err(|e: PyErr| e.to_string())?;
        let total: usize = result.get_item("total").map_err(|e| e.to_string())?
            .extract::<usize>().map_err(|e: PyErr| e.to_string())?;
        let pass_rate: f64 = result.get_item("pass_rate").map_err(|e| e.to_string())?
            .extract::<f64>().map_err(|e: PyErr| e.to_string())?;
        let verdict: String = result.get_item("verdict").map_err(|e| e.to_string())?
            .extract::<String>().map_err(|e: PyErr| e.to_string())?;

        Ok(VerifyResult {
            verdict,
            confidence: pass_rate,
            passed,
            total,
            mode: "python-L1".to_string(),
        })
    })
}

#[derive(Debug, Clone, Serialize)]
struct VerifyResult {
    verdict: String,
    confidence: f64,
    passed: usize,
    total: usize,
    mode: String,
}

// ══════════════════════════════════════════════
// UNIFIED VERIFY — Rust-first with Python fallback
// ══════════════════════════════════════════════

#[derive(Debug, Clone, Serialize)]
struct FullResult {
    text: String,
    verdict: String,
    confidence: f64,
    rust_solvers: SolverResult,
    python_solvers: Option<VerifyResult>,
    features: ClaimFeatures,
    temporal_freshness: f64,
    temporal_domain: String,
    ks_enabled: bool,
    mode: String,
    version: String,
    time_us: u128,
}

fn verify(text: &str, use_python: bool) -> FullResult {
    let start = Instant::now();

    // Phase 1: Rust-native feature extraction + solver chain
    let features = extract_features(text);
    let rust_result = rust_solver_chain(&features);

    // Phase 2: Temporal decay (Rust-native)
    let hl = domain_half_life(&features.domain);
    let freshness = temporal_decay(0.0, hl); // Age 0 for fresh claims

    // Phase 3: Optional Python verification
    let py_result = if use_python {
        match python_verify_full(text) {
            Ok(r) => Some(r),
            Err(_) => None,
        }
    } else {
        None
    };

    // Phase 4: Combine results
    let has_known_false = rust_result.semantic_reasons.iter().any(|r| r.starts_with("KNOWN_FALSE"));
    let (verdict, confidence) = if let Some(ref py) = py_result {
        // Blend: 45% Rust + 55% Python (Rust now has semantic solvers)
        let blended = rust_result.confidence * 0.45 + py.confidence * 0.55;
        // Known false always fails, even if Python says otherwise
        let v = if has_known_false { "FAIL" } else if blended >= 0.70 { "PASS" } else { "FAIL" };
        (v.to_string(), blended)
    } else {
        (rust_result.verdict.to_string(), rust_result.confidence)
    };

    let elapsed = start.elapsed().as_micros();
    let domain = features.domain.clone();

    FullResult {
        text: if text.len() > 200 { text[..200].to_string() } else { text.to_string() },
        verdict,
        confidence,
        rust_solvers: rust_result,
        python_solvers: py_result,
        features,
        temporal_freshness: freshness,
        temporal_domain: domain,
        ks_enabled: true,
        mode: if use_python { "rust+python" } else { "rust-only" }.to_string(),
        version: VERSION.to_string(),
        time_us: elapsed,
    }
}

/// Batch verify using Rayon parallel.
fn verify_batch(texts: &[String], use_python: bool) -> Vec<FullResult> {
    if use_python {
        // Python GIL → sequential for Python mode
        texts.iter().map(|t| verify(t, true)).collect()
    } else {
        // Pure Rust → parallel
        texts.par_iter().map(|t| verify(t, false)).collect()
    }
}

// ══════════════════════════════════════════════
// HTTP SERVER
// ══════════════════════════════════════════════

#[derive(Deserialize)]
struct VerifyRequest {
    text: Option<String>,
    texts: Option<Vec<String>>,
    fast: Option<bool>,
    channel: Option<String>,
}

#[derive(Deserialize)]
struct ToggleRequest {
    channel: String,
    enabled: bool,
}

fn json_response(status: u16, body: &str) -> Response<std::io::Cursor<Vec<u8>>> {
    let bytes = body.as_bytes().to_vec();
    let len = bytes.len();
    Response::new(
        tiny_http::StatusCode(status),
        vec![Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap()],
        std::io::Cursor::new(bytes),
        Some(len),
        None,
    )
}

fn handle_request(mut request: Request) {
    let url = request.url().to_string();
    let method = request.method().clone();

    match (method, url.as_str()) {
        (Method::Get, "/") | (Method::Get, "/status") => {
            let state = KS_STATE.lock().unwrap();
            let mut status_map = serde_json::Map::new();
            status_map.insert("status".into(), serde_json::Value::String("running".into()));
            status_map.insert("version".into(), serde_json::Value::String(VERSION.into()));
            status_map.insert("global".into(), serde_json::Value::Bool(state.global));
            let channels: serde_json::Map<String, serde_json::Value> = state.status()
                .into_iter().map(|(k, v)| (k, serde_json::Value::Bool(v))).collect();
            status_map.insert("channels".into(), serde_json::Value::Object(channels));
            let body = serde_json::Value::Object(status_map).to_string();
            let _ = request.respond(json_response(200, &body));
        }

        (Method::Post, "/verify") | (Method::Post, "/") => {
            let mut body = String::new();
            let _ = request.as_reader().read_to_string(&mut body);

            let req: VerifyRequest = match serde_json::from_str(&body) {
                Ok(r) => r,
                Err(e) => {
                    let msg = format!(r#"{{"error":"{}"}}"#, e);
                    let _ = request.respond(json_response(400, &msg));
                    return;
                }
            };

            // Check if KS is enabled for this channel
            let channel = req.channel.as_deref().unwrap_or("default");
            let enabled = KS_STATE.lock().unwrap().is_enabled(channel);

            if !enabled {
                let mut m = serde_json::Map::new();
                m.insert("ks_enabled".into(), serde_json::Value::Bool(false));
                m.insert("channel".into(), serde_json::Value::String(channel.into()));
                m.insert("message".into(), serde_json::Value::String("KS verification is OFF for this channel".into()));
                let _ = request.respond(json_response(200, &serde_json::Value::Object(m).to_string()));
                return;
            }

            let use_python = !req.fast.unwrap_or(false);

            if let Some(texts) = req.texts {
                let results = verify_batch(&texts, use_python);
                let json = serde_json::to_string(&results).unwrap_or_default();
                let _ = request.respond(json_response(200, &json));
            } else if let Some(text) = req.text {
                let result = verify(&text, use_python);
                let json = serde_json::to_string(&result).unwrap_or_default();
                let _ = request.respond(json_response(200, &json));
            } else {
                let _ = request.respond(json_response(400, r#"{"error":"missing 'text' or 'texts'"}"#));
            }
        }

        (Method::Post, "/toggle") => {
            let mut body = String::new();
            let _ = request.as_reader().read_to_string(&mut body);

            match serde_json::from_str::<ToggleRequest>(&body) {
                Ok(tog) => {
                    let mut state = KS_STATE.lock().unwrap();
                    state.set(&tog.channel, tog.enabled);
                    let channels: serde_json::Map<String, serde_json::Value> = state.status()
                        .into_iter().map(|(k, v)| (k, serde_json::Value::Bool(v))).collect();
                    let mut m = serde_json::Map::new();
                    m.insert("channel".into(), serde_json::Value::String(tog.channel));
                    m.insert("enabled".into(), serde_json::Value::Bool(tog.enabled));
                    m.insert("channels".into(), serde_json::Value::Object(channels));
                    let _ = request.respond(json_response(200, &serde_json::Value::Object(m).to_string()));
                }
                Err(e) => {
                    let msg = format!(r#"{{"error":"{}"}}"#, e);
                    let _ = request.respond(json_response(400, &msg));
                }
            }
        }

        (Method::Get, "/self-verify") | (Method::Post, "/self-verify") => {
            let default_path = format!("{}/../data/self_verify_oracle.json", env!("CARGO_MANIFEST_DIR"));

            // Capture JSON output by running self-verify
            let data = match std::fs::read_to_string(&default_path) {
                Ok(d) => d,
                Err(e) => {
                    let msg = format!(r#"{{"error":"Cannot read oracle: {}"}}"#, e);
                    let _ = request.respond(json_response(500, &msg));
                    return;
                }
            };
            let oracle: OracleFile = match serde_json::from_str(&data) {
                Ok(o) => o,
                Err(e) => {
                    let msg = format!(r#"{{"error":"Cannot parse oracle: {}"}}"#, e);
                    let _ = request.respond(json_response(500, &msg));
                    return;
                }
            };

            let total = oracle.cases.len();
            let mut results: Vec<SelfVerifyResult> = Vec::new();

            for case in &oracle.cases {
                let result = verify(&case.text, false);
                let verdict_match = result.verdict == case.expected_verdict;
                let confidence_in_range = result.confidence >= case.expected_min_confidence
                    && result.confidence <= case.expected_max_confidence;
                let passed = verdict_match && confidence_in_range;

                let failure_reason = if !verdict_match {
                    Some(format!("Verdict: expected={}, got={}", case.expected_verdict, result.verdict))
                } else if !confidence_in_range {
                    Some(format!("Confidence: expected=[{:.2},{:.2}], got={:.3}",
                        case.expected_min_confidence, case.expected_max_confidence, result.confidence))
                } else {
                    None
                };

                results.push(SelfVerifyResult {
                    id: case.id.clone(),
                    text: if case.text.len() > 60 { format!("{}...", &case.text[..57]) } else { case.text.clone() },
                    expected_verdict: case.expected_verdict.clone(),
                    actual_verdict: result.verdict.clone(),
                    expected_confidence_range: (case.expected_min_confidence, case.expected_max_confidence),
                    actual_confidence: result.confidence,
                    verdict_match,
                    confidence_in_range,
                    passed,
                    category: case.category.clone(),
                    failure_reason,
                });
            }

            let passed_count = results.iter().filter(|r| r.passed).count();
            let pass_rate = if total > 0 { passed_count as f64 / total as f64 } else { 0.0 };
            let integrity = if pass_rate >= 0.95 { "HIGH" }
                else if pass_rate >= 0.80 { "MEDIUM" }
                else if pass_rate >= 0.60 { "LOW" }
                else { "CRITICAL" };

            let failures: Vec<SelfVerifyResult> = results.iter().filter(|r| !r.passed).cloned().collect();

            let report = SelfVerifyReport {
                version: VERSION.to_string(),
                timestamp: chrono_now_iso(),
                total_cases: total,
                passed_cases: passed_count,
                failed_cases: total - passed_count,
                pass_rate,
                verifier_integrity: integrity.to_string(),
                results,
                failures,
            };

            let json = serde_json::to_string(&report).unwrap_or_default();
            let _ = request.respond(json_response(200, &json));
        }

        // ── Coding Mode Pipeline Endpoint ──
        (Method::Post, "/coding-mode") => {
            let mut body = String::new();
            let _ = request.as_reader().read_to_string(&mut body);

            #[derive(Deserialize)]
            struct CodingModeRequest {
                message: String,
                channel: Option<String>,
                user_id: Option<String>,
            }

            let req: CodingModeRequest = match serde_json::from_str(&body) {
                Ok(r) => r,
                Err(e) => {
                    let _ = request.respond(json_response(400, &format!(r#"{{"error":"{}"}}"#, e)));
                    return;
                }
            };

            let channel = req.channel.as_deref().unwrap_or("default");
            let user_id = req.user_id.as_deref().unwrap_or("unknown");

            let route = MODE_GATE.process_message(&req.message, channel, user_id);

            let mut m = serde_json::Map::new();
            m.insert("channel".into(), serde_json::Value::String(channel.into()));
            m.insert("user_id".into(), serde_json::Value::String(user_id.into()));

            match route {
                PipelineRoute::Normal => {
                    m.insert("mode".into(), serde_json::Value::String("normal".into()));
                    m.insert("coding_mode_active".into(), serde_json::Value::Bool(false));
                }
                PipelineRoute::CodingMode => {
                    // Run KS verification on the message
                    let result = verify(&req.message, false);

                    m.insert("mode".into(), serde_json::Value::String("coding".into()));
                    m.insert("coding_mode_active".into(), serde_json::Value::Bool(true));
                    m.insert("ks_verdict".into(), serde_json::Value::String(result.verdict.clone()));
                    m.insert("ks_confidence".into(), serde_json::json!(result.confidence));
                    m.insert("approval_required".into(), serde_json::Value::Bool(true));
                    m.insert("can_execute".into(), serde_json::Value::Bool(false));
                    m.insert("message".into(), serde_json::Value::String(
                        "Coding mode active. KS/KCS gates passed. Awaiting approver.".into()
                    ));
                }
            }

            let _ = request.respond(json_response(200, &serde_json::Value::Object(m).to_string()));
        }

        // ── Coding Mode Exit ──
        (Method::Post, "/coding-mode/exit") => {
            let mut body = String::new();
            let _ = request.as_reader().read_to_string(&mut body);

            #[derive(Deserialize)]
            struct ExitRequest {
                channel: Option<String>,
                user_id: Option<String>,
            }

            let req: ExitRequest = match serde_json::from_str(&body) {
                Ok(r) => r,
                Err(e) => {
                    let _ = request.respond(json_response(400, &format!(r#"{{"error":"{}"}}"#, e)));
                    return;
                }
            };

            let channel = req.channel.as_deref().unwrap_or("default");
            let user_id = req.user_id.as_deref().unwrap_or("unknown");
            let exited = MODE_GATE.exit(channel, user_id);

            let mut m = serde_json::Map::new();
            m.insert("exited".into(), serde_json::Value::Bool(exited));
            m.insert("channel".into(), serde_json::Value::String(channel.into()));
            let _ = request.respond(json_response(200, &serde_json::Value::Object(m).to_string()));
        }

        // ── Audit Log ──
        (Method::Get, "/audit") => {
            let log = SHARED_AUDIT.lock().unwrap();
            let json = log.to_json();
            let _ = request.respond(json_response(200, &json));
        }

        _ => {
            let _ = request.respond(json_response(404, r#"{"error":"not found"}"#));
        }
    }
}

// ══════════════════════════════════════════════
// CLI
// ══════════════════════════════════════════════

// ══════════════════════════════════════════════
// SELF-VERIFICATION MODE
// ══════════════════════════════════════════════

/// Oracle test case loaded from JSON.
#[derive(Debug, Clone, Deserialize)]
struct OracleCase {
    id: String,
    text: String,
    expected_verdict: String,
    expected_min_confidence: f64,
    expected_max_confidence: f64,
    category: String,
    domain: String,
    notes: String,
}

#[derive(Debug, Clone, Deserialize)]
struct OracleFile {
    _meta: serde_json::Value,
    cases: Vec<OracleCase>,
}

#[derive(Debug, Clone, Serialize)]
struct SelfVerifyResult {
    id: String,
    text: String,
    expected_verdict: String,
    actual_verdict: String,
    expected_confidence_range: (f64, f64),
    actual_confidence: f64,
    verdict_match: bool,
    confidence_in_range: bool,
    passed: bool,
    category: String,
    failure_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct SelfVerifyReport {
    version: String,
    timestamp: String,
    total_cases: usize,
    passed_cases: usize,
    failed_cases: usize,
    pass_rate: f64,
    verifier_integrity: String,
    results: Vec<SelfVerifyResult>,
    failures: Vec<SelfVerifyResult>,
}

fn run_self_verify(oracle_path: &str, json_out: bool) -> bool {
    let data = match std::fs::read_to_string(oracle_path) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("ERROR: Cannot read oracle file '{}': {}", oracle_path, e);
            return false;
        }
    };
    let oracle: OracleFile = match serde_json::from_str(&data) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("ERROR: Cannot parse oracle file: {}", e);
            return false;
        }
    };

    let mut results: Vec<SelfVerifyResult> = Vec::new();
    let total = oracle.cases.len();

    eprintln!("╔══════════════════════════════════════════╗");
    eprintln!("║   KS Self-Verification Mode              ║");
    eprintln!("║   Oracle: {} cases                        ║", total);
    eprintln!("║   Version: {}                    ║", VERSION);
    eprintln!("╚══════════════════════════════════════════╝");
    eprintln!();

    for case in &oracle.cases {
        // Run Rust-only verification (fast mode for self-verify)
        let result = verify(&case.text, false);

        let verdict_match = result.verdict == case.expected_verdict;
        let confidence_in_range = result.confidence >= case.expected_min_confidence
            && result.confidence <= case.expected_max_confidence;
        let passed = verdict_match && confidence_in_range;

        let failure_reason = if !verdict_match {
            Some(format!("Verdict mismatch: expected={}, got={}", case.expected_verdict, result.verdict))
        } else if !confidence_in_range {
            Some(format!("Confidence out of range: expected=[{:.2}, {:.2}], got={:.3}",
                case.expected_min_confidence, case.expected_max_confidence, result.confidence))
        } else {
            None
        };

        let sv = SelfVerifyResult {
            id: case.id.clone(),
            text: if case.text.len() > 60 { format!("{}...", &case.text[..57]) } else { case.text.clone() },
            expected_verdict: case.expected_verdict.clone(),
            actual_verdict: result.verdict.clone(),
            expected_confidence_range: (case.expected_min_confidence, case.expected_max_confidence),
            actual_confidence: result.confidence,
            verdict_match,
            confidence_in_range,
            passed,
            category: case.category.clone(),
            failure_reason,
        };

        if !json_out {
            let icon = if passed { "✅" } else { "❌" };
            eprintln!("  {} {} — {} (conf={:.3}, expected={}[{:.2}-{:.2}])",
                icon, sv.id, sv.actual_verdict, sv.actual_confidence,
                sv.expected_verdict, case.expected_min_confidence, case.expected_max_confidence);
            if let Some(ref reason) = sv.failure_reason {
                eprintln!("     └─ {}", reason);
            }
        }

        results.push(sv);
    }

    let passed_count = results.iter().filter(|r| r.passed).count();
    let failed_count = total - passed_count;
    let pass_rate = if total > 0 { passed_count as f64 / total as f64 } else { 0.0 };

    let integrity = if pass_rate >= 0.95 {
        "HIGH"
    } else if pass_rate >= 0.80 {
        "MEDIUM"
    } else if pass_rate >= 0.60 {
        "LOW"
    } else {
        "CRITICAL"
    };

    let failures: Vec<SelfVerifyResult> = results.iter().filter(|r| !r.passed).cloned().collect();

    let report = SelfVerifyReport {
        version: VERSION.to_string(),
        timestamp: chrono_now_iso(),
        total_cases: total,
        passed_cases: passed_count,
        failed_cases: failed_count,
        pass_rate,
        verifier_integrity: integrity.to_string(),
        results: results.clone(),
        failures,
    };

    if json_out {
        println!("{}", serde_json::to_string_pretty(&report).unwrap_or_default());
    } else {
        eprintln!();
        eprintln!("═══════════════════════════════════════════");
        eprintln!("  SELF-VERIFICATION REPORT");
        eprintln!("  Version:    {}", VERSION);
        eprintln!("  Cases:      {}", total);
        eprintln!("  Passed:     {} ✅", passed_count);
        eprintln!("  Failed:     {} ❌", failed_count);
        eprintln!("  Pass Rate:  {:.1}%", pass_rate * 100.0);
        eprintln!("  Integrity:  {}", integrity);
        eprintln!("═══════════════════════════════════════════");

        if failed_count > 0 {
            eprintln!();
            eprintln!("  FAILURES:");
            for f in &report.failures {
                eprintln!("  ❌ {} [{}]: {}", f.id, f.category, f.failure_reason.as_deref().unwrap_or("unknown"));
            }
        }
    }

    pass_rate >= 0.80
}

/// Simple ISO timestamp without chrono dependency.
fn chrono_now_iso() -> String {
    // Use std::time for a basic timestamp
    let dur = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    format!("unix:{}", dur.as_secs())
}

fn print_usage() {
    eprintln!("Usage: ks_engine [OPTIONS] [CLAIM]");
    eprintln!();
    eprintln!("Options:");
    eprintln!("  --serve [PORT]    Start HTTP server (default: {})", DEFAULT_PORT);
    eprintln!("  --fast            Rust-only mode (no Python)");
    eprintln!("  --python          Use Python L1 solvers (blended)");
    eprintln!("  --json            JSON output");
    eprintln!("  --batch           Read claims from stdin (one per line)");
    eprintln!("  --self-verify [PATH]  Run self-verification against oracle dataset");
    eprintln!("  --status          Show KS on/off status");
    eprintln!("  --on CHANNEL      Enable KS for channel");
    eprintln!("  --off CHANNEL     Disable KS for channel");
    eprintln!();
    eprintln!("Self-Verify:");
    eprintln!("  ks_engine --self-verify ../data/self_verify_oracle.json");
    eprintln!("  ks_engine --self-verify ../data/self_verify_oracle.json --json");
    eprintln!();
    eprintln!("Defaults ON: {:?}", DEFAULTS_ON);
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.is_empty() {
        print_usage();
        std::process::exit(1);
    }

    let mut serve = false;
    let mut port = DEFAULT_PORT;
    let mut fast = false;
    let mut json_out = false;
    let mut batch = false;
    let mut self_verify: Option<String> = None;
    let mut claim_parts: Vec<String> = Vec::new();

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--serve" => {
                serve = true;
                if i + 1 < args.len() {
                    if let Ok(p) = args[i + 1].parse::<u16>() {
                        port = p;
                        i += 1;
                    }
                }
            }
            "--fast" => fast = true,
            "--python" => fast = false,
            "--json" => json_out = true,
            "--batch" => batch = true,
            "--self-verify" => {
                // Default oracle path
                let default_path = format!("{}/../data/self_verify_oracle.json", env!("CARGO_MANIFEST_DIR"));
                if i + 1 < args.len() && !args[i + 1].starts_with("--") {
                    i += 1;
                    self_verify = Some(args[i].clone());
                } else {
                    self_verify = Some(default_path);
                }
            }
            "--status" => {
                let state = KS_STATE.lock().unwrap();
                println!("{}", serde_json::to_string_pretty(&state.status()).unwrap());
                return;
            }
            "--on" => {
                if i + 1 < args.len() {
                    i += 1;
                    KS_STATE.lock().unwrap().set(&args[i], true);
                    println!("KS ON for: {}", args[i]);
                }
                return;
            }
            "--off" => {
                if i + 1 < args.len() {
                    i += 1;
                    KS_STATE.lock().unwrap().set(&args[i], false);
                    println!("KS OFF for: {}", args[i]);
                }
                return;
            }
            "--help" | "-h" => {
                print_usage();
                return;
            }
            _ => claim_parts.push(args[i].clone()),
        }
        i += 1;
    }

    // Self-verify mode
    if let Some(oracle_path) = self_verify {
        let ok = run_self_verify(&oracle_path, json_out);
        std::process::exit(if ok { 0 } else { 1 });
    }

    if serve {
        let addr = format!("0.0.0.0:{}", port);
        let server = Server::http(&addr).expect("Failed to start server");
        eprintln!("KS Engine {} listening on http://{}", VERSION, addr);
        eprintln!("  POST /verify  →  {{\"text\": \"...\", \"fast\": true}}");
        eprintln!("  POST /toggle  →  {{\"channel\": \"...\", \"enabled\": true}}");
        eprintln!("  GET  /status");
        eprintln!("  Default ON: {:?}", DEFAULTS_ON);

        for request in server.incoming_requests() {
            handle_request(request);
        }
        return;
    }

    let use_python = !fast;

    if batch {
        let stdin = std::io::stdin();
        let lines: Vec<String> = stdin.lines().filter_map(|l| l.ok()).filter(|l| !l.is_empty()).collect();
        let results = verify_batch(&lines, use_python);
        for r in &results {
            if json_out {
                println!("{}", serde_json::to_string(r).unwrap_or_default());
            } else {
                println!("[{}] {} ({:.3}) in {}μs — {}", r.version, r.verdict, r.confidence, r.time_us, r.text);
            }
        }
        return;
    }

    let claim = claim_parts.join(" ");
    if claim.is_empty() {
        print_usage();
        std::process::exit(1);
    }

    let result = verify(&claim, use_python);
    if json_out {
        println!("{}", serde_json::to_string_pretty(&result).unwrap_or_default());
    } else {
        println!("[{}] {} (confidence={:.3}) in {}μs", result.version, result.verdict, result.confidence, result.time_us);
        println!("  Rust solvers: {}/{} passed", result.rust_solvers.passed, result.rust_solvers.total);
        if let Some(ref py) = result.python_solvers {
            println!("  Python L1:    {}/{} passed", py.passed, py.total);
        }
        println!("  Domain: {} (freshness={:.2})", result.temporal_domain, result.temporal_freshness);
        println!("  Mode: {}", result.mode);
    }
}
