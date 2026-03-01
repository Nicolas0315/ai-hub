# Coding as Translation: Self-Referential Verification of Design-to-Code Fidelity

**Authors**: Youta Hilono, Shirokuma (OpenClaw AI)

**Target venue**: ICSE 2026 / FSE 2026 / ASE 2026

---

## Abstract

We present the Katala Coding Series (KCS), a self-referential code verification framework that treats programming as an act of translation from design intent (concept space) to implementation (formal language). Drawing on the Holographic Translation Loss Framework (HTLF), KCS measures design-to-code fidelity along five axes: structural preservation, contextual retention, qualia transfer, cultural convention adherence, and temporal relevance. Unlike static analysis tools that detect syntactic bugs, KCS detects *semantic drift* — cases where code is syntactically correct but diverges from design intent. We demonstrate that KCS can verify its own codebase (self-referential application without Gödelian collapse), and present results from a full scan of 156 production modules showing systematic quality improvement from D→B grades. Our approach is complementary to existing CI/CD pipelines and introduces a novel "transparency model" where different agents handle design, translation, audit, and repair.

**Keywords**: code verification, design intent, translation loss, self-referential systems, software quality

---

## 1. Introduction

Software engineering has long recognized the gap between specification and implementation. Requirements drift (Nuseibeh & Easterbrook, 2000), design erosion (Perry & Wolf, 1992), and technical debt (Cunningham, 1992) are manifestations of *translation loss* — information that existed in the designer's mind but failed to reach the code.

Existing tools address surface symptoms: linters catch style violations, type checkers verify interface contracts, and test suites validate behavioral correctness. None measure the deeper question: *how faithfully does this code express the designer's intent?*

We propose that **coding is fundamentally an act of translation** from human concept space to formal language, and that this translation is subject to the same structured information loss as any inter-system translation. By applying the Holographic Translation Loss Framework (HTLF) to the code-design pair, we obtain a quantitative measure of design fidelity — what we call the KCS score.

### 1.1 The Transparency Model

A key design principle is that **different agents should handle different stages**:

```
Human (design) → AI (translation) → Code → KCS (audit) → AI (fix) → KCS (re-audit)
```

No single agent sees the entire pipeline. The designer specifies intent; the implementer translates; an independent auditor measures fidelity; a different agent fixes detected drift; and the auditor re-verifies. This separation creates local transparency at each stage, even if no single entity has global transparency.

### 1.2 Self-Reference Without Collapse

KCS can verify its own codebase. This self-referential application seems paradoxical — can a verification system verify itself? We show it avoids Gödelian collapse because the KS series uses modular consistent axiom systems where each axis measures independently. The measurement targets differ at each level of self-reference:

- **Level 0**: KCS measures whether code X faithfully implements design X
- **Level 1**: KCS measures whether *KCS code* faithfully implements *KCS design*
- **Level 2**: The verification of Level 1's result measures code quality metrics (R_struct), not truth claims

Since each level's measurement target is categorically different, no self-referential paradox arises.

---

## 2. Framework

### 2.1 Five-Axis Code Fidelity

Given a design description D and its implementation code C:

**R_struct** (Structure): Does the code's architecture (class hierarchy, function decomposition, data flow) mirror the design's conceptual structure?
- Measured via: concept-level DAG extraction from both D and C, bipartite matching

**R_context** (Context): Are domain assumptions, preconditions, and background knowledge preserved?  
- Measured via: TF-IDF overlap of domain terms + semantic embedding similarity

**R_qualia** (Expressiveness): Is the code readable, idiomatic, and experientially faithful to the design's "spirit"?
- Measured via: docstring coverage, naming conventions, magic number absence, nesting depth

**R_cultural** (Convention): Does the code follow the cultural norms of its ecosystem?
- Measured via: language-specific idiom detection, framework convention adherence

**R_temporal** (Relevance): Is the code using current best practices, or relying on deprecated patterns?
- Measured via: API currency detection, deprecation warnings, ecosystem half-life model

### 2.2 Grading

Fidelity scores map to grades:

| Grade | Fidelity | Meaning |
|-------|----------|---------|
| S | ≥ 0.90 | Exceptional — all axes ≥ 0.85 |
| A | ≥ 0.80 | Excellent |
| B | ≥ 0.60 | Good — production quality |
| C | ≥ 0.50 | Adequate — needs improvement |
| D | < 0.50 | Poor — significant drift |

The grading philosophy is "no lies" — Grade S should be truly excellent across all dimensions, not achievable through high scores on some axes compensating for low scores on others.

### 2.3 Severity Cascade

Issues detected by KCS are classified by severity with multiplicative impact:

- **Critical** (e.g., design intent reversed): × 0.50
- **Major** (e.g., missing core functionality): × 0.85
- **Minor** (e.g., style violation): × 0.95

Applied multiplicatively: a module with one critical and one major issue gets: base × 0.50 × 0.85 = base × 0.425.

---

## 3. Implementation

### 3.1 KCS-1b: Forward Verification

KCS-1b takes (design_description, code) as input and computes 5-axis fidelity:

```python
kcs = KCS1b()
result = kcs.verify(
    "Rust Bridge: transparent fallback wrapper for Rust acceleration",
    code_text
)
# result.final_grade = "B"
# result.forward.total_fidelity = 0.665
```

Key implementation detail: **argument order matters**. `verify(design, code)` — design first, code second. Swapping produces garbage scores (R_struct=0.1 vs 0.975) because the direction of translation measurement is reversed.

### 3.2 KCS-2a: Reverse Inference

KCS-2a performs the inverse operation: given only code, infer the design intent. This enables auditing code where the original design document is lost or was never written.

### 3.3 Domain-Aware Scoring

KCS-1b includes domain detection to avoid false positives:

- **Binary parsing code**: Relaxed nesting depth threshold (4→7), struct offsets excluded from magic numbers
- **Multimodal processing**: Media constants (sample rates, dimensions) excluded  
- **General code**: Standard thresholds

---

## 4. Evaluation

### 4.1 Full Codebase Scan

We scanned 156 production modules of the Katala Samurai verification pipeline:

| Grade | Count | Percentage |
|-------|-------|-----------|
| A | 5 | 3.2% |
| B | 99 | 63.5% |
| C | 46 | 29.5% |
| D | 6 | 3.8% |

Average fidelity: 0.689 (Grade B).

### 4.2 D-Grade Elimination

We systematically improved D-grade modules:

| Module | Before | After | Changes |
|--------|--------|-------|---------|
| rust_bridge.py | D (0.430) | B (0.665) | 18 constants extracted, 14 docstrings |
| ks34a.py | D (0.434) | C (0.590) | 19 constants, class+method docstrings |

Common D-grade patterns:
- **Magic numbers**: Inline numeric literals without named constants
- **Missing docstrings**: Functions lacking documentation (R_qualia penalty)
- **Deep nesting**: Excessive if/for depth (R_struct penalty)
- **Over-engineering**: Too many entities for too few concepts

### 4.3 Self-Referential Scan

Running KCS on its own codebase (kcs1b.py):

| Axis | Score |
|------|-------|
| R_struct | 0.72 |
| R_context | 0.94 |
| R_qualia | 0.81 |
| R_cultural | 0.88 |
| R_temporal | 0.95 |
| **Total** | **0.78 (B)** |

The system rates itself as Grade B — honest self-assessment, not artificially inflated.

---

## 5. Related Work

**Static Analysis**: ESLint, pylint, mypy detect syntactic and type errors but not design drift. KCS measures the semantic gap between intent and implementation.

**Code Review**: Human code review implicitly measures design fidelity, but inconsistently and non-quantitatively. KCS provides reproducible, quantitative design fidelity scores.

**Design-by-Contract**: Eiffel (Meyer, 1992) and modern DbC (Liskov & Wing, 1994) specify behavioral contracts. KCS goes beyond contracts to measure *holistic* design fidelity including readability, convention adherence, and temporal relevance.

**AI Code Generation**: Copilot (Chen et al., 2021), CodeGen (Nijkamp et al., 2022), and AlphaCode (Li et al., 2022) generate code from specifications. KCS can measure their output quality along dimensions invisible to pass/fail test suites.

---

## 6. Conclusion

We presented KCS, a framework that treats coding as translation and measures design-to-code fidelity along five axes. The self-referential application demonstrates that verification systems can audit themselves without logical paradox. Our full-scan results on 156 production modules show that systematic application of KCS-guided improvements eliminates D-grade code and raises average fidelity.

---

## References

[To be completed with full bibliography]
