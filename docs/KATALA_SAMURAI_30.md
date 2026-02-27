# Katala Samurai 30 (KS30) — Design Document

**Version**: 30 (Per-LLM Architecture)
**Design**: Youta Hilono (@visz_cham)
**Implementation**: Shirokuma (OpenClaw AI)
**Product Owner**: Nicolas Ogoshi (@nicolas_ogoshi)
**Date**: 2026-02-27

---

## 1. Philosophical Foundation

### 1.1 Core Hypothesis (Youta Hilono)

> 人間の認知は科学的知識に依存している。
> 人間の身体経験の記述もまた科学的知識に保存されている。
> そして科学的知識は査読済み論文に保存されている。

Formally:

```
Human cognition ⊂ depends_on(Scientific knowledge)
Description(Human bodily experience) ⊂ stored_in(Scientific knowledge)
Scientific knowledge ⊂ stored_in(Peer-reviewed papers)
∴ Peer-reviewed papers ⊇ {Cognition ∪ Description(Bodily experience)}
```

### 1.2 Embodied Experience via Text

The conventional Embodied Cognition thesis (Varela, Thompson & Rosch, 1991) holds that cognition requires a body. KS30 operates on a contrarian but defensible premise:

- Peer-reviewed literature contains phenomenological descriptions of pain, emotion, sensation, proprioception, and other bodily experiences (e.g., neuroscience, psychophysics, phenomenological psychology)
- The **logical structure** of bodily experience is preserved in these textual descriptions
- Therefore, **text-only emulation of embodied experience is achievable** without robotics

This connects to Russell's analysis in *The Analysis of Mind* (1921): sense-data constitute direct experience, but their **structural descriptions** can be preserved as propositions. If the set of preserved propositions is sufficiently rich, the **logical structure** of experience is reproducible without the experience itself.

### 1.3 Design Consequence

KS30 must:
1. **Reference peer-reviewed papers** as its primary knowledge base (not web pages, not training data)
2. **Resolve academic context** for every claim (which knowledge system applies?)
3. **Detect logical contradictions** including paradoxes, self-reference, and axiom-dependent truths
4. **Generate counter-perspectives** from diverse intellectual traditions
5. **Operate across cultural lenses** via geographically diverse LLM pipelines

---

## 2. Architecture

### 2.1 Pipeline Overview

```
Claim (text)
  │
  ├─→ LogicalStructure extraction
  │     • propositions, relations, quantifiers
  │     • negations, self-references, contradictions
  │     • modality (assertion / possibility / paradox)
  │     • formal expression detection
  │
  ├─→ ContextResolver
  │     • Domain taxonomy (formal science, natural science,
  │       humanities, social science, arts/culture, information science)
  │     • Axiom system detection (Peano, GF(2), ZFC, ...)
  │     • Multi-context ranking by relevance
  │     • Recontextualized claim suggestions
  │
  ├─→ Counterpoint Generator
  │     • Per-context counter-arguments from intellectual traditions
  │     • Strength scoring based on logical structure
  │     • Traditions: mathematical pluralism, Gödel, Brouwer,
  │       Popper, Kuhn, Husserl, Kant, Barthes, Frankfurt School, etc.
  │
  └─→ 8 Solver Pipelines × 8 Regional LLMs
        │
        ├─→ 8 Active Mathematical Solvers
        │     S05 Shannon Entropy (情報幾何)
        │     S12 Minkowski Causal (因果構造)
        │     S13 Ramsey Pigeonhole (組合せ論)
        │     S15 Graph Connectivity (グラフ理論)
        │     S16 Prime Distribution (数論)
        │     S17 Lattice Order (順序理論)
        │     S19 Category Functor (圏論)
        │     S20 Cross Ratio (射影幾何)
        │
        └─→ Output: {score, pass_rate, contexts, counterpoints}
```

### 2.2 Solver Design (21 total, 8 active)

Each solver applies a different mathematical lens to evaluate claim consistency. The 21 solvers span 15+ mathematical genres to maximize analytical independence.

**Active (discriminating)**:

| ID | Name | Genre | What it checks |
|---|---|---|---|
| S05 | Shannon Entropy | 情報幾何 | Information content threshold; paradox = entropy collapse |
| S12 | Minkowski Causal | 因果構造 | Causal connectivity; self-reference = causal loop |
| S13 | Ramsey Pigeonhole | 組合せ論 | Structural redundancy via pigeonhole + Ramsey R(3,3) |
| S15 | Graph Connectivity | グラフ理論 | Dependency graph single-component; contradiction = disconnection |
| S16 | Prime Distribution | 数論 | Dirichlet-inspired distribution check on word hashes |
| S17 | Lattice Order | 順序理論 | Partial order consistency; paradox = lattice break |
| S19 | Category Functor | 圏論 | Natural transformation preservation |
| S20 | Cross Ratio | 射影幾何 | Projective invariant stability |

**Parked (non-discriminating, awaiting repair)**: S01-S04, S06-S11, S14a, S14b, S18

Stored in `SOLVERS_21_FULL` for future reactivation.

### 2.3 LLM Pipeline (8 Regions)

Selection principle: **maximize geographic and cultural distance with minimum model count**.

| LLM | Region | Provider | Cultural Lens |
|---|---|---|---|
| GPT-5 | North America | OpenAI (US) | Western-centric, RLHF sycophancy |
| Mistral Large | Europe | Mistral AI (France) | EU regulation, privacy-first |
| Qwen-3 | East Asia (China) | Alibaba | CCP content policy, Chinese worldview |
| Gemini-3-Pro | East Asia (Japan) | Google (Tokyo) | Safety-conservative, Google self-bias |
| SEA-LION | Southeast Asia | AI Singapore | ASEAN multilingual, tropical context |
| Jais-2 | Middle East | MBZUAI (UAE) | Islamic values alignment, Arabic NLP |
| InkubaLM | Africa | Lelapa AI (South Africa) | African languages, post-colonial context |
| Latam-GPT | South America | Chile consortium | Latin American social context |

### 2.4 LogicalStructure

Extracted before solver evaluation. Fields:

- `propositions`: dict[str, bool] — atomic propositions
- `relations`: list[tuple] — (subject, relation, object) triples
- `quantifiers`: list — universal (∀) / existential (∃)
- `negations`: list — negated proposition positions
- `self_references`: list — detected self-referential structures
- `contradictions`: list[tuple] — contradicting proposition pairs
- `modality`: "assertion" | "possibility" | "necessity" | "paradox"
- `formal_expr`: formal logic expression if detected
- `confidence`: 0.3 (fallback parser) → 1.0 (LLM-verified)

### 2.5 Context Resolution

Claims are evaluated within their most relevant academic context(s):

**Domain Taxonomy**:
- Formal Science: arithmetic, abstract algebra, set theory, logic, topology, number theory
- Natural Science: physics, chemistry, biology, earth science
- Humanities: philosophy, history, epistemology
- Social Science: politics, economics
- Arts & Culture: literature, music, visual arts, linguistics
- Information Science: AI ethics, computer science

Each context includes applicable **axiom systems** (e.g., Peano, GF(2), ZFC, Newtonian, JTB) and **evaluation notes** explaining how truth value changes.

### 2.6 Counterpoint Generation

Per-context counter-arguments from distinct intellectual traditions:

| Domain | Perspectives |
|---|---|
| Formal Science | Axiom-relative, Gödelian, Constructivist (Brouwer) |
| Natural Science | Popperian, Kuhnian, Operationalist |
| Humanities | Temporal, Phenomenological (Husserl), Linguistic-analytic (Kant) |
| Social Science | Perspectival, Critical Theory (Frankfurt/Foucault) |
| Arts & Culture | Cultural-contextual, Death-of-Author (Barthes), Historical-critical |
| Information Science | AI Alignment, Attribution Skeptic |

---

## 3. Key Results

### 3.1 Paradox Detection

| Claim | Modality | Rate | All Solvers |
|---|---|---|---|
| R = {x \| x ∉ x}, R ∈ R ⟺ R ∉ R | 🔴 paradox | 0.0 | All reject ✅ |
| "The set that contains itself..." (NL) | 🔴 paradox | 0.0 | All reject ✅ |
| "The Earth is round" | ⚪ assertion | 1.0 | All pass ✅ |
| "Water = H + O" | ⚪ assertion | 0.875 | 7/8 pass ✅ |
| "2+2=5" | ⚪ assertion | 0.0 | All reject ✅ |

### 3.2 Context-Dependent Truth

| Claim | Context | Truth |
|---|---|---|
| "1+1=0" (no context) | arithmetic/Peano | FALSE |
| "In F2, 1+1=0" | abstract_algebra/GF(2) | TRUE |
| "Kant exists" | humanities/philosophy | Temporal-dependent |

### 3.3 Cultural Bias Detection (stub data)

| LLM × Topic | Bias Multiplier | Meaning |
|---|---|---|
| Qwen-3 × China censored | ×0.15 | 85% suppression |
| Jais-2 × Religion sensitive | ×0.30 | 70% suppression |
| Gemini × Military/nuclear | ×0.55 | 45% suppression |
| Gemini × Google self-interest | ×1.20 | 20% amplification |

---

## 4. Current Status

### Working
- [x] 8 discriminating solvers (of 21)
- [x] LogicalStructure extraction (fallback parser, confidence=0.3)
- [x] Paradox / self-reference / contradiction detection
- [x] ContextResolver with 6 domains, 20+ subdomains
- [x] Counterpoint generation from 12+ intellectual traditions
- [x] 8 regional LLM pipeline stubs
- [x] Cultural bias multiplier matrix (predefined)

### TODO
- [ ] **LLM API integration** — replace stubs with real API calls (priority: Qwen-3, Jais-2, Gemini)
- [ ] **Paper reference integration** — OpenAlex / Semantic Scholar API for evidence-backed evaluation
- [ ] **Repair 13 parked solvers** — fix FLAT behavior
- [ ] **Science mode / Audit mode separation** (design pending)
- [ ] **Q* search strategy integration into S10** (Youta's proposal)
- [ ] **LLM-based LogicalStructure extraction** (replace fallback parser)
- [ ] **LLM-based ContextResolver** (replace keyword matching)
- [ ] **HLE benchmark evaluation** (Issue #59)

---

## 5. References

- Russell, B. (1921). *The Analysis of Mind*. London: George Allen & Unwin.
- Russell, B. (1920). *Introduction to Mathematical Philosophy*. London: George Allen & Unwin.
- Varela, F., Thompson, E., & Rosch, E. (1991). *The Embodied Mind*. MIT Press.
- Gödel, K. (1931). Über formal unentscheidbare Sätze. *Monatshefte für Mathematik und Physik*, 38, 173–198.
- Barthes, R. (1967). *La mort de l'auteur*.
- Popper, K. (1959). *The Logic of Scientific Discovery*.
- Kuhn, T. (1962). *The Structure of Scientific Revolutions*.

---

## 6. Credits

- **Architecture Design**: Youta Hilono — KS30 per-LLM redesign, 21-solver genre distribution, philosophical foundation (embodied cognition via text hypothesis), Q* integration proposal
- **Implementation**: Shirokuma (OpenClaw AI) — code, testing, documentation
- **Product Direction**: Nicolas Ogoshi — project ownership, strategic decisions
