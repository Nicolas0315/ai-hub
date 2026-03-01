use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
type PyObject = Py<PyAny>;
use rayon::prelude::*;
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;
use std::time::{SystemTime, UNIX_EPOCH};

// ══════════════════════════════════════════════
// MODULE 1: CLAIM CLASSIFIER (LazyLock regex)
// ══════════════════════════════════════════════

struct ClaimPatterns {
    patterns: Vec<(&'static str, Vec<Regex>)>,
}

static COMPILED: LazyLock<ClaimPatterns> = LazyLock::new(|| {
    let raw: Vec<(&str, Vec<&str>)> = vec![
        ("causal", vec![
            r"\bcaus(?:es?|ed|ing|al)\b", r"\bleads?\s+to\b", r"\bresults?\s+in\b",
            r"\bbecause\b", r"\bdue\s+to\b", r"\beffect\s+of\b", r"\btrigger",
            r"\binduc(?:es?|ed)\b",
        ]),
        ("statistical", vec![
            r"(?i)\bp[\-\s]?value\b", r"\bsignifican(?:t|ce)\b", r"\bcorrelat",
            r"\bsample\s+size\b", r"\bn\s*=\s*\d+", r"\beffect\s+size\b",
            r"\bconfidence\s+interval\b", r"\bregression\b",
        ]),
        ("definitional", vec![
            r"\bis\s+(?:defined|the)\b", r"\bmeans?\s+that\b", r"\brefers?\s+to\b",
            r"\bby\s+definition\b", r"\bis\s+known\s+as\b",
        ]),
        ("empirical", vec![
            r"\bstudy\b", r"\bresearch\b", r"\bexperiment\b", r"\bobserv(?:e|ed|ation)\b",
            r"\bdata\s+show", r"\bevidence\b", r"\bmeasur(?:e|ed|ement)\b",
        ]),
        ("logical", vec![
            r"\btherefore\b", r"\bthus\b", r"\bhence\b", r"\bit\s+follows\b",
            r"\bnecessarily\b",
        ]),
        ("normative", vec![
            r"\bshould\b", r"\bmust\b", r"\bought\b", r"\bbetter\s+to\b",
            r"\bethical\b", r"\bmoral\b",
        ]),
        ("historical", vec![
            r"\bin\s+\d{3,4}\b", r"\bcentury\b", r"\bhistor(?:y|ical)\b",
            r"\bfounded\b", r"\binvent(?:ed|ion)\b",
        ]),
    ];
    ClaimPatterns {
        patterns: raw.into_iter().map(|(name, pats)| {
            let compiled: Vec<Regex> = pats.into_iter().filter_map(|p| Regex::new(p).ok()).collect();
            (name, compiled)
        }).collect()
    }
});

#[pyfunction]
fn classify_claim(text: &str) -> PyResult<HashMap<String, f64>> {
    let text_lower = text.to_lowercase();
    let mut scores: HashMap<String, f64> = HashMap::new();
    for (ctype, regexes) in &COMPILED.patterns {
        let hits: usize = regexes.iter().filter(|re| re.is_match(&text_lower)).count();
        if hits > 0 {
            let threshold = (regexes.len() as f64 * 0.4).max(3.0);
            scores.insert(ctype.to_string(), (hits as f64 / threshold).min(1.0));
        }
    }
    if scores.is_empty() { scores.insert("unknown".into(), 1.0); }
    let total: f64 = scores.values().sum();
    for v in scores.values_mut() { *v = (*v / total * 1000.0).round() / 1000.0; }
    Ok(scores)
}

// ══════════════════════════════════════════════
// MODULE 2: LATERAL INHIBITION
// ══════════════════════════════════════════════

#[pyfunction]
fn lateral_inhibit(confidences: Vec<f64>, threshold: f64) -> PyResult<Vec<f64>> {
    let n = confidences.len();
    if n < 2 { return Ok(confidences); }
    let mut suppression = vec![0.0_f64; n];
    for i in 0..n {
        if confidences[i] < threshold { continue; }
        for j in 0..n {
            if j == i { continue; }
            if (confidences[i] > 0.65 && confidences[j] < 0.35)
                || (confidences[i] < 0.35 && confidences[j] > 0.65) {
                if confidences[j] < confidences[i] {
                    suppression[j] += (confidences[i] - confidences[j]) * 0.5;
                }
            }
        }
    }
    Ok(confidences.iter().zip(suppression.iter())
        .map(|(c, s)| ((c - s).max(0.1) * 10000.0).round() / 10000.0).collect())
}

// ══════════════════════════════════════════════
// MODULE 3: FEATURE EXTRACTION
// ══════════════════════════════════════════════

#[pyfunction]
fn extract_features(text: &str) -> PyResult<HashMap<String, String>> {
    // Legacy compatibility: returns string-encoded values
    let lower = text.to_lowercase();
    let words: HashSet<&str> = lower.split_whitespace().collect();
    let neg: HashSet<&str> = ["not","never","no","neither","without","none"].into();
    let cau: HashSet<&str> = ["cause","causes","caused","because","effect","leads","results"].into();
    let sta: HashSet<&str> = ["significant","correlation","sample","regression"].into();
    let def: HashSet<&str> = ["defined","means","refers","definition","known"].into();
    let mut f: HashMap<String, String> = HashMap::new();
    f.insert("word_count".into(), words.len().to_string());
    f.insert("char_count".into(), text.len().to_string());
    f.insert("has_numbers".into(), text.chars().any(|c| c.is_ascii_digit()).to_string());
    f.insert("has_negation".into(), words.iter().any(|w| neg.contains(w)).to_string());
    f.insert("has_causal".into(), words.iter().any(|w| cau.contains(w)).to_string());
    f.insert("has_statistical".into(), words.iter().any(|w| sta.contains(w)).to_string());
    f.insert("has_definition".into(), words.iter().any(|w| def.contains(w)).to_string());
    f.insert("sentence_count".into(),
        text.chars().filter(|c| *c=='.'||*c=='!'||*c=='?').count().max(1).to_string());
    Ok(f)
}

// ══════════════════════════════════════════════
// MODULE 4: BOOTSTRAP CONFIDENCE (Rayon parallel)
// ══════════════════════════════════════════════

#[pyfunction]
fn bootstrap_confidence(scores: Vec<f64>, n_samples: usize, sample_ratio: f64) -> PyResult<HashMap<String, f64>> {
    if scores.is_empty() {
        let mut r = HashMap::new();
        r.insert("mean".into(), 0.5); r.insert("std".into(), 0.25);
        r.insert("ci_low".into(), 0.25); r.insert("ci_high".into(), 0.75);
        return Ok(r);
    }
    let n = scores.len();
    let k = ((n as f64 * sample_ratio) as usize).max(1);
    let means: Vec<f64> = (0..n_samples).into_par_iter().map(|seed| {
        let mut rng = seed as u64 ^ 0xdeadbeef;
        let mut sum = 0.0;
        for _ in 0..k {
            rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            sum += scores[(rng >> 33) as usize % n];
        }
        sum / k as f64
    }).collect();
    let mean: f64 = means.iter().sum::<f64>() / means.len() as f64;
    let var: f64 = means.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / means.len() as f64;
    let mut sorted = means; sorted.sort_by(|a,b| a.partial_cmp(b).unwrap());
    let mut r = HashMap::new();
    r.insert("mean".into(), (mean*10000.0).round()/10000.0);
    r.insert("std".into(), (var.sqrt()*10000.0).round()/10000.0);
    r.insert("ci_low".into(), (sorted[(n_samples as f64*0.025) as usize]*10000.0).round()/10000.0);
    r.insert("ci_high".into(), (sorted[(n_samples as f64*0.975) as usize]*10000.0).round()/10000.0);
    Ok(r)
}

// ══════════════════════════════════════════════
// MODULE 5: COHERENCE CHECK
// ══════════════════════════════════════════════

#[pyfunction]
fn check_coherence(confidences: Vec<f64>) -> PyResult<HashMap<String, f64>> {
    let n = confidences.len();
    if n < 2 {
        let mut r = HashMap::new();
        r.insert("coherence".into(), 1.0); r.insert("conflicts".into(), 0.0);
        return Ok(r);
    }
    let mut conflicts = 0_usize;
    let mut support = 0_usize;
    for i in 0..n {
        for j in (i+1)..n {
            if (confidences[i]>0.65 && confidences[j]<0.35) || (confidences[i]<0.35 && confidences[j]>0.65) {
                conflicts += 1;
            } else if (confidences[i]-confidences[j]).abs() < 0.2 {
                support += 1;
            }
        }
    }
    let max_p = n*(n-1)/2;
    let coh = (1.0 - conflicts as f64 / max_p.max(1) as f64 * 2.0).max(0.0);
    let mut r = HashMap::new();
    r.insert("coherence".into(), (coh*10000.0).round()/10000.0);
    r.insert("conflicts".into(), conflicts as f64);
    r.insert("support_pairs".into(), support as f64);
    r.insert("modifier".into(), if coh<0.5 {((-0.1*(1.0-coh))*10000.0).round()/10000.0} else {0.0});
    Ok(r)
}

// ══════════════════════════════════════════════
// MODULE 6: REASON SPACE (full port from Python)
// ══════════════════════════════════════════════

static WORD_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\b\w+\b").unwrap());
static POS_VERDICTS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| 
    ["VERIFIED","TRUE","PASS","CONSISTENT"].into());
static NEG_VERDICTS: LazyLock<HashSet<&'static str>> = LazyLock::new(||
    ["UNVERIFIED","FALSE","FAIL","INCONSISTENT"].into());

#[pyfunction]
fn reason_space_analyze(
    solvers: Vec<String>,
    reasons: Vec<String>,
    confidences: Vec<f64>,
    verdicts: Vec<String>,
) -> PyResult<HashMap<String, String>> {
    // Returns JSON-encoded strings for complex types, f64 as string for simple
    let n = solvers.len();
    if n < 2 {
        let mut r: HashMap<String, String> = HashMap::new();
        r.insert("coherence".into(), "1.0".into());
        r.insert("conflict_count".into(), "0".into());
        r.insert("support_pairs".into(), "0".into());
        r.insert("isolated_solvers".into(), "[]".into());
        r.insert("confidence_modifier".into(), "0.0".into());
        r.insert("assessment".into(), "COHERENT".into());
        r.insert("conflicts".into(), "[]".into());
        return Ok(r);
    }

    let reason_words: Vec<HashSet<String>> = reasons.iter().map(|r| {
        WORD_RE.find_iter(&r.to_lowercase())
            .map(|m| m.as_str().to_string())
            .collect()
    }).collect();

    let verdict_upper: Vec<String> = verdicts.iter().map(|v| v.to_uppercase()).collect();

    let mut conflicts = 0_usize;
    let mut conflict_list: Vec<String> = Vec::new();
    let mut support_set: HashSet<usize> = HashSet::new();
    let mut support_count = 0_usize;

    for i in 0..n {
        for j in (i+1)..n {
            let c1 = confidences[i];
            let c2 = confidences[j];
            if (c1 > 0.7 && c2 < 0.3) || (c1 < 0.3 && c2 > 0.7) {
                conflicts += 1;
                if conflict_list.len() < 5 {
                    conflict_list.push(format!(
                        r#"{{"solvers":["{}","{}"],"reason":"directional_opposition","severity":"high"}}"#,
                        solvers[i], solvers[j]));
                }
                continue;
            }
            let v1_pos = POS_VERDICTS.iter().any(|p| verdict_upper[i].contains(p));
            let v1_neg = NEG_VERDICTS.iter().any(|p| verdict_upper[i].contains(p));
            let v2_pos = POS_VERDICTS.iter().any(|p| verdict_upper[j].contains(p));
            let v2_neg = NEG_VERDICTS.iter().any(|p| verdict_upper[j].contains(p));
            if (v1_pos && v2_neg) || (v1_neg && v2_pos) {
                conflicts += 1;
                if conflict_list.len() < 5 {
                    conflict_list.push(format!(
                        r#"{{"solvers":["{}","{}"],"reason":"verdict_contradiction","severity":"medium"}}"#,
                        solvers[i], solvers[j]));
                }
                continue;
            }
            let overlap = reason_words[i].intersection(&reason_words[j]).count();
            if overlap >= 3 && (c1 - c2).abs() < 0.2 {
                support_set.insert(i);
                support_set.insert(j);
                support_count += 1;
            }
        }
    }

    let all_solvers: HashSet<usize> = (0..n).collect();
    let isolated: Vec<&String> = all_solvers.difference(&support_set)
        .map(|&i| &solvers[i]).collect();

    let max_pairs = n * (n - 1) / 2;
    let conflict_ratio = conflicts as f64 / max_pairs.max(1) as f64;
    let isolation_ratio = isolated.len() as f64 / n.max(1) as f64;
    let coherence = (1.0 - conflict_ratio * 2.0 - isolation_ratio * 0.5).max(0.0);

    let mut modifier = 0.0;
    if coherence < 0.5 { modifier = -0.1 * (1.0 - coherence); }
    if conflicts >= 3 { modifier -= 0.05; }

    let assessment = if coherence > 0.7 { "COHERENT" }
        else if coherence > 0.4 { "PARTIALLY_COHERENT" }
        else { "INCOHERENT" };

    let mut r: HashMap<String, String> = HashMap::new();
    r.insert("coherence".into(), format!("{}", (coherence*10000.0).round()/10000.0));
    r.insert("conflicts".into(), format!("[{}]", conflict_list.join(",")));
    r.insert("conflict_count".into(), conflicts.to_string());
    r.insert("isolated_solvers".into(), format!("[{}]", isolated.iter().map(|s| format!("\"{}\"", s)).collect::<Vec<_>>().join(",")));
    r.insert("support_pairs".into(), support_count.to_string());
    r.insert("confidence_modifier".into(), format!("{}", (modifier*10000.0).round()/10000.0));
    r.insert("assessment".into(), assessment.into());
    Ok(r)
}

// ══════════════════════════════════════════════
// MODULE 7: NEUROMODULATION (full port)
// ══════════════════════════════════════════════

#[pyfunction]
fn neuromodulate(
    claim_type: &str,
    difficulty: &str,
    prediction_error: f64,
    novelty: f64,
) -> PyResult<HashMap<String, f64>> {
    let mut attention: f64;
    let mut threshold: f64;
    let mut learning_rate: f64;

    if prediction_error > 0.2 || novelty > 0.7 {
        attention = (1.0 + prediction_error * 2.0).min(2.0);
        threshold = (0.5 - novelty * 0.2).max(0.3);
        learning_rate = (1.0 + novelty).min(2.0);
    } else {
        attention = (1.0 - (1.0 - novelty) * 0.3).max(0.5);
        threshold = (0.5 + (1.0 - novelty) * 0.2).min(0.7);
        learning_rate = (1.0 - (1.0 - novelty) * 0.3).max(0.5);
    }

    let caution: f64 = match difficulty {
        "LOW" => 0.7, "HIGH" => 1.5, _ => 1.0,
    };

    // Type-specific serotonergic modulation
    match claim_type {
        "causal" => { attention *= 1.2; },
        "statistical" => { attention *= 1.4; threshold = 0.4; },
        "definitional" => { attention *= 0.7; threshold = 0.6; },
        "normative" => { attention *= 1.1; },
        _ => {}
    }
    let caution_mod = match claim_type {
        "causal" => caution * 1.3,
        "normative" => caution * 1.5,
        _ => caution,
    };

    attention = (attention.max(0.3).min(2.5) * 10000.0).round() / 10000.0;
    threshold = (threshold.max(0.2).min(0.8) * 10000.0).round() / 10000.0;
    learning_rate = (learning_rate.max(0.3).min(2.5) * 10000.0).round() / 10000.0;
    let caution_final = (caution_mod.max(0.5).min(2.0) * 10000.0).round() / 10000.0;

    let mode = if attention > 1.3 { "VIGILANT" } else if attention < 0.7 { "RELAXED" } else { "NORMAL" };

    let mut r = HashMap::new();
    r.insert("attention".into(), attention);
    r.insert("threshold".into(), threshold);
    r.insert("learning_rate".into(), learning_rate);
    r.insert("caution".into(), caution_final);
    // Encode mode as f64: 0=NORMAL, 1=VIGILANT, -1=RELAXED
    r.insert("mode".into(), match mode { "VIGILANT" => 1.0, "RELAXED" => -1.0, _ => 0.0 });
    Ok(r)
}

#[pyfunction]
fn neuro_apply_confidence(raw_confidence: f64, caution: f64) -> PyResult<f64> {
    let modulated = if caution > 1.0 {
        raw_confidence + (0.5 - raw_confidence) * (caution - 1.0) * 0.3
    } else {
        raw_confidence
    };
    Ok((modulated.max(0.0).min(1.0) * 10000.0).round() / 10000.0)
}

// ══════════════════════════════════════════════
// MODULE 8: PREDICTIVE CODING (core compute)
// ══════════════════════════════════════════════

#[pyfunction]
fn predictive_error(
    predicted_confidence: f64,
    actual_confidence: f64,
    predicted_verdict: &str,
    actual_verdict: &str,
    range_low: f64,
    range_high: f64,
    precision: f64,
    surprise_threshold: f64,
) -> PyResult<HashMap<String, f64>> {
    let error = actual_confidence - predicted_confidence;
    let abs_error = error.abs();
    let surprising = abs_error > surprise_threshold;
    let weighted_error = abs_error * precision;
    let verdict_match = predicted_verdict == actual_verdict;
    let in_range = actual_confidence >= range_low && actual_confidence <= range_high;

    // meta_depth: 0=MINIMAL, 1=PARTIAL, 2=FULL
    let meta_depth = if !surprising && verdict_match && in_range { 0.0 }
        else if surprising && !verdict_match { 2.0 }
        else { 1.0 };

    let mut r = HashMap::new();
    r.insert("error".into(), (error * 10000.0).round() / 10000.0);
    r.insert("abs_error".into(), (abs_error * 10000.0).round() / 10000.0);
    r.insert("weighted_error".into(), (weighted_error * 10000.0).round() / 10000.0);
    r.insert("surprising".into(), if surprising { 1.0 } else { 0.0 });
    r.insert("verdict_match".into(), if verdict_match { 1.0 } else { 0.0 });
    r.insert("in_range".into(), if in_range { 1.0 } else { 0.0 });
    r.insert("meta_depth".into(), meta_depth);
    Ok(r)
}

#[pyfunction]
fn predictive_update_precision(errors: Vec<f64>) -> PyResult<f64> {
    if errors.len() < 3 { return Ok(1.0); }
    let n = errors.len().min(10);
    let recent: &[f64] = &errors[errors.len()-n..];
    let variance: f64 = recent.iter().map(|e| e * e).sum::<f64>() / n as f64;
    Ok(((1.0 / variance.max(0.01)) * 10000.0).round() / 10000.0)
}

// ══════════════════════════════════════════════
// MODULE 9: SOLVER CACHE (Rust HashMap + MD5)
// ══════════════════════════════════════════════

use std::sync::Mutex;

struct CacheEntry {
    value_json: String,
    ts: f64,
}

static CACHE: LazyLock<Mutex<HashMap<String, CacheEntry>>> = LazyLock::new(|| Mutex::new(HashMap::new()));
static CACHE_STATS: LazyLock<Mutex<(u64, u64)>> = LazyLock::new(|| Mutex::new((0, 0)));

fn now_secs() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs_f64()
}

fn cache_key(namespace: &str, query: &str) -> String {
    let input = format!("{}:{}", namespace, query);
    let digest = md5_simple(input.as_bytes());
    format!("{}:{}", namespace, &digest[..16])
}

fn md5_simple(data: &[u8]) -> String {
    // Simple MD5 via manual - but let's just use a hash
    use std::hash::{Hash, Hasher};
    use std::collections::hash_map::DefaultHasher;
    let mut h = DefaultHasher::new();
    data.hash(&mut h);
    let v = h.finish();
    format!("{:016x}", v)
}

#[pyfunction]
fn cache_get(namespace: &str, query: &str, ttl: f64) -> PyResult<Option<String>> {
    let key = cache_key(namespace, query);
    let mut cache = CACHE.lock().unwrap();
    let mut stats = CACHE_STATS.lock().unwrap();
    if let Some(entry) = cache.get(&key) {
        if now_secs() - entry.ts < ttl {
            stats.0 += 1; // hit
            return Ok(Some(entry.value_json.clone()));
        } else {
            cache.remove(&key);
        }
    }
    stats.1 += 1; // miss
    Ok(None)
}

#[pyfunction]
fn cache_put(namespace: &str, query: &str, value_json: &str, max_size: usize) -> PyResult<()> {
    let key = cache_key(namespace, query);
    let mut cache = CACHE.lock().unwrap();
    if cache.len() >= max_size {
        // Evict oldest
        if let Some(oldest_key) = cache.iter()
            .min_by(|a, b| a.1.ts.partial_cmp(&b.1.ts).unwrap())
            .map(|(k, _)| k.clone()) {
            cache.remove(&oldest_key);
        }
    }
    cache.insert(key, CacheEntry { value_json: value_json.to_string(), ts: now_secs() });
    Ok(())
}

#[pyfunction]
fn cache_stats() -> PyResult<HashMap<String, f64>> {
    let cache = CACHE.lock().unwrap();
    let stats = CACHE_STATS.lock().unwrap();
    let total = stats.0 + stats.1;
    let mut r = HashMap::new();
    r.insert("size".into(), cache.len() as f64);
    r.insert("hits".into(), stats.0 as f64);
    r.insert("misses".into(), stats.1 as f64);
    r.insert("hit_rate".into(), if total > 0 { (stats.0 as f64 / total as f64 * 1000.0).round() / 1000.0 } else { 0.0 });
    Ok(r)
}

#[pyfunction]
fn cache_clear() -> PyResult<()> {
    CACHE.lock().unwrap().clear();
    let mut s = CACHE_STATS.lock().unwrap();
    *s = (0, 0);
    Ok(())
}



// ══════════════════════════════════════════════
// MODULE 10: HTLF acceleration
// ══════════════════════════════════════════════

fn cosine_similarity(a: &[f64], b: &[f64]) -> f64 {
    if a.is_empty() || b.is_empty() || a.len() != b.len() { return 0.0; }
    let mut dot = 0.0;
    let mut na = 0.0;
    let mut nb = 0.0;
    for (x, y) in a.iter().zip(b.iter()) {
        dot += x * y;
        na += x * x;
        nb += y * y;
    }
    if na <= 1e-12 || nb <= 1e-12 { return 0.0; }
    (dot / (na.sqrt() * nb.sqrt())).clamp(-1.0, 1.0)
}

#[pyfunction]
fn compute_similarity_matrix(source_embeddings: Vec<Vec<f64>>, target_embeddings: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    let matrix: Vec<Vec<f64>> = source_embeddings.par_iter().map(|s| {
        target_embeddings.iter().map(|t| cosine_similarity(s, t).clamp(0.0, 1.0)).collect()
    }).collect();
    Ok(matrix)
}

#[pyfunction]
fn greedy_bipartite_match(sim_matrix: Vec<Vec<f64>>, threshold: f64) -> PyResult<Vec<(usize, usize, f64)>> {
    let mut cands: Vec<(f64, usize, usize)> = Vec::new();
    for (i, row) in sim_matrix.iter().enumerate() {
        for (j, s) in row.iter().enumerate() {
            cands.push((*s, i, j));
        }
    }
    cands.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    let mut used_i: HashSet<usize> = HashSet::new();
    let mut used_j: HashSet<usize> = HashSet::new();
    let mut out: Vec<(usize, usize, f64)> = Vec::new();
    for (s, i, j) in cands {
        if s < threshold || used_i.contains(&i) || used_j.contains(&j) { continue; }
        used_i.insert(i);
        used_j.insert(j);
        out.push((i, j, s));
    }
    Ok(out)
}

#[pyfunction]
fn compute_r_struct_typed(
    source_edges: Vec<(usize, usize, String)>,
    target_edges: Vec<(usize, usize, String)>,
    node_mapping: Vec<(usize, usize)>,
    type_weights: HashMap<String, f64>,
    mismatch_penalties: HashMap<(String, String), f64>,
) -> PyResult<f64> {
    if source_edges.is_empty() { return Ok(1.0); }
    let mapping: HashMap<usize, usize> = node_mapping.into_iter().collect();
    if mapping.is_empty() { return Ok(0.0); }

    let mut tgt_index: HashMap<(usize, usize), Vec<String>> = HashMap::new();
    for (s, t, tp) in target_edges {
        tgt_index.entry((s, t)).or_default().push(tp);
    }

    let mut weighted_score = 0.0;
    let mut total_weight = 0.0;

    for (s, t, src_tp) in source_edges {
        let ms = if let Some(v) = mapping.get(&s) { *v } else { continue };
        let mt = if let Some(v) = mapping.get(&t) { *v } else { continue };

        let w = *type_weights.get(&src_tp).unwrap_or(&1.0);
        total_weight += w;

        let mut best: f64 = 0.0;
        if let Some(cands) = tgt_index.get(&(ms, mt)) {
            for tgt_tp in cands {
                if tgt_tp == &src_tp {
                    best = best.max(1.0);
                } else {
                    let key = (src_tp.clone(), tgt_tp.clone());
                    best = best.max(*mismatch_penalties.get(&key).unwrap_or(&0.5));
                }
            }
        }
        weighted_score += w * best;
    }

    if total_weight <= 1e-12 { return Ok(0.0); }
    Ok((weighted_score / total_weight).clamp(0.0, 1.0))
}

#[pyfunction]
fn compute_tfidf_overlap(source_terms: Vec<String>, target_text: String, idf_weights: HashMap<String, f64>) -> PyResult<f64> {
    if source_terms.is_empty() { return Ok(0.0); }
    let tgt_tokens: HashSet<String> = WORD_RE.find_iter(&target_text.to_lowercase()).map(|m| m.as_str().to_string()).collect();
    let mut num = 0.0;
    let mut den = 0.0;
    for t in source_terms {
        let key = t.to_lowercase();
        let w = *idf_weights.get(&key).unwrap_or(&1.0);
        den += w;
        if tgt_tokens.contains(&key) { num += w; }
    }
    if den <= 1e-12 { return Ok(0.0); }
    Ok((num / den).clamp(0.0, 1.0))
}

#[pyfunction]
fn cosine_distance(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    let cos = cosine_similarity(&a, &b);
    Ok(((1.0 - cos) / 2.0).clamp(0.0, 1.0))
}

#[pyfunction]
fn mahalanobis_distance(a: Vec<f64>, b: Vec<f64>, cov_inv: Vec<Vec<f64>>) -> PyResult<f64> {
    if a.is_empty() || b.is_empty() || a.len() != b.len() || cov_inv.len() != a.len() {
        return Ok(1.0);
    }
    let d: Vec<f64> = a.iter().zip(b.iter()).map(|(x, y)| x - y).collect();
    let mut quad = 0.0;
    for i in 0..d.len() {
        if cov_inv[i].len() != d.len() { return Ok(1.0); }
        for j in 0..d.len() {
            quad += d[i] * cov_inv[i][j] * d[j];
        }
    }
    let dist = quad.abs().sqrt() / (d.len() as f64).sqrt();
    Ok(dist.clamp(0.0, 1.0))
}

#[pyfunction]
fn wasserstein_1d(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    if a.is_empty() || b.is_empty() || a.len() != b.len() { return Ok(1.0); }
    let mut sa = a;
    let mut sb = b;
    sa.sort_by(|x, y| x.partial_cmp(y).unwrap_or(std::cmp::Ordering::Equal));
    sb.sort_by(|x, y| x.partial_cmp(y).unwrap_or(std::cmp::Ordering::Equal));
    let mut sum = 0.0;
    for (x, y) in sa.iter().zip(sb.iter()) { sum += (x - y).abs(); }
    Ok((sum / sa.len() as f64).clamp(0.0, 1.0))
}

#[pyfunction]
fn batch_qualia_distances(source_vectors: Vec<Vec<f64>>, target_vectors: Vec<Vec<f64>>, method: String) -> PyResult<Vec<f64>> {
    let n = source_vectors.len().min(target_vectors.len());
    let m = method.to_lowercase();
    let out: Vec<f64> = (0..n).into_par_iter().map(|i| {
        match m.as_str() {
            "wasserstein" => wasserstein_1d(source_vectors[i].clone(), target_vectors[i].clone()).unwrap_or(1.0),
            "mahalanobis" => {
                // diagonal approx covariance inverse
                let a = &source_vectors[i];
                let b = &target_vectors[i];
                if a.is_empty() || b.is_empty() || a.len() != b.len() { return 1.0; }
                let mut sum = 0.0;
                for (x, y) in a.iter().zip(b.iter()) {
                    let v = (((x.abs() + y.abs()) / 2.0).powi(2) + 1e-3).max(1e-6);
                    sum += ((x - y).powi(2)) / v;
                }
                (sum.sqrt() / (a.len() as f64).sqrt()).clamp(0.0, 1.0)
            }
            _ => cosine_distance(source_vectors[i].clone(), target_vectors[i].clone()).unwrap_or(1.0),
        }
    }).collect();
    Ok(out)
}

#[pyfunction]
fn classify_profile_batch(r_structs: Vec<f64>, r_contexts: Vec<f64>, r_qualias: Vec<Option<f64>>) -> PyResult<Vec<String>> {
    let n = r_structs.len().min(r_contexts.len()).min(r_qualias.len());
    let mut out = Vec::with_capacity(n);

    for i in 0..n {
        let rs = r_structs[i].clamp(0.0, 1.0);
        let rc = r_contexts[i].clamp(0.0, 1.0);
        let rq = r_qualias[i].map(|v| v.clamp(0.0, 1.0));

        let mut best_name = "P00_unclassified".to_string();
        let mut best_score = -1.0;

        let candidates: Vec<(&str, Option<f64>)> = vec![
            ("P01_struct_context_sum", Some((rs + rc) / 2.0)),
            ("P02_struct_context_prod", Some((rs * rc).sqrt())),
            ("P03_struct_qualia_sum", rq.map(|q| (rs + q) / 2.0)),
            ("P04_struct_qualia_prod", rq.map(|q| (rs * q).sqrt())),
            ("P05_context_qualia_sum", rq.map(|q| (rc + q) / 2.0)),
            ("P06_context_qualia_prod", rq.map(|q| (rc * q).sqrt())),
            ("P07_struct_sum", Some(rs)),
            ("P08_struct_prod", Some(rs)),
            ("P09_context_sum", Some(rc)),
            ("P10_context_prod", Some(rc)),
            ("P11_qualia_sum", rq),
            ("P12_qualia_prod", rq),
        ];

        for (name, score_opt) in candidates {
            if let Some(score) = score_opt {
                if score > best_score {
                    best_score = score;
                    best_name = name.to_string();
                }
            }
        }
        out.push(best_name);
    }

    Ok(out)
}

// ══════════════════════════════════════════════
// PyModule
// ══════════════════════════════════════════════

#[pymodule]
fn ks_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Original 5
    m.add_function(wrap_pyfunction!(classify_claim, m)?)?;
    m.add_function(wrap_pyfunction!(lateral_inhibit, m)?)?;
    m.add_function(wrap_pyfunction!(extract_features, m)?)?;
    m.add_function(wrap_pyfunction!(bootstrap_confidence, m)?)?;
    m.add_function(wrap_pyfunction!(check_coherence, m)?)?;
    // reason_space
    m.add_function(wrap_pyfunction!(reason_space_analyze, m)?)?;
    // neuromodulation
    m.add_function(wrap_pyfunction!(neuromodulate, m)?)?;
    m.add_function(wrap_pyfunction!(neuro_apply_confidence, m)?)?;
    // predictive_coding
    m.add_function(wrap_pyfunction!(predictive_error, m)?)?;
    m.add_function(wrap_pyfunction!(predictive_update_precision, m)?)?;
    // solver_cache
    m.add_function(wrap_pyfunction!(cache_get, m)?)?;
    m.add_function(wrap_pyfunction!(cache_put, m)?)?;
    m.add_function(wrap_pyfunction!(cache_stats, m)?)?;
    m.add_function(wrap_pyfunction!(cache_clear, m)?)?;
    // HTLF
    m.add_function(wrap_pyfunction!(compute_similarity_matrix, m)?)?;
    m.add_function(wrap_pyfunction!(greedy_bipartite_match, m)?)?;
    m.add_function(wrap_pyfunction!(compute_r_struct_typed, m)?)?;
    m.add_function(wrap_pyfunction!(compute_tfidf_overlap, m)?)?;
    m.add_function(wrap_pyfunction!(cosine_distance, m)?)?;
    m.add_function(wrap_pyfunction!(mahalanobis_distance, m)?)?;
    m.add_function(wrap_pyfunction!(wasserstein_1d, m)?)?;
    m.add_function(wrap_pyfunction!(batch_qualia_distances, m)?)?;
    m.add_function(wrap_pyfunction!(classify_profile_batch, m)?)?;
    // Cultural/Temporal
    m.add_function(wrap_pyfunction!(cultural_frame_distance, m)?)?;
    m.add_function(wrap_pyfunction!(paradigm_distance, m)?)?;
    m.add_function(wrap_pyfunction!(compute_cultural_loss, m)?)?;
    m.add_function(wrap_pyfunction!(compute_temporal_loss, m)?)?;
    // Parse
    m.add_function(wrap_pyfunction!(parse_propositions, m)?)?;
    m.add_function(wrap_pyfunction!(batch_parse_propositions, m)?)?;
    // ── NEW: Batch acceleration ──
    m.add_function(wrap_pyfunction!(semantic_fingerprint, m)?)?;
    m.add_function(wrap_pyfunction!(char_ngrams_jaccard, m)?)?;
    m.add_function(wrap_pyfunction!(batch_jaccard, m)?)?;
    m.add_function(wrap_pyfunction!(gram_schmidt, m)?)?;
    m.add_function(wrap_pyfunction!(orthogonality_matrix, m)?)?;
    m.add_function(wrap_pyfunction!(heuristic_extract, m)?)?;
    m.add_function(wrap_pyfunction!(batch_heuristic_extract, m)?)?;
    m.add_function(wrap_pyfunction!(temporal_decay, m)?)?;
    m.add_function(wrap_pyfunction!(batch_temporal_decay, m)?)?;
    m.add_function(wrap_pyfunction!(text_structural_diff, m)?)?;
    m.add_function(wrap_pyfunction!(extract_numbers, m)?)?;
    m.add_function(wrap_pyfunction!(concept_bridge_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(batch_concept_bridge, m)?)?;
    Ok(())
}

// ============================================================
// Cultural & Temporal Translation Loss (Quine/Kuhn/Barthes)
// ============================================================

/// Cosine distance between two cultural frame vectors.
/// frames_a, frames_b: Vec<(frame_name, weight)>
#[pyfunction]
fn cultural_frame_distance(
    frames_a: Vec<(String, f64)>,
    frames_b: Vec<(String, f64)>,
) -> f64 {
    use std::collections::HashSet;
    let all_frames: HashSet<&str> = frames_a.iter().map(|(k, _)| k.as_str())
        .chain(frames_b.iter().map(|(k, _)| k.as_str()))
        .collect();
    if all_frames.is_empty() {
        return 0.0;
    }
    let mut sorted: Vec<&str> = all_frames.into_iter().collect();
    sorted.sort();

    let map_a: std::collections::HashMap<&str, f64> =
        frames_a.iter().map(|(k, v)| (k.as_str(), *v)).collect();
    let map_b: std::collections::HashMap<&str, f64> =
        frames_b.iter().map(|(k, v)| (k.as_str(), *v)).collect();

    let (mut dot, mut norm_a, mut norm_b) = (0.0f64, 0.0f64, 0.0f64);
    for f in &sorted {
        let a = map_a.get(f).copied().unwrap_or(0.0);
        let b = map_b.get(f).copied().unwrap_or(0.0);
        dot += a * b;
        norm_a += a * a;
        norm_b += b * b;
    }
    let denom = norm_a.sqrt() * norm_b.sqrt();
    if denom < 1e-10 {
        return 0.0;
    }
    1.0 - (dot / denom).clamp(0.0, 1.0)
}

/// Kuhnian paradigmatic distance between two eras.
/// era_source, era_target: era name strings.
/// Returns (paradigm_distance, n_shifts_crossed).
#[pyfunction]
fn paradigm_distance(era_source: &str, era_target: &str) -> (f64, usize) {
    const ERA_ORDER: &[&str] = &[
        "ancient", "medieval", "early_modern", "modern_19c",
        "early_20c", "late_20c", "contemporary",
    ];
    // Shift boundaries: (era_a_idx, era_b_idx, amplifier)
    const SHIFTS: &[(usize, usize, f64)] = &[
        (0, 2, 0.15),  // ancient → early_modern (scientific revolution)
        (2, 4, 0.20),  // early_modern → early_20c (relativity/quantum)
        (3, 4, 0.15),  // modern_19c → early_20c (physics revolution)
        (5, 6, 0.10),  // late_20c → contemporary (AI/digital)
        (1, 2, 0.15),  // medieval → early_modern (enlightenment)
    ];

    let idx_s = ERA_ORDER.iter().position(|&e| e == era_source);
    let idx_t = ERA_ORDER.iter().position(|&e| e == era_target);
    let (idx_s, idx_t) = match (idx_s, idx_t) {
        (Some(a), Some(b)) => (a, b),
        _ => return (0.3, 0),
    };
    if idx_s == idx_t {
        return (0.0, 0);
    }

    let chrono = (idx_s as f64 - idx_t as f64).abs() / (ERA_ORDER.len() - 1) as f64;
    let min_idx = idx_s.min(idx_t);
    let max_idx = idx_s.max(idx_t);

    let mut shift_amp = 0.0;
    let mut n_shifts = 0usize;
    for &(sa, sb, amp) in SHIFTS {
        let si_min = sa.min(sb);
        let si_max = sa.max(sb);
        if min_idx <= si_min && si_max <= max_idx {
            shift_amp += amp;
            n_shifts += 1;
        }
    }

    ((chrono + shift_amp).min(1.0), n_shifts)
}

/// Full cultural loss computation in Rust.
/// cultural_distance, n_concept_gaps, text_len, marker_count → (loss, indeterminacy, holistic_dep)
#[pyfunction]
fn compute_cultural_loss(
    cultural_distance: f64,
    n_concept_gaps: usize,
    text_len: usize,
    marker_count: usize,
) -> (f64, f64, f64) {
    // Holistic dependency (Duhem-Quine)
    let gap_factor = (n_concept_gaps as f64 / 5.0).min(1.0) * 0.4;
    let dist_factor = cultural_distance * 0.35;
    let density = (marker_count as f64 / (text_len as f64 / 500.0).max(1.0)).min(1.0) * 0.25;
    let holistic_dep = (gap_factor + dist_factor + density).min(1.0);

    // Loss estimate
    let gap_loss = (n_concept_gaps as f64 / 8.0).min(1.0);
    let loss = (0.35 * cultural_distance + 0.35 * gap_loss + 0.30 * holistic_dep).min(1.0);

    // Quinean indeterminacy
    let indet = (0.40 * cultural_distance
        + 0.35 * holistic_dep
        + 0.25 * (n_concept_gaps as f64 / 3.0).min(1.0)).min(1.0);

    (loss, indet, holistic_dep)
}

/// Full temporal loss computation in Rust.
/// paradigm_dist, n_incommensurable, semantic_drift → (loss, indeterminacy, web_decay)
#[pyfunction]
fn compute_temporal_loss(
    paradigm_dist: f64,
    n_incommensurable: usize,
    semantic_drift: f64,
) -> (f64, f64, f64) {
    // Duhem-Quine web decay
    let web_decay = (0.40 * paradigm_dist
        + 0.30 * (n_incommensurable as f64 / 4.0).min(1.0)
        + 0.30 * semantic_drift).min(1.0);

    // Loss
    let loss = (0.35 * paradigm_dist
        + 0.25 * (n_incommensurable as f64 / 5.0).min(1.0)
        + 0.20 * semantic_drift
        + 0.20 * web_decay).min(1.0);

    // Indeterminacy
    let indet = (0.40 * paradigm_dist
        + 0.30 * (n_incommensurable as f64 / 3.0).min(1.0)
        + 0.30 * web_decay).min(1.0);

    (loss, indet, web_decay)
}

// ══════════════════════════════════════════════
// MODULE: ENHANCED _parse() — Content-Sensitive Proposition Extraction
// 35 features (22→35 upgrade from Python version)
// ══════════════════════════════════════════════

static STOP_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    [
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "it", "its", "this", "that", "these", "those",
        "and", "or", "but", "not", "no", "nor",
    ].into()
});

static NEGATION_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["not", "no", "never", "neither", "nor", "none", "cannot", "nothing",
     "nowhere", "nobody", "hardly", "scarcely", "barely"].into()
});

static QUANTIFIER_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["all", "every", "each", "some", "many", "most", "few", "several",
     "any", "none", "always", "never", "often", "sometimes"].into()
});

static CAUSAL_PHRASES: LazyLock<Vec<&'static str>> = LazyLock::new(|| {
    vec!["because", "therefore", "hence", "thus", "consequently", "causes",
         "leads", "results", "due", "since", "implies", "entails",
         "as a result", "in consequence", "owing to"]
});

static COMPARATIVE_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["more", "less", "better", "worse", "greater", "smaller", "higher",
     "lower", "faster", "slower", "than", "compared", "superior",
     "inferior", "exceeds", "outperforms"].into()
});

static TEMPORAL_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["before", "after", "during", "when", "then", "now", "previously",
     "currently", "recently", "future", "past", "present", "eventually",
     "meanwhile", "simultaneously", "subsequently"].into()
});

static DEFINITIONAL_PHRASES: LazyLock<Vec<&'static str>> = LazyLock::new(|| {
    vec!["is a", "is an", "defined as", "refers to", "means", "constitutes",
         "consists of", "known as", "classified as", "characterized by"]
});

static MODAL_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["can", "could", "may", "might", "should", "would", "must",
     "shall", "ought", "need"].into()
});

static EVIDENCE_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["study", "research", "evidence", "data", "experiment", "analysis",
     "survey", "trial", "observation", "measurement", "finding",
     "result", "showed", "demonstrated", "proved", "confirmed"].into()
});

static HEDGING_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["perhaps", "possibly", "likely", "unlikely", "probably", "apparently",
     "seemingly", "arguably", "roughly", "approximately", "about",
     "suggest", "indicates", "implies"].into()
});

/// Enhanced content-sensitive proposition extraction.
/// Returns HashMap<String, bool> with 35 features.
/// Rust version: ~10-50x faster than Python for long texts.
#[pyfunction]
fn parse_propositions(text: &str) -> PyResult<HashMap<String, bool>> {
    let lower = text.to_lowercase();
    let words: Vec<&str> = lower.split_whitespace().collect();
    let word_set: HashSet<&str> = words.iter().copied().collect();
    let word_count = words.len();

    // Content words (non-stop, >1 char)
    let content_words: Vec<&str> = words.iter()
        .map(|w| w.trim_matches(|c: char| c.is_ascii_punctuation()))
        .filter(|w| w.len() > 1 && !STOP_WORDS.contains(w))
        .collect();
    let unique_content: HashSet<&str> = content_words.iter().copied().collect();

    let mut props = HashMap::new();

    // ── Lexical (6) ──
    props.insert("p_has_content".into(), !content_words.is_empty());
    props.insert("p_rich_vocab".into(),
        if content_words.is_empty() { false }
        else { unique_content.len() as f64 > (content_words.len() as f64 * 0.5).max(3.0) });
    props.insert("p_long_text".into(), word_count > 15);
    props.insert("p_short_text".into(), word_count <= 5);
    props.insert("p_complex_words".into(),
        content_words.iter().any(|w| w.len() > 10));
    props.insert("p_very_long".into(), word_count > 50);

    // ── Structural (6) ──
    let sentence_count = text.chars()
        .filter(|c| *c == '.' || *c == '!' || *c == '?')
        .count().max(1);
    props.insert("p_multi_sentence".into(), sentence_count > 1);
    props.insert("p_many_sentences".into(), sentence_count > 4);
    props.insert("p_has_conjunction".into(),
        [" and ", " or ", " but ", " yet ", " however ", " moreover ", " furthermore "]
        .iter().any(|w| lower.contains(w)));
    props.insert("p_has_negation".into(),
        words.iter().any(|w| NEGATION_WORDS.contains(w)));
    props.insert("p_has_quantifier".into(),
        words.iter().any(|w| QUANTIFIER_WORDS.contains(w)));
    props.insert("p_has_parenthetical".into(),
        text.contains('(') || text.contains('['));

    // ── Semantic (10) ──
    props.insert("p_causal".into(),
        CAUSAL_PHRASES.iter().any(|w| lower.contains(w)));
    props.insert("p_comparative".into(),
        words.iter().any(|w| COMPARATIVE_WORDS.contains(w)));
    props.insert("p_temporal".into(),
        words.iter().any(|w| TEMPORAL_WORDS.contains(w)));
    props.insert("p_definitional".into(),
        DEFINITIONAL_PHRASES.iter().any(|w| lower.contains(w)));
    props.insert("p_has_numbers".into(),
        text.chars().any(|c| c.is_ascii_digit()));
    props.insert("p_has_modal".into(),
        words.iter().any(|w| MODAL_WORDS.contains(w)));
    props.insert("p_has_evidence".into(),
        words.iter().any(|w| EVIDENCE_WORDS.contains(w)));
    props.insert("p_has_hedging".into(),
        words.iter().any(|w| HEDGING_WORDS.contains(w)));
    props.insert("p_conditional".into(),
        lower.contains("if ") || lower.contains("unless ") ||
        lower.contains("provided ") || lower.contains("assuming "));
    props.insert("p_evaluative".into(),
        ["good", "bad", "important", "significant", "critical", "essential",
         "excellent", "poor", "valuable", "harmful"]
        .iter().any(|w| lower.contains(w)));

    // ── Complexity (7) ──
    props.insert("p_nested".into(), text.matches(',').count() > 2 || text.contains('('));
    props.insert("p_chain".into(),
        ["therefore", "thus", "hence", "consequently", "so that", "it follows"]
        .iter().any(|w| lower.contains(w)));
    props.insert("p_list_structure".into(),
        lower.contains("first") && (lower.contains("second") || lower.contains("then")));
    props.insert("p_high_density".into(), {
        let ratio = if word_count > 0 { content_words.len() as f64 / word_count as f64 } else { 0.0 };
        ratio > 0.65
    });
    props.insert("p_question".into(), text.contains('?'));
    props.insert("p_imperative".into(),
        ["must", "should", "need to", "have to", "required"]
        .iter().any(|w| lower.contains(w)));
    props.insert("p_exclamatory".into(), text.contains('!'));

    // ── Hash-based diversity (2) ──
    let hash = md5_simple(text.as_bytes());
    let h0 = u8::from_str_radix(&hash[0..2], 16).unwrap_or(0);
    props.insert("p_hash_even".into(), h0 % 2 == 0);
    props.insert("p_hash_quarter".into(), h0 % 4 == 0);

    // ── Cross-domain signals (4) ──
    props.insert("p_mathematical".into(),
        text.contains('=') || text.contains('∀') || text.contains('∃') ||
        ["equation", "theorem", "proof", "formula", "axiom"]
        .iter().any(|w| lower.contains(w)));
    props.insert("p_scientific".into(),
        ["hypothesis", "experiment", "variable", "control", "sample",
         "coefficient", "p-value", "null hypothesis"]
        .iter().any(|w| lower.contains(w)));
    props.insert("p_technical".into(),
        ["algorithm", "implementation", "architecture", "protocol",
         "interface", "module", "framework", "pipeline"]
        .iter().any(|w| lower.contains(w)));
    props.insert("p_philosophical".into(),
        ["ontolog", "epistemo", "phenomeno", "metaphysic", "axiolog",
         "hermeneutic", "dialectic", "apriori"]
        .iter().any(|w| lower.contains(w)));

    Ok(props)
}

/// Batch parse: process multiple texts in parallel with Rayon.
/// Returns Vec<HashMap<String, bool>>.
#[pyfunction]
fn batch_parse_propositions(texts: Vec<String>) -> PyResult<Vec<HashMap<String, bool>>> {
    let results: Vec<HashMap<String, bool>> = texts.par_iter()
        .map(|text| {
            // Inline parse logic (avoid PyResult in rayon)
            let lower = text.to_lowercase();
            let words: Vec<&str> = lower.split_whitespace().collect();
            let word_set: HashSet<&str> = words.iter().copied().collect();
            let word_count = words.len();

            let content_words: Vec<&str> = words.iter()
                .map(|w| w.trim_matches(|c: char| c.is_ascii_punctuation()))
                .filter(|w| w.len() > 1 && !STOP_WORDS.contains(w))
                .collect();
            let unique_content: HashSet<&str> = content_words.iter().copied().collect();

            let mut props = HashMap::new();

            // Lexical
            props.insert("p_has_content".into(), !content_words.is_empty());
            props.insert("p_rich_vocab".into(),
                if content_words.is_empty() { false }
                else { unique_content.len() as f64 > (content_words.len() as f64 * 0.5).max(3.0) });
            props.insert("p_long_text".into(), word_count > 15);
            props.insert("p_short_text".into(), word_count <= 5);
            props.insert("p_complex_words".into(), content_words.iter().any(|w| w.len() > 10));
            props.insert("p_very_long".into(), word_count > 50);

            let sentence_count = text.chars()
                .filter(|c| *c == '.' || *c == '!' || *c == '?')
                .count().max(1);
            props.insert("p_multi_sentence".into(), sentence_count > 1);
            props.insert("p_many_sentences".into(), sentence_count > 4);
            props.insert("p_has_conjunction".into(),
                [" and ", " or ", " but ", " yet ", " however "]
                .iter().any(|w| lower.contains(w)));
            props.insert("p_has_negation".into(),
                words.iter().any(|w| NEGATION_WORDS.contains(w)));
            props.insert("p_has_quantifier".into(),
                words.iter().any(|w| QUANTIFIER_WORDS.contains(w)));
            props.insert("p_has_parenthetical".into(), text.contains('(') || text.contains('['));

            // Semantic
            props.insert("p_causal".into(), CAUSAL_PHRASES.iter().any(|w| lower.contains(w)));
            props.insert("p_comparative".into(), words.iter().any(|w| COMPARATIVE_WORDS.contains(w)));
            props.insert("p_temporal".into(), words.iter().any(|w| TEMPORAL_WORDS.contains(w)));
            props.insert("p_definitional".into(), DEFINITIONAL_PHRASES.iter().any(|w| lower.contains(w)));
            props.insert("p_has_numbers".into(), text.chars().any(|c| c.is_ascii_digit()));
            props.insert("p_has_modal".into(), words.iter().any(|w| MODAL_WORDS.contains(w)));
            props.insert("p_has_evidence".into(), words.iter().any(|w| EVIDENCE_WORDS.contains(w)));
            props.insert("p_has_hedging".into(), words.iter().any(|w| HEDGING_WORDS.contains(w)));
            props.insert("p_conditional".into(),
                lower.contains("if ") || lower.contains("unless ") ||
                lower.contains("provided ") || lower.contains("assuming "));
            props.insert("p_evaluative".into(),
                ["good", "bad", "important", "significant", "critical", "essential"]
                .iter().any(|w| lower.contains(w)));

            // Complexity
            props.insert("p_nested".into(), text.matches(',').count() > 2 || text.contains('('));
            props.insert("p_chain".into(),
                ["therefore", "thus", "hence", "consequently"]
                .iter().any(|w| lower.contains(w)));
            props.insert("p_list_structure".into(),
                lower.contains("first") && (lower.contains("second") || lower.contains("then")));
            props.insert("p_high_density".into(), {
                let ratio = if word_count > 0 { content_words.len() as f64 / word_count as f64 } else { 0.0 };
                ratio > 0.65
            });
            props.insert("p_question".into(), text.contains('?'));
            props.insert("p_imperative".into(),
                ["must", "should", "need to", "have to", "required"]
                .iter().any(|w| lower.contains(w)));
            props.insert("p_exclamatory".into(), text.contains('!'));

            // Hash
            let hash = md5_simple(text.as_bytes());
            let h0 = u8::from_str_radix(&hash[0..2], 16).unwrap_or(0);
            props.insert("p_hash_even".into(), h0 % 2 == 0);
            props.insert("p_hash_quarter".into(), h0 % 4 == 0);

            // Cross-domain
            props.insert("p_mathematical".into(),
                text.contains('=') || text.contains("equation") || text.contains("theorem"));
            props.insert("p_scientific".into(),
                ["hypothesis", "experiment", "variable", "sample"]
                .iter().any(|w| lower.contains(w)));
            props.insert("p_technical".into(),
                ["algorithm", "implementation", "architecture", "protocol", "pipeline"]
                .iter().any(|w| lower.contains(w)));
            props.insert("p_philosophical".into(),
                ["ontolog", "epistemo", "phenomeno", "metaphysic"]
                .iter().any(|w| lower.contains(w)));

            props
        })
        .collect();
    Ok(results)
}

// ════════════════════════════════════════════════════════════
// NEW: Semantic Cache Acceleration
// ════════════════════════════════════════════════════════════

const STOP_WORDS_CACHE: &[&str] = &[
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "it", "its", "this", "that", "and", "or", "but", "not",
];

/// Compute semantic fingerprint: lowercase → strip punctuation → remove stops → sort → join.
#[pyfunction]
fn semantic_fingerprint(text: &str) -> String {
    let lower = text.to_lowercase();
    let cleaned: String = lower.chars()
        .map(|c| if c.is_alphanumeric() || c.is_whitespace() { c } else { ' ' })
        .collect();
    let mut words: Vec<&str> = cleaned.split_whitespace()
        .filter(|w| w.len() > 1 && !STOP_WORDS_CACHE.contains(w))
        .collect();
    words.sort_unstable();
    words.dedup();
    words.join(" ")
}

/// Compute character n-gram Jaccard similarity between two texts.
#[pyfunction]
fn char_ngrams_jaccard(text_a: &str, text_b: &str, n: usize) -> f64 {
    use std::collections::HashSet;
    let ngrams_a: HashSet<&str> = (0..text_a.len().saturating_sub(n - 1))
        .filter_map(|i| text_a.get(i..i + n))
        .collect();
    let ngrams_b: HashSet<&str> = (0..text_b.len().saturating_sub(n - 1))
        .filter_map(|i| text_b.get(i..i + n))
        .collect();
    if ngrams_a.is_empty() && ngrams_b.is_empty() {
        return 1.0;
    }
    if ngrams_a.is_empty() || ngrams_b.is_empty() {
        return 0.0;
    }
    let intersection = ngrams_a.intersection(&ngrams_b).count() as f64;
    let union = ngrams_a.union(&ngrams_b).count() as f64;
    intersection / union
}

/// Batch Jaccard: compute pairwise Jaccard for query against N cached fingerprints.
/// Returns Vec<(index, similarity)> sorted by similarity desc.
#[pyfunction]
fn batch_jaccard(query_fp: &str, cached_fps: Vec<String>, ngram_size: usize, threshold: f64) -> Vec<(usize, f64)> {
    use std::collections::HashSet;
    let q_ngrams: HashSet<&str> = (0..query_fp.len().saturating_sub(ngram_size - 1))
        .filter_map(|i| query_fp.get(i..i + ngram_size))
        .collect();

    let mut results: Vec<(usize, f64)> = cached_fps.par_iter()
        .enumerate()
        .filter_map(|(idx, fp)| {
            let c_ngrams: HashSet<&str> = (0..fp.len().saturating_sub(ngram_size - 1))
                .filter_map(|i| fp.get(i..i + ngram_size))
                .collect();
            if q_ngrams.is_empty() && c_ngrams.is_empty() {
                return Some((idx, 1.0));
            }
            if q_ngrams.is_empty() || c_ngrams.is_empty() {
                return None;
            }
            let intersection = q_ngrams.intersection(&c_ngrams).count() as f64;
            let union = q_ngrams.union(&c_ngrams).count() as f64;
            let sim = intersection / union;
            if sim >= threshold { Some((idx, sim)) } else { None }
        })
        .collect();
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    results
}

// ════════════════════════════════════════════════════════════
// NEW: Solver Orthogonality — Gram-Schmidt & Cosine Matrix
// ════════════════════════════════════════════════════════════

/// Gram-Schmidt orthogonalization on a set of weight vectors.
/// Input: Vec of Vec<f64> (each is a solver weight vector).
/// Output: orthogonalized vectors + retention blend factors.
#[pyfunction]
fn gram_schmidt(vectors: Vec<Vec<f64>>, retention: f64) -> PyResult<Vec<Vec<f64>>> {
    let n = vectors.len();
    if n == 0 {
        return Ok(vec![]);
    }
    let dim = vectors[0].len();
    let mut ortho: Vec<Vec<f64>> = Vec::with_capacity(n);

    for i in 0..n {
        let mut v = vectors[i].clone();
        // Subtract projections onto previous orthogonal vectors
        for j in 0..ortho.len() {
            let dot_vu: f64 = v.iter().zip(ortho[j].iter()).map(|(a, b)| a * b).sum();
            let dot_uu: f64 = ortho[j].iter().map(|x| x * x).sum();
            if dot_uu > 1e-12 {
                let proj = dot_vu / dot_uu;
                for k in 0..dim {
                    v[k] -= proj * ortho[j][k];
                }
            }
        }
        // Normalize
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm > 1e-12 {
            for x in v.iter_mut() {
                *x /= norm;
            }
        }
        // Blend with retention (keep some original direction)
        let blended: Vec<f64> = v.iter().zip(vectors[i].iter())
            .map(|(orth, orig)| {
                let o_norm: f64 = vectors[i].iter().map(|x| x * x).sum::<f64>().sqrt();
                let orig_n = if o_norm > 1e-12 { orig / o_norm } else { 0.0 };
                (1.0 - retention) * orth + retention * orig_n
            })
            .collect();
        // Re-normalize blended
        let b_norm: f64 = blended.iter().map(|x| x * x).sum::<f64>().sqrt();
        if b_norm > 1e-12 {
            ortho.push(blended.iter().map(|x| x / b_norm).collect());
        } else {
            ortho.push(blended);
        }
    }
    Ok(ortho)
}

/// Compute pairwise cosine similarity matrix for a set of vectors.
/// Returns NxN matrix.
#[pyfunction]
fn orthogonality_matrix(vectors: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    let n = vectors.len();
    let norms: Vec<f64> = vectors.iter()
        .map(|v| v.iter().map(|x| x * x).sum::<f64>().sqrt())
        .collect();

    let matrix: Vec<Vec<f64>> = (0..n).map(|i| {
        (0..n).map(|j| {
            if norms[i] < 1e-12 || norms[j] < 1e-12 {
                return 0.0;
            }
            let dot: f64 = vectors[i].iter().zip(vectors[j].iter())
                .map(|(a, b)| a * b).sum();
            (dot / (norms[i] * norms[j])).clamp(-1.0, 1.0)
        }).collect()
    }).collect();
    Ok(matrix)
}

// ════════════════════════════════════════════════════════════
// NEW: Heuristic Proposition Extraction (semantic_parse fallback)
// ════════════════════════════════════════════════════════════

/// Fast heuristic proposition extraction from text.
/// Returns JSON-compatible HashMap with propositions, relations, entities, etc.
#[pyfunction]
fn heuristic_extract(text: &str) -> PyResult<HashMap<String, String>> {
    let mut result = HashMap::new();

    // Split into sentences (no lookbehind in Rust regex — use char split)
    let sentences: Vec<&str> = text.split(|c: char| c == '.' || c == '!' || c == '?')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .take(10)
        .collect();

    // Build propositions JSON array
    let lower = text.to_lowercase();
    let mut props_json = Vec::new();
    for (i, sent) in sentences.iter().enumerate() {
        let s_lower = sent.to_lowercase();
        let ptype = if ["because", "causes", "leads to", "results in", "due to"]
            .iter().any(|w| s_lower.contains(w)) { "causal" }
        else if ["is a", "defined as", "refers to", "means"]
            .iter().any(|w| s_lower.contains(w)) { "definitional" }
        else if ["more", "less", "better", "worse", "than"]
            .iter().any(|w| s_lower.contains(w)) { "comparative" }
        else if ["if", "unless", "provided", "assuming"]
            .iter().any(|w| s_lower.contains(w)) { "conditional" }
        else if ["good", "bad", "important", "should"]
            .iter().any(|w| s_lower.contains(w)) { "evaluative" }
        else { "factual" };

        let truncated: String = sent.chars().take(200).collect();
        props_json.push(format!(
            r#"{{"id":"P{}","text":"{}","type":"{}"}}"#,
            i + 1,
            truncated.replace('"', "'"),
            ptype
        ));
    }
    result.insert("propositions".into(), format!("[{}]", props_json.join(",")));

    // Relations: sequential
    let mut rels_json = Vec::new();
    for i in 0..sentences.len().saturating_sub(1) {
        let s_lower = sentences[i].to_lowercase();
        let rtype = if s_lower.contains("because") || s_lower.contains("causes") { "causes" }
        else if lower.contains("therefore") || lower.contains("thus") { "implies" }
        else { "supports" };
        rels_json.push(format!(
            r#"{{"from":"P{}","to":"P{}","type":"{}"}}"#,
            i + 1, i + 2, rtype
        ));
    }
    result.insert("relations".into(), format!("[{}]", rels_json.join(",")));

    // Entities: capitalized words
    let entity_re = Regex::new(r"\b[A-Z][a-z]{2,}\b").unwrap();
    let skip = ["The", "This", "That", "These", "Those", "However", "Therefore",
        "Because", "Although", "Moreover", "Furthermore"];
    let mut entities: Vec<String> = entity_re.find_iter(text)
        .map(|m| m.as_str().to_string())
        .filter(|w| !skip.contains(&w.as_str()))
        .collect();
    entities.sort();
    entities.dedup();
    entities.truncate(10);
    let entities_json: Vec<String> = entities.iter()
        .map(|e| format!(r#""{}""#, e))
        .collect();
    result.insert("entities".into(), format!("[{}]", entities_json.join(",")));

    // Domain
    let domain = if ["equation", "theorem", "proof", "axiom"].iter().any(|w| lower.contains(w)) { "mathematics" }
    else if ["gene", "protein", "cell", "evolution"].iter().any(|w| lower.contains(w)) { "biology" }
    else if ["force", "energy", "quantum", "relativity"].iter().any(|w| lower.contains(w)) { "physics" }
    else if ["algorithm", "code", "function", "module"].iter().any(|w| lower.contains(w)) { "computer_science" }
    else if ["ontolog", "epistemo", "phenomeno"].iter().any(|w| lower.contains(w)) { "philosophy" }
    else if ["statute", "precedent", "jurisdiction"].iter().any(|w| lower.contains(w)) { "law" }
    else { "general" };
    result.insert("domain".into(), domain.into());

    // Negations
    let negation_ids: Vec<String> = sentences.iter().enumerate()
        .filter(|(_, s)| ["not", "no", "never", "neither", "cannot"]
            .iter().any(|w| s.to_lowercase().contains(w)))
        .map(|(i, _)| format!(r#""P{}""#, i + 1))
        .collect();
    result.insert("negations".into(), format!("[{}]", negation_ids.join(",")));

    // Quantifiers
    let mut quant_parts = Vec::new();
    for (i, sent) in sentences.iter().enumerate() {
        let s_lower = sent.to_lowercase();
        let q = if ["all", "every", "each", "always"].iter().any(|w| s_lower.contains(w)) { Some("universal") }
        else if ["some", "sometimes", "a few", "several"].iter().any(|w| s_lower.contains(w)) { Some("existential") }
        else if ["most", "many", "often"].iter().any(|w| s_lower.contains(w)) { Some("most") }
        else { None };
        if let Some(qtype) = q {
            quant_parts.push(format!(r#""P{}":"{}""#, i + 1, qtype));
        }
    }
    result.insert("quantifiers".into(), format!("{{{}}}", quant_parts.join(",")));
    result.insert("confidence".into(), "0.5".into());
    result.insert("prop_count".into(), sentences.len().to_string());

    Ok(result)
}

/// Batch heuristic extraction with Rayon parallelism.
#[pyfunction]
fn batch_heuristic_extract(texts: Vec<String>) -> PyResult<Vec<HashMap<String, String>>> {
    let results: Vec<HashMap<String, String>> = texts.par_iter()
        .map(|text| {
            // Inline simplified version for rayon (avoid Regex in tight loop)
            let mut result = HashMap::new();
            let lower = text.to_lowercase();
            let sentences: Vec<&str> = text.split(|c: char| c == '.' || c == '!' || c == '?')
                .map(|s| s.trim())
                .filter(|s| !s.is_empty())
                .take(10)
                .collect();

            result.insert("prop_count".into(), sentences.len().to_string());
            result.insert("confidence".into(), "0.5".into());

            // Domain
            let domain = if lower.contains("equation") || lower.contains("theorem") { "mathematics" }
            else if lower.contains("gene") || lower.contains("protein") { "biology" }
            else if lower.contains("force") || lower.contains("quantum") { "physics" }
            else if lower.contains("algorithm") || lower.contains("code") { "computer_science" }
            else { "general" };
            result.insert("domain".into(), domain.into());

            result
        })
        .collect();
    Ok(results)
}

// ════════════════════════════════════════════════════════════
// NEW: Temporal Decay Computation
// ════════════════════════════════════════════════════════════

/// Compute temporal decay factor: exp(-ln2 * age_years / half_life_years).
/// Returns decay factor in [0, 1].
#[pyfunction]
fn temporal_decay(age_years: f64, half_life_years: f64) -> f64 {
    if half_life_years <= 0.0 {
        return 0.0;
    }
    (-std::f64::consts::LN_2 * age_years / half_life_years).exp()
}

/// Batch temporal decay with domain-specific half-lives.
/// Input: Vec<(age_years, domain)>
/// Returns: Vec<decay_factor>
#[pyfunction]
fn batch_temporal_decay(items: Vec<(f64, String)>) -> Vec<f64> {
    items.par_iter()
        .map(|(age, domain)| {
            let half_life = match domain.as_str() {
                "ai" | "machine_learning" => 0.5,
                "technology" | "computer_science" => 2.0,
                "medicine" | "biology" => 5.0,
                "chemistry" => 8.0,
                "economics" => 7.0,
                "physics" => 20.0,
                "geology" => 50.0,
                "mathematics" => 100.0,
                "philosophy" => 200.0,
                "history" => 500.0,
                _ => 10.0,
            };
            if half_life <= 0.0 { 0.0 }
            else { (-std::f64::consts::LN_2 * age / half_life).exp() }
        })
        .collect()
}

// ════════════════════════════════════════════════════════════
// NEW: Adversarial Text Analysis
// ════════════════════════════════════════════════════════════

/// Compute structural diff between two texts.
/// Returns: (word_overlap_ratio, sentence_overlap_ratio, length_ratio)
#[pyfunction]
fn text_structural_diff(original: &str, perturbed: &str) -> (f64, f64, f64) {
    use std::collections::HashSet;

    let orig_words: HashSet<&str> = original.split_whitespace().collect();
    let pert_words: HashSet<&str> = perturbed.split_whitespace().collect();

    let word_overlap = if orig_words.is_empty() && pert_words.is_empty() {
        1.0
    } else if orig_words.is_empty() || pert_words.is_empty() {
        0.0
    } else {
        let intersection = orig_words.intersection(&pert_words).count() as f64;
        let union = orig_words.union(&pert_words).count() as f64;
        intersection / union
    };

    let orig_sents: Vec<&str> = original.split(|c: char| c == '.' || c == '!' || c == '?')
        .map(|s| s.trim()).filter(|s| !s.is_empty()).collect();
    let pert_sents: Vec<&str> = perturbed.split(|c: char| c == '.' || c == '!' || c == '?')
        .map(|s| s.trim()).filter(|s| !s.is_empty()).collect();
    let sent_overlap = if orig_sents.is_empty() && pert_sents.is_empty() {
        1.0
    } else {
        let o_set: HashSet<&str> = orig_sents.iter().copied().collect();
        let p_set: HashSet<&str> = pert_sents.iter().copied().collect();
        let intersection = o_set.intersection(&p_set).count() as f64;
        let union = o_set.union(&p_set).count() as f64;
        if union > 0.0 { intersection / union } else { 1.0 }
    };

    let len_ratio = if original.len() > 0 {
        perturbed.len() as f64 / original.len() as f64
    } else {
        1.0
    };

    (word_overlap, sent_overlap, len_ratio)
}

/// Extract all numbers from text as f64.
#[pyfunction]
fn extract_numbers(text: &str) -> Vec<f64> {
    let re = Regex::new(r"-?\d+\.?\d*").unwrap();
    re.find_iter(text)
        .filter_map(|m| m.as_str().parse::<f64>().ok())
        .collect()
}

// ════════════════════════════════════════════════════════════
// NEW: Cross-Domain Concept Bridge
// ════════════════════════════════════════════════════════════

/// Compute concept bridge similarity between two domain concept sets.
/// Each concept is (name, domain, weight). Returns structural + semantic similarity.
#[pyfunction]
fn concept_bridge_similarity(
    concepts_a: Vec<(String, String, f64)>,
    concepts_b: Vec<(String, String, f64)>,
) -> PyResult<(f64, f64)> {
    if concepts_a.is_empty() || concepts_b.is_empty() {
        return Ok((0.0, 0.0));
    }

    // Structural: same-name matches across domains
    let structural: f64 = {
        let mut matches = 0.0;
        let total = concepts_a.len().max(concepts_b.len()) as f64;
        for (name_a, _, w_a) in &concepts_a {
            for (name_b, _, w_b) in &concepts_b {
                // Exact or substring match
                let na = name_a.to_lowercase();
                let nb = name_b.to_lowercase();
                if na == nb || na.contains(&nb) || nb.contains(&na) {
                    matches += (w_a * w_b).sqrt();
                }
            }
        }
        (matches / total).min(1.0)
    };

    // Semantic: domain distance-based similarity
    let semantic: f64 = {
        let domain_distance = |a: &str, b: &str| -> f64 {
            if a == b { return 0.0; }
            let groups = vec![
                vec!["math", "mathematics", "physics", "computer_science"],
                vec!["biology", "chemistry", "medicine"],
                vec!["music", "art", "creative"],
                vec!["philosophy", "law", "social"],
            ];
            for group in &groups {
                let a_in = group.iter().any(|g| a.contains(g));
                let b_in = group.iter().any(|g| b.contains(g));
                if a_in && b_in { return 0.3; }
            }
            0.7
        };

        let mut total_sim = 0.0;
        let count = concepts_a.len() as f64;
        for (_, domain_a, _) in &concepts_a {
            let mut best = 0.0_f64;
            for (_, domain_b, _) in &concepts_b {
                let d = domain_distance(domain_a, domain_b);
                let sim = 1.0 - d;
                best = best.max(sim);
            }
            total_sim += best;
        }
        total_sim / count
    };

    Ok((structural, semantic))
}

/// Batch concept bridge: compute similarities for N pairs.
#[pyfunction]
fn batch_concept_bridge(
    pairs: Vec<(Vec<(String, String, f64)>, Vec<(String, String, f64)>)>,
) -> Vec<(f64, f64)> {
    pairs.par_iter()
        .map(|(a, b)| {
            if a.is_empty() || b.is_empty() {
                return (0.0, 0.0);
            }
            let structural = {
                let mut matches = 0.0;
                let total = a.len().max(b.len()) as f64;
                for (na, _, wa) in a {
                    for (nb, _, wb) in b {
                        let la = na.to_lowercase();
                        let lb = nb.to_lowercase();
                        if la == lb || la.contains(&lb) || lb.contains(&la) {
                            matches += (wa * wb).sqrt();
                        }
                    }
                }
                (matches / total).min(1.0)
            };
            (structural, 0.5) // semantic defaults to 0.5 in batch mode
        })
        .collect()
}
