use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
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
fn extract_features(text: &str) -> PyResult<HashMap<String, PyObject>> {
    Python::with_gil(|py| {
        let lower = text.to_lowercase();
        let words: HashSet<&str> = lower.split_whitespace().collect();
        let neg: HashSet<&str> = ["not","never","no","neither","without","none"].into();
        let cau: HashSet<&str> = ["cause","causes","caused","because","effect","leads","results"].into();
        let sta: HashSet<&str> = ["significant","correlation","sample","regression"].into();
        let def: HashSet<&str> = ["defined","means","refers","definition","known"].into();
        let mut f: HashMap<String, PyObject> = HashMap::new();
        f.insert("word_count".into(), words.len().to_object(py));
        f.insert("char_count".into(), text.len().to_object(py));
        f.insert("has_numbers".into(), text.chars().any(|c| c.is_ascii_digit()).to_object(py));
        f.insert("has_negation".into(), words.iter().any(|w| neg.contains(w)).to_object(py));
        f.insert("has_causal".into(), words.iter().any(|w| cau.contains(w)).to_object(py));
        f.insert("has_statistical".into(), words.iter().any(|w| sta.contains(w)).to_object(py));
        f.insert("has_definition".into(), words.iter().any(|w| def.contains(w)).to_object(py));
        f.insert("sentence_count".into(),
            text.chars().filter(|c| *c=='.'||*c=='!'||*c=='?').count().max(1).to_object(py));
        Ok(f)
    })
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
    // New: reason_space
    m.add_function(wrap_pyfunction!(reason_space_analyze, m)?)?;
    // New: neuromodulation
    m.add_function(wrap_pyfunction!(neuromodulate, m)?)?;
    m.add_function(wrap_pyfunction!(neuro_apply_confidence, m)?)?;
    // New: predictive_coding
    m.add_function(wrap_pyfunction!(predictive_error, m)?)?;
    m.add_function(wrap_pyfunction!(predictive_update_precision, m)?)?;
    // New: solver_cache
    m.add_function(wrap_pyfunction!(cache_get, m)?)?;
    m.add_function(wrap_pyfunction!(cache_put, m)?)?;
    m.add_function(wrap_pyfunction!(cache_stats, m)?)?;
    m.add_function(wrap_pyfunction!(cache_clear, m)?)?;
    Ok(())
}
