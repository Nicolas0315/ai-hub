use pyo3::prelude::*;
use std::collections::HashSet;

fn layer_num(s: &str) -> i32 {
    s.trim_start_matches('L').parse::<i32>().unwrap_or(0)
}

#[pyfunction]
fn invariant_preservation_score(
    truth_conflict: bool,
    provability_ratio: f64,
    counterexample_consistent: bool,
    l2f: f64,
    f2p: f64,
    p2h: f64,
) -> f64 {
    let score = 0.45 * (1.0 - if truth_conflict { 1.0 } else { 0.0 })
        + 0.30 * provability_ratio
        + 0.15 * if counterexample_consistent { 1.0 } else { 0.0 }
        + 0.10 * ((l2f + f2p + p2h) / 3.0);
    (score * 10000.0).round() / 10000.0
}

#[pyfunction]
fn strict_specificity_score(spec: String) -> f64 {
    let s = spec.to_lowercase();
    let has_struct = s.contains("and(") || s.contains("forall") || s.contains("exists") || s.contains("vars:");
    if has_struct { 1.0 } else { 0.6 }
}

#[pyfunction]
fn dense_dependency_edges(
    node_ids: Vec<String>,
    node_layers: Vec<String>,
    node_morphisms: Vec<String>,
    node_invariants: Vec<String>,
    explicit_edges: Vec<(String, String)>,
) -> Vec<(String, String)> {
    let ids: HashSet<String> = node_ids.iter().cloned().collect();
    let mut out: HashSet<(String, String)> = HashSet::new();

    for (a, b) in explicit_edges.iter() {
        if a != b && ids.contains(a) && ids.contains(b) {
            out.insert((a.clone(), b.clone()));
        }
    }

    for i in 0..node_ids.len() {
        for j in 0..node_ids.len() {
            if i == j {
                continue;
            }
            if layer_num(&node_layers[j]) >= layer_num(&node_layers[i]) {
                continue;
            }
            let same_m = !node_morphisms[j].is_empty() && node_morphisms[j] == node_morphisms[i];
            let same_inv = !node_invariants[j].is_empty() && node_invariants[j] == node_invariants[i];
            let prev_bridge = layer_num(&node_layers[i]) - layer_num(&node_layers[j]) == 1;
            if same_m || same_inv || prev_bridge {
                out.insert((node_ids[j].clone(), node_ids[i].clone()));
            }
        }
    }

    let mut v: Vec<(String, String)> = out.into_iter().collect();
    v.sort();
    v
}

#[pymodule]
fn katala_rust_hotpath(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(invariant_preservation_score, m)?)?;
    m.add_function(wrap_pyfunction!(strict_specificity_score, m)?)?;
    m.add_function(wrap_pyfunction!(dense_dependency_edges, m)?)?;
    Ok(())
}
