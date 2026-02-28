use ks40b_lite::KS40bLite;

#[test]
fn test_arithmetic_correct() {
    let ks = KS40bLite::new();
    let r = ks.verify("2+2=4", None, None);
    assert!(r.pass_rate > 0.5, "2+2=4 should pass: rate={}", r.pass_rate);
    assert_eq!(r.detected_layer, "math");
}

#[test]
fn test_arithmetic_wrong() {
    let ks = KS40bLite::new();
    let r = ks.verify("2+2=5", None, None);
    assert!(r.pass_rate < 1.0, "2+2=5 should have issues");
}

#[test]
fn test_self_contradiction() {
    let ks = KS40bLite::new();
    let r = ks.verify("It is both true and false", None, None);
    assert!(r.pass_rate < 1.0, "self-contradiction should be caught");
}

#[test]
fn test_natural_language() {
    let ks = KS40bLite::new();
    let r = ks.verify("地球は太陽系の惑星である", None, None);
    assert_eq!(r.detected_layer, "natural_language");
}

#[test]
fn test_htlf_same_layer() {
    let ks = KS40bLite::new();
    let r = ks.verify("Hello world", None, Some("Hello world"));
    assert!(r.translation_loss.total_loss < 0.2, "same-layer should have low loss");
}

#[test]
fn test_coherence() {
    let ks = KS40bLite::new();
    let r = ks.verify("2+2=4", None, None);
    assert!(r.coherence_score > 0.5, "consistent results should have high coherence");
}

#[test]
fn test_needs_llm_review() {
    let ks = KS40bLite::new();
    // Ambiguous claim that deterministic solvers can't fully resolve
    let r = ks.verify("The economy will grow by 3% next year", None, None);
    // This should flag for LLM review since solvers can't verify predictions
    assert!(r.needs_llm_review || r.pass_rate > 0.5, "ambiguous claims should be flagged or pass");
}
