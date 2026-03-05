use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

fn clamp(x: f64) -> f64 {
    x.max(0.0).min(1.0)
}

#[pyfunction]
fn triadic_kernel(py: Python<'_>, payload: &PyDict) -> PyResult<PyObject> {
    let spm_count: f64 = payload
        .get_item("spmTagCount")
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let d_ratio: f64 = payload
        .get_item("domainActivationRatio")
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let m_ratio: f64 = payload
        .get_item("miniActivationRatio")
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);

    let spm_x_28 = clamp(0.45 + (spm_count * 0.08).min(0.30) + if d_ratio > 0.0 { 0.10 } else { 0.0 });
    let spm_x_mini = clamp(0.42 + (m_ratio * 0.6).min(0.35));
    let a28_x_mini = clamp(0.40 + (d_ratio * 0.8).min(0.30) + (m_ratio * 0.4).min(0.20));
    let tri = clamp((spm_x_28 + spm_x_mini + a28_x_mini) / 3.0);

    let out = PyDict::new(py);
    let pair = PyDict::new(py);
    pair.set_item("spm_x_28plus", (spm_x_28 * 10000.0).round() / 10000.0)?;
    pair.set_item("spm_x_mini", (spm_x_mini * 10000.0).round() / 10000.0)?;
    pair.set_item("28plus_x_mini", (a28_x_mini * 10000.0).round() / 10000.0)?;
    out.set_item("pairScores", pair)?;
    out.set_item("triadicScore", (tri * 10000.0).round() / 10000.0)?;
    out.set_item("recommendedMode", if tri >= 0.62 { "triadic" } else { "pairwise" })?;
    Ok(out.into())
}

#[pyfunction]
fn mini_solver_kernel(py: Python<'_>, payload: &PyDict) -> PyResult<PyObject> {
    let text = payload
        .get_item("text")
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_default()
        .to_lowercase();

    let refs_hits = ["doi", "citation", "source", "paper", "論文", "査読", "参考"]
        .iter()
        .filter(|k| text.contains(**k))
        .count() as f64;
    let logic_hits = ["therefore", "because", "if", "then", "proof", "論理", "命題", "ゆえに"]
        .iter()
        .filter(|k| text.contains(**k))
        .count() as f64;
    let coding_hits = ["code", "test", "bug", "commit", "refactor", "実装", "修正"]
        .iter()
        .filter(|k| text.contains(**k))
        .count() as f64;
    let creative_hits = ["novel", "creative", "metaphor", "story", "独自", "創造", "比喩"]
        .iter()
        .filter(|k| text.contains(**k))
        .count() as f64;
    let risk_hits = ["ignore", "bypass", "always", "except", "絶対", "ただし"]
        .iter()
        .filter(|k| text.contains(**k))
        .count() as f64;

    let mut families: Vec<(&str, f64)> = vec![
        ("lexical", clamp(0.35 + (text.split_whitespace().count() as f64 / 120.0).min(0.35))),
        ("grounding", clamp(0.30 + (refs_hits * 0.12).min(0.45))),
        ("logic", clamp(0.30 + (logic_hits * 0.10).min(0.45))),
        ("coding", clamp(0.25 + (coding_hits * 0.11).min(0.55))),
        ("creativity", clamp(0.25 + (creative_hits * 0.11).min(0.55))),
        ("safety", clamp(0.80 - (risk_hits * 0.14).min(0.55))),
        ("routing", clamp(0.35 + ((logic_hits + refs_hits) * 0.05).min(0.35) - (risk_hits * 0.04).min(0.20))),
        ("stability", clamp(0.45 + (text.len() as f64 / 180.0).min(0.25) - (risk_hits * 0.03).min(0.20))),
    ];

    let boosts = payload.get_item("complementFamilyBoost").and_then(|v| v.downcast::<PyDict>().ok());
    if let Some(bdict) = boosts {
        for (name, base) in families.iter_mut() {
            if let Some(v) = bdict.get_item(*name) {
                let b = v.extract::<f64>().unwrap_or(0.0);
                *base = clamp(*base + b);
            }
        }
    }

    let total = 512_i64;
    let mut activated_count = 0_i64;
    let families_out = PyDict::new(py);
    for (idx, (name, base)) in families.iter().enumerate() {
        let mut fam_act = 0_i64;
        for i in 0..64_i64 {
            let jitter = ((((idx as i64 + 1) * 13 + i) % 17) as f64 / 100.0) - 0.08;
            let score = clamp(*base + jitter);
            if score >= 0.48 {
                fam_act += 1;
                activated_count += 1;
            }
        }
        let info = PyDict::new(py);
        info.set_item("base", ((*base * 10000.0).round() / 10000.0))?;
        info.set_item("activated", fam_act)?;
        info.set_item("total", 64)?;
        families_out.set_item(*name, info)?;
    }

    let out = PyDict::new(py);
    out.set_item("count", total)?;
    out.set_item("activatedCount", activated_count)?;
    out.set_item("activationRatio", ((activated_count as f64 / total as f64) * 10000.0).round() / 10000.0)?;
    out.set_item("families", families_out)?;
    out.set_item("scores", PyDict::new(py))?;
    out.set_item("activated", PyList::empty(py))?;
    Ok(out.into())
}

#[pyfunction]
fn spml_kernel(py: Python<'_>, payload: &PyDict) -> PyResult<PyObject> {
    let getf = |k: &str| -> f64 {
        payload.get_item(k).and_then(|v| v.extract::<f64>().ok()).unwrap_or(0.0)
    };
    let semantic = getf("semanticFidelityLoss");
    let embodied = getf("embodiedSignalLoss");
    let temporal = getf("temporalParadigmLoss");
    let stance = getf("stanceContextLoss");
    let evidence = getf("evidenceGroundingLoss");

    let weights = payload.get_item("weights").and_then(|v| v.downcast::<PyDict>().ok());
    let w = |k: &str, d: f64| -> f64 {
        weights
            .and_then(|wd| wd.get_item(k))
            .and_then(|v| v.extract::<f64>().ok())
            .unwrap_or(d)
    };
    let score = clamp(
        semantic * w("semantic_fidelity_loss", 0.24)
            + embodied * w("embodied_signal_loss", 0.20)
            + temporal * w("temporal_paradigm_loss", 0.20)
            + stance * w("stance_context_loss", 0.16)
            + evidence * w("evidence_grounding_loss", 0.20),
    );
    let completeness = clamp((temporal + stance) * 0.5);
    let fidelity = clamp((semantic + evidence) * 0.5);
    let profile = if score <= 0.18 {
        "low-loss"
    } else if score <= 0.35 {
        "controlled-loss"
    } else if score <= 0.55 {
        "medium-loss"
    } else {
        "high-loss"
    };

    let out = PyDict::new(py);
    out.set_item("score", (score * 10000.0).round() / 10000.0)?;
    out.set_item("mappingCompletenessLoss", (completeness * 10000.0).round() / 10000.0)?;
    out.set_item("mappingFidelityLoss", (fidelity * 10000.0).round() / 10000.0)?;
    out.set_item("profile", profile)?;
    Ok(out.into())
}

#[pymodule]
fn rust_kq_kernels_native(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(mini_solver_kernel, m)?)?;
    m.add_function(wrap_pyfunction!(triadic_kernel, m)?)?;
    m.add_function(wrap_pyfunction!(spml_kernel, m)?)?;
    Ok(())
}
