use pyo3::prelude::*;
use rayon::prelude::*;
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

// ══════════════════════════════════════
// 1) CLAIM CLASSIFIER — LazyLock compiled regexes
// ══════════════════════════════════════

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
            let compiled: Vec<Regex> = pats.into_iter()
                .filter_map(|p| Regex::new(p).ok())
                .collect();
            (name, compiled)
        }).collect()
    }
});

#[pyfunction]
fn classify_claim(text: &str) -> PyResult<HashMap<String, f64>> {
    let text_lower = text.to_lowercase();
    let mut scores: HashMap<String, f64> = HashMap::new();

    for (ctype, regexes) in &COMPILED.patterns {
        let hits: usize = regexes.iter()
            .filter(|re| re.is_match(&text_lower))
            .count();
        if hits > 0 {
            let threshold = (regexes.len() as f64 * 0.4).max(3.0);
            scores.insert(ctype.to_string(), (hits as f64 / threshold).min(1.0));
        }
    }

    if scores.is_empty() {
        scores.insert("unknown".to_string(), 1.0);
    }

    let total: f64 = scores.values().sum();
    for v in scores.values_mut() {
        *v = (*v / total * 1000.0).round() / 1000.0;
    }
    Ok(scores)
}

// ══════════════════════════════════════
// 2) LATERAL INHIBITION
// ══════════════════════════════════════

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
        .map(|(c, s)| ((c - s).max(0.1) * 10000.0).round() / 10000.0)
        .collect())
}

// ══════════════════════════════════════
// 3) FEATURE EXTRACTION
// ══════════════════════════════════════

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

// ══════════════════════════════════════
// 4) BOOTSTRAP (Rayon parallel)
// ══════════════════════════════════════

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

// ══════════════════════════════════════
// 5) COHERENCE CHECK
// ══════════════════════════════════════

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

#[pymodule]
fn ks_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(classify_claim, m)?)?;
    m.add_function(wrap_pyfunction!(lateral_inhibit, m)?)?;
    m.add_function(wrap_pyfunction!(extract_features, m)?)?;
    m.add_function(wrap_pyfunction!(bootstrap_confidence, m)?)?;
    m.add_function(wrap_pyfunction!(check_coherence, m)?)?;
    Ok(())
}
