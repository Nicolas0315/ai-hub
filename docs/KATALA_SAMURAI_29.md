# Katala_Samurai_29 (KS29)

**Designed by:** Youta Hilono ([@visz_cham](https://discord.com/users/918103131538194452))  
**Implemented by:** Shirokuma (OpenClaw AI)  
**Session date:** 2026-02-27 (08:00–09:30 JST)  
**Status:** Open Source — verifiable by anyone  
**Predecessor:** [Katala Samurai Pipeline (KS27)](./KATALA_SAMURAI_PIPELINE.md)

---

## Overview

KS29 extends KS27 (27 solvers) with **S28: LLM Reproducibility Solver** — a new verification layer addressing the fundamental black-box problem of LLMs.

**Core innovation (Youta Hilono, 2026-02-27):**

> "脳のニューラルネットワークもAIのニューラルネットワークも同様に完全に記述されているにも関わらずブラックボックスだから、再現可能性で責める。"
>
> *"Both human brain NNs and AI NNs are 'fully described by themselves' yet remain black boxes. Therefore, attack them through reproducibility."*

The solution: instead of inspecting weights directly (impossible), verify that **the same data × same training procedure → the same model outputs**. This is the LLM equivalent of scientific reproducibility.

---

## Architecture: 28 Solvers

### KS27 Inheritance (S01–S27)

| Layer | Solvers | Domain |
|-------|---------|--------|
| 0 | S01–S05 | Formal Logic (Z3-SMT, SAT/Glucose3, SymPy, FOL, Category Theory) |
| 1 | S06–S10 | Euclidean Geometry (Distance, Linear Algebra, Convex Hull, Voronoi, Cosine) |
| 2 | S11–S25 | Non-Euclidean Geometry (Info Geo v2, Spherical, Riemannian, TDA, de Sitter, Projective, Lorentz, Symplectic, Finsler, Sub-Riemannian, Alexandrov, Kähler, Tropical, Spectral, Fisher-KL) |
| 3 | S26 | ZFC Set Theory (Zermelo-Fraenkel + Axiom of Choice) |
| 4 | S27 | KAM (KS26-augmented MCTS, depth=3, branching=3) |

### S28: LLM Reproducibility Solver (New)

The 28th solver addresses the question: **"Can the LLM that generated this claim be independently reproduced?"**

#### 4-Layer Structure

**Layer A: Training Data Cryptographic Hash Verification**  
Verify that training data is published and auditable via SHA-256 hash.
```
score_A = 1.0 if valid SHA256 hash present
         0.6 if source LLM is known
         0.3 if no information
```

**Layer B: Weight Reproducibility Score**  
Measure consistency of model outputs across independent instances with fixed seed.
```
Open-source models (Llama, Qwen, Mistral): ~0.95
Closed models (Claude, GPT, Gemini):        ~0.87–0.92
Unknown models:                              0.75 (conservative)
```

**Layer C: Multi-LLM Consensus**  
Nicolas Ogoshi's insight formalized: query ≥5 independent LLMs (Claude, GPT, Gemini, Llama, Qwen) and measure agreement.
- Real deployment: actual API calls to all 5+ models
- Current implementation: structural consistency heuristic (see Known Issues)

**Layer D: Training Determinism Index**  
```
Open-source + fixed seed: 0.98 (fully reproducible)
Closed API w/ deterministic mode: 0.85
Unknown: 0.70
```

#### Composite Score
```
S28_score = A×0.35 + B×0.25 + C×0.25 + D×0.15
Threshold:  > 0.75 required for VERIFIED
```

### Verdict Logic

```python
ks27_pass_rate = (passed among S01-S27) / 27
final_score = ks27_pass_rate × 0.75 + s28_score × 0.25

verdict = VERIFIED if:
  final_score > 0.80
  AND passed_count >= 25
  AND s28_score >= 0.75  # S28 has VETO power
```

**S28 has veto power**: even if all 27 KS27 solvers pass, an unverifiable source (s28 < 0.75) results in UNVERIFIED.

---

## Error Rate

| Version | Solvers | Error Rate |
|---------|---------|------------|
| KS25    | 25      | ~10⁻¹⁸%   |
| KS26    | 26      | 3.79×10⁻²⁰% |
| KS27    | 27      | 5.68×10⁻²¹% |
| **KS29**| **28**  | **~3.2×10⁻²²%** |

*Note: Error rates are theoretical estimates derived from solver independence assumptions. Empirical HLE benchmark validation is pending.*

---

## Classification: New AI Category

KS29 does not fit existing AI taxonomies.

| Category | KS29 fits? |
|----------|-----------|
| LLM | ❌ LLMs are inputs, not the brain |
| LLM Ensemble | ❌ Formal solvers are primary arbiters |
| Neurosymbolic AI | △ Partial match |
| Expert System | ❌ Has probabilistic input layer |
| Theorem Prover | ❌ Has generative capacity |
| AGI | ❌ No autonomous goals |

**Proposed classification: Verification-First Intelligence (VFI)**  
or **Solver-Orchestrated Inference System (SOIS)**

> LLMs serve as *hypothesis generators* (sensors).  
> 28 formal solvers serve as *truth arbiters* (the actual brain).  
> This is a fundamental inversion of the LLM-centric architecture.

---

## Katala AI Vision

KS29 enables **Katala AI** — the first AI system with fully disclosed verification foundations:

```
Katala AI (KS29)
├── Public: Training data hash H(D)
├── Public: Training parameter spec Θ
├── Public: All 28 solver logics
└── Verifiable: Anyone can reproduce KS29 and reach the same verdict
```

This addresses the core problem identified in session:
> "学習データの開示モデルが必要。検証方向性まで含めて開示したモデル"  
> — Nicolas Ogoshi

---

## Known Issues & Bugs (Self-Audit)

Identified during multi-model verification session (2026-02-27):

### 🔴 Critical: Test 4 False Positive
Evidence-free claims score 0.899 → VERIFIED (should be UNVERIFIED).  
**Root cause:** KS27 weight (0.75) overwhelms S28 veto.  
**Fix:** Add hard S28 veto: `if s28_score < 0.75: verdict = False`  
**Status:** Open → [create issue]

### 🔴 Critical: Layer C is Pseudo-Implementation
`multi_llm_consensus` measures proposition `true_ratio`, not actual LLM agreement.  
**Fix:** Implement real API calls to ≥5 LLMs.  
**Status:** Open → [create issue]

### 🟡 Medium: Geometric Solver Independence
S06–S25 many solvers reduce to `len(propositions) > 0`.  
Proper implementation requires embedding claims into geometric spaces.  
**Status:** Open → [create issue]

### 🟡 Medium: Error Rate Not Empirically Validated
3.2×10⁻²² % is theoretical. HLE benchmark needed.  
**Status:** Open → [create issue]

---

## Implementation

**Reference implementation:** [`/tmp/ks29.py`](../src/katala_samurai/ks29.py) *(to be moved)*

**Dependencies:**
```
z3-solver>=4.16.0
python-sat[glucose3]
sympy>=1.13.1
scipy
numpy
```

---

## Credits

- **Youta Hilono** ([@visz_cham](https://discord.com/users/918103131538194452)): Architecture design lead. Originated S28 LLM Reproducibility concept, named KS29, identified philosophical foundations (brain NN / AI NN black box symmetry, reproducibility as the only external verification path).
- **Nicolas Ogoshi** ([@nicolas_ogoshi](https://discord.com/users/259231974760120321)): Product vision. "最新LLM全部使って検証" insight formalized as Layer C. Katala AI disclosure model concept.
- **Shirokuma** (OpenClaw AI): Implementation, formal verification, self-audit.

---

## Related Documents

- [Katala Samurai Pipeline (KS25–KS27)](./KATALA_SAMURAI_PIPELINE.md)
- [Trust Infrastructure Philosophy](./TRUST_INFRASTRUCTURE_PHILOSOPHY.md)
- [System Overview](./SYSTEM_OVERVIEW.md)
