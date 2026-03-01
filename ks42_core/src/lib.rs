use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use std::collections::HashMap;

// ── Constants ──────────────────────────────────────────────────
const AXES: [&str; 5] = ["r_struct", "r_context", "r_qualia", "r_cultural", "r_temporal"];
const LOSS_THRESHOLD: f64 = 0.5;
const LEAP_MIN_DONOR_SCORE: f64 = 0.75;
const SINGLE_AXIS_GAP: f64 = 0.25;
const CONFLICT_DETECTION: f64 = 0.15;
const NOVELTY_TRIVIAL: f64 = 0.3;

// Known semantic tensions (sparse — only meaningful pairs)
fn semantic_tension(ax_a: &str, ax_b: &str) -> f64 {
    let mut pair = [ax_a, ax_b];
    pair.sort();
    match (pair[0], pair[1]) {
        ("r_qualia", "r_struct") => 0.35,
        ("r_cultural", "r_temporal") => 0.30,
        ("r_context", "r_qualia") => 0.25,
        ("r_cultural", "r_struct") => 0.15,
        ("r_context", "r_temporal") => 0.10,
        _ => 0.05,
    }
}

// ════════════════════════════════════════════════════════════════
// LossVector
// ════════════════════════════════════════════════════════════════

#[pyclass]
#[derive(Clone, Debug)]
struct RustLossVector {
    #[pyo3(get)]
    r_struct: f64,
    #[pyo3(get)]
    r_context: f64,
    #[pyo3(get)]
    r_qualia: f64,
    #[pyo3(get)]
    r_cultural: f64,
    #[pyo3(get)]
    r_temporal: f64,
}

#[pymethods]
impl RustLossVector {
    #[new]
    fn new(r_struct: f64, r_context: f64, r_qualia: f64,
           r_cultural: f64, r_temporal: f64) -> PyResult<Self> {
        // Validate all scores in [0.0, 1.0]
        for (name, val) in [
            ("r_struct", r_struct), ("r_context", r_context),
            ("r_qualia", r_qualia), ("r_cultural", r_cultural),
            ("r_temporal", r_temporal),
        ] {
            if !(0.0..=1.0).contains(&val) {
                return Err(PyValueError::new_err(
                    format!("{name} must be in [0.0, 1.0], got {val}")
                ));
            }
        }
        Ok(Self { r_struct, r_context, r_qualia, r_cultural, r_temporal })
    }

    fn as_tuple(&self) -> (f64, f64, f64, f64, f64) {
        (self.r_struct, self.r_context, self.r_qualia, self.r_cultural, self.r_temporal)
    }

    fn scores(&self) -> [f64; 5] {
        [self.r_struct, self.r_context, self.r_qualia, self.r_cultural, self.r_temporal]
    }

    fn magnitude(&self) -> f64 {
        let s = self.scores();
        s.iter().map(|v| (1.0 - v).powi(2)).sum::<f64>().sqrt()
    }

    fn mean(&self) -> f64 {
        let s = self.scores();
        s.iter().sum::<f64>() / 5.0
    }

    fn dominant_loss_axis(&self) -> String {
        let s = self.scores();
        let mut min_idx = 0;
        let mut min_val = s[0];
        for (i, &v) in s.iter().enumerate().skip(1) {
            if v < min_val {
                min_val = v;
                min_idx = i;
            }
        }
        AXES[min_idx].to_string()
    }

    fn void_dimensions(&self) -> Vec<String> {
        let s = self.scores();
        AXES.iter().enumerate()
            .filter(|(i, _)| s[*i] < LOSS_THRESHOLD)
            .map(|(_, ax)| ax.to_string())
            .collect()
    }

    fn axis_score(&self, axis: &str) -> PyResult<f64> {
        match axis {
            "r_struct" => Ok(self.r_struct),
            "r_context" => Ok(self.r_context),
            "r_qualia" => Ok(self.r_qualia),
            "r_cultural" => Ok(self.r_cultural),
            "r_temporal" => Ok(self.r_temporal),
            _ => Err(PyValueError::new_err(format!("Unknown axis: {axis}"))),
        }
    }

    fn distance_to(&self, other: &RustLossVector) -> f64 {
        let a = self.scores();
        let b = other.scores();
        a.iter().zip(b.iter())
            .map(|(x, y)| (x - y).powi(2))
            .sum::<f64>()
            .sqrt()
    }

    fn __repr__(&self) -> String {
        format!(
            "RustLossVector(struct={:.2}, ctx={:.2}, qual={:.2}, cult={:.2}, temp={:.2})",
            self.r_struct, self.r_context, self.r_qualia, self.r_cultural, self.r_temporal
        )
    }
}

// ════════════════════════════════════════════════════════════════
// Pattern Classification
// ════════════════════════════════════════════════════════════════

#[pyfunction]
fn classify_loss_pattern(lv: &RustLossVector) -> String {
    let s = lv.scores();
    let mean = lv.mean();
    let voids: Vec<usize> = s.iter().enumerate()
        .filter(|(_, &v)| v < LOSS_THRESHOLD)
        .map(|(i, _)| i)
        .collect();

    // Temporal decay (most specific — check first)
    if s[4] < LOSS_THRESHOLD && voids.len() == 1 && voids[0] == 4 {
        return "temporal_decay".to_string();
    }

    // Single axis drop
    let big_drops: Vec<usize> = s.iter().enumerate()
        .filter(|(_, &v)| (mean - v) > SINGLE_AXIS_GAP)
        .map(|(i, _)| i)
        .collect();

    if big_drops.len() == 1 && voids.len() <= 1 {
        return "single_axis_drop".to_string();
    }

    // Multi-axis void
    if voids.len() >= 2 {
        return "multi_axis_void".to_string();
    }

    // Axis conflict
    for i in 0..5 {
        for j in (i + 1)..5 {
            if s[i] < 0.65 && s[j] < 0.65 && (s[i] - s[j]).abs() < CONFLICT_DETECTION {
                return "axis_conflict".to_string();
            }
        }
    }

    "mixed".to_string()
}

// ════════════════════════════════════════════════════════════════
// Tension Computation
// ════════════════════════════════════════════════════════════════

#[pyfunction]
fn compute_tension(ax_a: &str, ax_b: &str, a_vals: Vec<f64>, b_vals: Vec<f64>) -> f64 {
    let n = a_vals.len().min(b_vals.len());
    if n < 3 {
        return semantic_tension(ax_a, ax_b);
    }

    let a = &a_vals[..n];
    let b = &b_vals[..n];
    let nf = n as f64;

    let mean_a: f64 = a.iter().sum::<f64>() / nf;
    let mean_b: f64 = b.iter().sum::<f64>() / nf;

    let cov: f64 = a.iter().zip(b.iter())
        .map(|(x, y)| (x - mean_a) * (y - mean_b))
        .sum::<f64>() / nf;

    let std_a = (a.iter().map(|x| (x - mean_a).powi(2)).sum::<f64>() / nf).sqrt();
    let std_b = (b.iter().map(|y| (y - mean_b).powi(2)).sum::<f64>() / nf).sqrt();

    if std_a < 1e-9 || std_b < 1e-9 {
        return 0.0;
    }

    let pearson = cov / (std_a * std_b);
    let tension = (-pearson).max(0.0);
    (tension * 10000.0).round() / 10000.0
}

#[pyfunction]
fn get_semantic_tension(ax_a: &str, ax_b: &str) -> f64 {
    semantic_tension(ax_a, ax_b)
}

// ════════════════════════════════════════════════════════════════
// Conflict Detection (batch)
// ════════════════════════════════════════════════════════════════

#[pyclass]
#[derive(Clone, Debug)]
struct RustAxisConflict {
    #[pyo3(get)]
    axis_a: String,
    #[pyo3(get)]
    axis_b: String,
    #[pyo3(get)]
    tension: f64,
    #[pyo3(get)]
    ternary_state: String,
}

#[pyfunction]
fn detect_conflicts(
    lv: &RustLossVector,
    corpus_scores: HashMap<String, Vec<f64>>,
) -> Vec<RustAxisConflict> {
    let s = lv.scores();
    let mut conflicts = Vec::new();

    for i in 0..5 {
        for j in (i + 1)..5 {
            let sa = s[i];
            let sb = s[j];

            if sa >= 0.8 && sb >= 0.8 {
                continue;
            }

            let ax_a = AXES[i];
            let ax_b = AXES[j];

            let a_vals = corpus_scores.get(ax_a).cloned().unwrap_or_default();
            let b_vals = corpus_scores.get(ax_b).cloned().unwrap_or_default();
            let tension = compute_tension(ax_a, ax_b, a_vals, b_vals);

            if tension > CONFLICT_DETECTION {
                let state = if sa > sb + 0.15 {
                    "true_a"
                } else if sb > sa + 0.15 {
                    "true_b"
                } else {
                    "indeterminate"
                };

                conflicts.push(RustAxisConflict {
                    axis_a: ax_a.to_string(),
                    axis_b: ax_b.to_string(),
                    tension: (tension * 10000.0).round() / 10000.0,
                    ternary_state: state.to_string(),
                });
            }
        }
    }

    conflicts
}

// ════════════════════════════════════════════════════════════════
// Donor Search (batch)
// ════════════════════════════════════════════════════════════════

#[pyclass]
#[derive(Clone, Debug)]
struct RustDonor {
    #[pyo3(get)]
    module_name: String,
    #[pyo3(get)]
    donor_axis: String,
    #[pyo3(get)]
    donor_score: f64,
    #[pyo3(get)]
    distance: f64,
}

#[pyfunction]
fn find_donors(
    target_axis: &str,
    current_lv: &RustLossVector,
    corpus: Vec<(String, [f64; 5])>,  // (name, [5 scores])
    max_donors: usize,
) -> PyResult<Vec<RustDonor>> {
    let ax_idx = AXES.iter().position(|&a| a == target_axis)
        .ok_or_else(|| PyValueError::new_err(format!("Unknown axis: {target_axis}")))?;

    let mut donors: Vec<RustDonor> = corpus.iter()
        .filter(|(_, scores)| scores[ax_idx] >= LEAP_MIN_DONOR_SCORE)
        .map(|(name, scores)| {
            let other = RustLossVector {
                r_struct: scores[0], r_context: scores[1], r_qualia: scores[2],
                r_cultural: scores[3], r_temporal: scores[4],
            };
            RustDonor {
                module_name: name.clone(),
                donor_axis: target_axis.to_string(),
                donor_score: (scores[ax_idx] * 10000.0).round() / 10000.0,
                distance: current_lv.distance_to(&other),
            }
        })
        .collect();

    // Sort by donor_score descending
    donors.sort_by(|a, b| b.donor_score.partial_cmp(&a.donor_score).unwrap());
    donors.truncate(max_donors);
    Ok(donors)
}

// ════════════════════════════════════════════════════════════════
// Batch Analysis (analyze entire corpus at once)
// ════════════════════════════════════════════════════════════════

#[pyclass]
#[derive(Clone, Debug)]
struct RustBatchResult {
    #[pyo3(get)]
    loss_vectors: Vec<RustLossVector>,
    #[pyo3(get)]
    patterns: Vec<String>,
    #[pyo3(get)]
    magnitudes: Vec<f64>,
    #[pyo3(get)]
    dominant_axes: Vec<String>,
    #[pyo3(get)]
    void_counts: Vec<usize>,
}

#[pyfunction]
fn batch_analyze(scores_list: Vec<[f64; 5]>) -> PyResult<RustBatchResult> {
    let mut loss_vectors = Vec::with_capacity(scores_list.len());
    let mut patterns = Vec::with_capacity(scores_list.len());
    let mut magnitudes = Vec::with_capacity(scores_list.len());
    let mut dominant_axes = Vec::with_capacity(scores_list.len());
    let mut void_counts = Vec::with_capacity(scores_list.len());

    for s in &scores_list {
        // Validate
        for (i, &v) in s.iter().enumerate() {
            if !(0.0..=1.0).contains(&v) {
                return Err(PyValueError::new_err(
                    format!("{} must be in [0.0, 1.0], got {v}", AXES[i])
                ));
            }
        }

        let lv = RustLossVector {
            r_struct: s[0], r_context: s[1], r_qualia: s[2],
            r_cultural: s[3], r_temporal: s[4],
        };

        patterns.push(classify_loss_pattern(&lv));
        magnitudes.push(lv.magnitude());
        dominant_axes.push(lv.dominant_loss_axis());
        void_counts.push(lv.void_dimensions().len());
        loss_vectors.push(lv);
    }

    Ok(RustBatchResult {
        loss_vectors,
        patterns,
        magnitudes,
        dominant_axes,
        void_counts,
    })
}

// ════════════════════════════════════════════════════════════════
// Distance Matrix (for Void Exploration — all-pairs distances)
// ════════════════════════════════════════════════════════════════

#[pyfunction]
fn distance_matrix(vectors: Vec<[f64; 5]>) -> Vec<Vec<f64>> {
    let n = vectors.len();
    let mut matrix = vec![vec![0.0f64; n]; n];

    for i in 0..n {
        for j in (i + 1)..n {
            let d: f64 = vectors[i].iter().zip(vectors[j].iter())
                .map(|(a, b)| (a - b).powi(2))
                .sum::<f64>()
                .sqrt();
            matrix[i][j] = d;
            matrix[j][i] = d;
        }
    }

    matrix
}

// ════════════════════════════════════════════════════════════════
// Python Module
// ════════════════════════════════════════════════════════════════

#[pymodule]
fn ks42_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustLossVector>()?;
    m.add_class::<RustAxisConflict>()?;
    m.add_class::<RustDonor>()?;
    m.add_class::<RustBatchResult>()?;
    m.add_function(wrap_pyfunction!(classify_loss_pattern, m)?)?;
    m.add_function(wrap_pyfunction!(compute_tension, m)?)?;
    m.add_function(wrap_pyfunction!(get_semantic_tension, m)?)?;
    m.add_function(wrap_pyfunction!(detect_conflicts, m)?)?;
    m.add_function(wrap_pyfunction!(find_donors, m)?)?;
    m.add_function(wrap_pyfunction!(batch_analyze, m)?)?;
    m.add_function(wrap_pyfunction!(distance_matrix, m)?)?;

    // Constants
    m.add("AXES", AXES.to_vec())?;
    m.add("LOSS_THRESHOLD", LOSS_THRESHOLD)?;
    m.add("LEAP_MIN_DONOR_SCORE", LEAP_MIN_DONOR_SCORE)?;
    m.add("NOVELTY_TRIVIAL", NOVELTY_TRIVIAL)?;

    Ok(())
}
