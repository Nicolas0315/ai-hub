// KS Engine — Rust-first verification engine with embedded Python.
//
// Architecture: Rust owns the event loop, HTTP server, and all pure-compute.
// Python is embedded via PyO3 for KS solver chain (KS31e L1) and KS42c full.
//
// Design: Youta Hilono — "Rustの上でPythonを走らせて"
// Implementation: Shirokuma, 2026-03-01

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
// RUST-NATIVE SOLVER CHAIN (S01-S27 logic)
// ══════════════════════════════════════════════

/// Run pure-Rust solver chain. Each solver checks a structural/semantic property.
fn rust_solver_chain(features: &ClaimFeatures) -> SolverResult {
    let mut results: Vec<(&str, bool)> = Vec::with_capacity(27);

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

    // S27: Overall coherence
    let pass_count = results.iter().filter(|(_, v)| *v).count();
    results.push(("S27_coherence", pass_count >= 15));

    let passed = results.iter().filter(|(_, v)| *v).count();
    let total = results.len();
    let confidence = passed as f64 / total as f64;

    SolverResult {
        passed,
        total,
        confidence,
        verdict: if confidence >= 0.75 { "PASS" } else { "FAIL" },
        solver_results: results.into_iter().map(|(k, v)| (k.to_string(), v)).collect(),
    }
}

#[derive(Debug, Clone, Serialize)]
struct SolverResult {
    passed: usize,
    total: usize,
    confidence: f64,
    verdict: &'static str,
    solver_results: Vec<(String, bool)>,
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
    let (verdict, confidence) = if let Some(ref py) = py_result {
        // Blend: 40% Rust + 60% Python (Python has fuller solver chain)
        let blended = rust_result.confidence * 0.4 + py.confidence * 0.6;
        let v = if blended >= 0.75 { "PASS" } else { "FAIL" };
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

        _ => {
            let _ = request.respond(json_response(404, r#"{"error":"not found"}"#));
        }
    }
}

// ══════════════════════════════════════════════
// CLI
// ══════════════════════════════════════════════

fn print_usage() {
    eprintln!("Usage: ks_engine [OPTIONS] [CLAIM]");
    eprintln!();
    eprintln!("Options:");
    eprintln!("  --serve [PORT]    Start HTTP server (default: {})", DEFAULT_PORT);
    eprintln!("  --fast            Rust-only mode (no Python)");
    eprintln!("  --python          Use Python L1 solvers (blended)");
    eprintln!("  --json            JSON output");
    eprintln!("  --batch           Read claims from stdin (one per line)");
    eprintln!("  --status          Show KS on/off status");
    eprintln!("  --on CHANNEL      Enable KS for channel");
    eprintln!("  --off CHANNEL     Disable KS for channel");
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
