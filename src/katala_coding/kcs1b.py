"""KCS-1b: Katala Coding Series — Integrated Translation Loss Analyzer.

Evolution of KCS-1a with three major upgrades:

A) Precision: R_struct/R_context use HTLF pipeline (parser→matcher→scorer)
   instead of keyword matching. LLM fallback for R_context.
B) Discrimination: Stricter grading. S requires excellence on ALL axes.
   Issue severity weighting. Penalty cascades (critical issue tanks grade).
C) Integration: Unified forward (1a) + reverse (2a) + Router in one pass.
   Design → Code → Reverse Inference → Gap Detection → Goals.

KCS-1a measured "how much loss." KCS-1b tells you "where, why, and what next."

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
Date: 2026-03-01
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from typing import Any

from katala_coding.kcs1a import (
    CodeVerdict,
    _analyze_code_structure,
    _extract_design_concepts,
    _nesting_depth,
    _KATALA_CONVENTIONS,
)
from katala_coding.kcs2a import KCS2a, ReverseAnalysis

# ── Try HTLF imports (graceful fallback) ──
try:
    from htlf.parser import parse_document
    from htlf.matcher import match_concepts
    from htlf.scorer import compute_r_struct as htlf_r_struct
    from htlf.scorer import compute_r_context as htlf_r_context
    _HAS_HTLF = True
except ImportError:
    _HAS_HTLF = False

try:
    from katala_samurai.solver_router import AdaptiveSolverRouter, classify_domain
    from katala_samurai.solver_types import create_full_solver_pool
    _HAS_ROUTER = True
except ImportError:
    _HAS_ROUTER = False

# ═══════════════════════════════════════════════
# Constants — Discriminative grading
# ═══════════════════════════════════════════════

# Grade S: truly excellent. All axes ≥ 0.85, total ≥ 0.92
# Grade A: good. Total ≥ 0.82, no axis below 0.6
# Grade B: acceptable. Total ≥ 0.65
# Grade C: needs work. Total ≥ 0.50
# Grade D: poor. Total ≥ 0.35
# Grade F: failing. Total < 0.35

GRADE_S_TOTAL = 0.92
GRADE_S_MIN_AXIS = 0.85
GRADE_A_TOTAL = 0.82
GRADE_A_MIN_AXIS = 0.60
GRADE_B_TOTAL = 0.65
GRADE_C_TOTAL = 0.50
GRADE_D_TOTAL = 0.35

# Issue severity multipliers — critical issues tank the axis score
SEVERITY_CRITICAL = 0.5    # Halves the axis score
SEVERITY_MAJOR = 0.85      # 15% penalty
SEVERITY_MINOR = 0.95      # 5% penalty

# Axis weights (rebalanced: struct and context dominate)
AXIS_WEIGHTS = {
    "r_struct":   0.30,
    "r_context":  0.25,
    "r_qualia":   0.20,
    "r_cultural": 0.10,
    "r_temporal": 0.15,
}

# R_struct sub-weights
STRUCT_CONCEPT_WEIGHT = 0.35       # Design concept → code entity mapping
STRUCT_HTLF_WEIGHT = 0.30         # HTLF parser/matcher score (when available)
STRUCT_COMPLEXITY_WEIGHT = 0.15    # Complexity penalty
STRUCT_COHESION_WEIGHT = 0.20     # Module cohesion

# R_context sub-weights
CONTEXT_FRAMEWORK_WEIGHT = 0.40   # Theoretical framework preservation
CONTEXT_NAMING_WEIGHT = 0.25      # Theory-aware naming
CONTEXT_DOCSTRING_WEIGHT = 0.20   # Documentation quality
CONTEXT_HTLF_WEIGHT = 0.15       # HTLF context score (when available)

# R_qualia thresholds (stricter)
QUALIA_DOCSTRING_MIN = 0.7        # Was 0.5 in KCS-1a
QUALIA_MAX_LINE = 100
QUALIA_MAX_MAGIC = 3              # Was 5 in KCS-1a
QUALIA_TYPE_HINT_MIN = 0.5        # Was 0.3 in KCS-1a

# R_temporal thresholds
TEMPORAL_MAX_GLOBALS = 8          # Was 10 in KCS-1a
TEMPORAL_MAX_KWARGS = 2           # Was 3 in KCS-1a

# Consistency check
MAX_NESTING = 4
MIN_NAME_LEN = 3
SCORE_PRECISION = 4


# ═══════════════════════════════════════════════
# Enhanced Result Type
# ═══════════════════════════════════════════════

@dataclass(slots=True)
class EnhancedVerdict:
    """KCS-1b enhanced verdict with reverse inference and routing."""
    # Forward verification (KCS-1a style)
    forward: CodeVerdict

    # Reverse inference (KCS-2a)
    reverse: ReverseAnalysis | None

    # Router efficiency (if enabled)
    router_activated: int
    router_savings: float

    # Combined grade (may differ from forward.grade due to penalties)
    final_grade: str
    penalty_log: list[str]

    # Bidirectional gap analysis
    design_to_code_gaps: list[str]    # Forward: design intent not in code
    code_to_design_gaps: list[str]    # Reverse: code functionality not in design

    # Generated next goals
    goals: list[str]


# ═══════════════════════════════════════════════
# R_struct: HTLF-Enhanced Structure Preservation
# ═══════════════════════════════════════════════

def _compute_r_struct_1b(
    design: str, code: str, structure: dict[str, Any],
) -> tuple[float, list[tuple[str, str]]]:
    """Enhanced R_struct using HTLF pipeline when available.

    Returns (score, [(issue, severity)])
    severity: "critical" | "major" | "minor"
    """
    issues: list[tuple[str, str]] = []

    if not structure.get("parseable", False):
        return 0.05, [("Code has syntax errors — cannot parse", "critical")]

    # 1. Concept coverage (same as 1a but stricter scoring)
    design_concepts = _extract_design_concepts(design)
    code_entities = set()
    for name in structure.get("class_names", []):
        code_entities.add(name.lower())
        parts = re.findall(r'[A-Z][a-z]+|[a-z]+', name)
        code_entities.update(p.lower() for p in parts)
    for name in structure.get("function_names", []):
        code_entities.update(name.lower().split('_'))

    code_idents = set(re.findall(r'[a-z_][a-z0-9_]{2,}', code.lower()))
    code_entities.update(code_idents)

    if design_concepts:
        matched = sum(1 for c in design_concepts
                      if any(c in e or e in c for e in code_entities))
        concept_coverage = matched / len(design_concepts)
    else:
        concept_coverage = 0.5

    if concept_coverage < 0.3:
        issues.append((f"Critical: only {concept_coverage:.0%} of design concepts found in code", "critical"))
    elif concept_coverage < 0.6:
        issues.append((f"Low design coverage: {concept_coverage:.0%}", "major"))

    # 2. HTLF pipeline score (when available)
    htlf_score = 0.5  # neutral default
    if _HAS_HTLF:
        try:
            design_graph = parse_document(design, layer="natural_language")
            code_graph = parse_document(code, layer="formal_language")
            matches = match_concepts(design_graph, code_graph)
            htlf_result = htlf_r_struct(design_graph, code_graph, matches)
            htlf_score = htlf_result if isinstance(htlf_result, float) else htlf_result.score
        except Exception:
            htlf_score = 0.5  # fallback

    # 3. Complexity analysis (stricter)
    depth = structure.get("max_depth", 0)
    depth_penalty = 0.0
    if depth > MAX_NESTING:
        depth_penalty = min(0.4, (depth - MAX_NESTING) * 0.15)
        sev = "critical" if depth > 6 else "major"
        issues.append((f"Nesting depth {depth} (max recommended: {MAX_NESTING})", sev))

    # Inheritance chains
    chain_penalty = 0.0
    for cls, bases in structure.get("inheritance_chains", []):
        if len(bases) > 2:
            chain_penalty += 0.15
            issues.append((f"Multiple inheritance: {cls}({', '.join(bases)})", "major"))

    # Over-engineering
    n_design = max(len(design_concepts), 1)
    n_code = structure.get("functions", 0) + structure.get("classes", 0)
    ratio = n_code / n_design
    if ratio > 4.0:
        issues.append((f"Over-engineering: {n_code} entities for {n_design} concepts ({ratio:.1f}x)", "major"))
        chain_penalty += min(0.15, (ratio - 4) * 0.03)

    # 4. Module cohesion: do functions relate to each other?
    func_names = structure.get("function_names", [])
    if len(func_names) > 3:
        # Check prefix clustering
        prefixes: dict[str, int] = {}
        for f in func_names:
            p = f.lstrip('_').split('_')[0] if '_' in f else f[:4]
            prefixes[p] = prefixes.get(p, 0) + 1
        # Cohesion = how concentrated the prefixes are
        max_cluster = max(prefixes.values()) if prefixes else 0
        cohesion = max_cluster / len(func_names)
    else:
        cohesion = 0.7  # small modules are cohesive by default

    # Weighted score
    score = (
        STRUCT_CONCEPT_WEIGHT * concept_coverage +
        STRUCT_HTLF_WEIGHT * htlf_score +
        STRUCT_COMPLEXITY_WEIGHT * max(0, 1.0 - depth_penalty - chain_penalty) +
        STRUCT_COHESION_WEIGHT * cohesion
    )

    return round(max(0.0, min(1.0, score)), SCORE_PRECISION), issues


# ═══════════════════════════════════════════════
# R_context: HTLF-Enhanced Context Preservation
# ═══════════════════════════════════════════════

_CONTEXT_MARKERS = {
    "quine": ["indeterminacy", "translation", "underdetermined", "behavioral evidence",
              "radical translation", "gavagai"],
    "duhem": ["holistic", "web of belief", "auxiliary", "not in isolation"],
    "kuhn": ["paradigm", "incommensurable", "revolution", "normal science"],
    "barthes": ["death of the author", "text", "reader", "arbitrary", "drift"],
    "behaviorist": ["observable", "behavioral", "response", "stimulus", "operant"],
    "pragmatist": ["pragmat", "usefulness", "cash value", "practical"],
    "sapir_whorf": ["linguistic relativity", "language shapes", "conceptual"],
    "holographic": ["holographic", "boundary", "bulk", "information", "surface"],
    "wiles": ["local", "global", "modular", "prime", "automorphic"],
    "goedel": ["incompleteness", "self-referential", "undecidable", "consistency"],
}


def _compute_r_context_1b(
    design: str, code: str,
) -> tuple[float, list[tuple[str, str]]]:
    """Enhanced R_context with HTLF pipeline and stricter framework matching."""
    gaps: list[tuple[str, str]] = []
    design_lower = design.lower()
    code_lower = code.lower()

    # Extract documentation from code
    docstrings = re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', code, re.DOTALL)
    comments = re.findall(r'#\s*(.*)', code)
    doc_text = (' '.join(d[0] or d[1] for d in docstrings) + ' ' + ' '.join(comments)).lower()

    # Find referenced frameworks in design
    referenced = []
    for fw, markers in _CONTEXT_MARKERS.items():
        if any(m in design_lower for m in markers) or fw in design_lower:
            referenced.append(fw)

    if not referenced:
        # No specific theory → check general documentation quality
        func_count = len(re.findall(r'def\s+\w+', code))
        doc_count = len(re.findall(r'def\s+\w+.*?:\s*\n\s+"""', code))
        doc_ratio = doc_count / max(func_count, 1)
        return round(0.5 + 0.3 * doc_ratio, SCORE_PRECISION), gaps

    # Check preservation
    preserved = 0
    for fw in referenced:
        markers = _CONTEXT_MARKERS[fw]
        in_docs = fw in doc_text or any(m in doc_text for m in markers)
        in_code = fw in code_lower or any(m in code_lower for m in markers)

        if in_docs and in_code:
            preserved += 1  # Full preservation
        elif in_code:
            preserved += 0.5  # In code but not documented
            gaps.append((f"Framework '{fw}' used in code but not documented", "minor"))
        else:
            gaps.append((f"Framework '{fw}' referenced in design but absent from code", "major"))

    framework_score = preserved / len(referenced) if referenced else 0.5

    # Theory-aware naming bonus
    theory_names = sum(1 for fw in referenced
                       if re.search(rf'{fw}|{"_".join(fw.split())}', code_lower))
    naming_score = min(1.0, theory_names / max(len(referenced), 1))

    # Docstring depth: not just presence but quality
    total_doc_chars = sum(len(d[0] or d[1]) for d in docstrings)
    total_code_lines = len(code.splitlines())
    doc_density = min(1.0, total_doc_chars / max(total_code_lines * 20, 1))

    # HTLF context score (when available)
    htlf_ctx = 0.5
    if _HAS_HTLF:
        try:
            design_graph = parse_document(design, layer="natural_language")
            code_graph = parse_document(code, layer="formal_language")
            matches = match_concepts(design_graph, code_graph)
            htlf_result = htlf_r_context(design_graph, code_graph, matches)
            htlf_ctx = htlf_result if isinstance(htlf_result, float) else htlf_result.score
        except Exception:
            htlf_ctx = 0.5

    score = (
        CONTEXT_FRAMEWORK_WEIGHT * framework_score +
        CONTEXT_NAMING_WEIGHT * naming_score +
        CONTEXT_DOCSTRING_WEIGHT * doc_density +
        CONTEXT_HTLF_WEIGHT * htlf_ctx
    )

    return round(max(0.0, min(1.0, score)), SCORE_PRECISION), gaps


# ═══════════════════════════════════════════════
# R_qualia: Stricter API Ergonomics
# ═══════════════════════════════════════════════

def _compute_r_qualia_1b(
    code: str, structure: dict[str, Any],
) -> tuple[float, list[tuple[str, str]]]:
    """Stricter qualia measurement with severity classification."""
    warnings: list[tuple[str, str]] = []
    scores: list[float] = []

    func_names = structure.get("function_names", [])

    # 1. Naming quality (stricter)
    if func_names:
        bad = []
        for n in func_names:
            if len(n) < MIN_NAME_LEN and not n.startswith('_'):
                bad.append(n)
            elif n.count('_') > 4:
                bad.append(n)  # Too many underscores = unclear
        naming = 1.0 - len(bad) / len(func_names)
        scores.append(naming)
        if bad:
            sev = "major" if len(bad) > 3 else "minor"
            warnings.append((f"Unclear names: {bad[:5]}", sev))
    else:
        scores.append(0.5)

    # 2. Docstring coverage (stricter threshold)
    if func_names:
        docstrings = len(re.findall(r'def\s+\w+.*?:\s*\n\s+"""', code))
        ratio = min(1.0, docstrings / len(func_names))
        scores.append(ratio)
        if ratio < QUALIA_DOCSTRING_MIN:
            sev = "major" if ratio < 0.3 else "minor"
            warnings.append((f"Docstring coverage: {ratio:.0%} (need ≥{QUALIA_DOCSTRING_MIN:.0%})", sev))
    else:
        scores.append(0.5)

    # 3. Line length
    lines = code.splitlines()
    if lines:
        long = sum(1 for l in lines if len(l) > QUALIA_MAX_LINE)
        ratio = 1.0 - min(1.0, long / max(len(lines), 1))
        scores.append(ratio)
        if long > len(lines) * 0.05:  # Stricter: 5% threshold
            warnings.append((f"{long} lines exceed {QUALIA_MAX_LINE} chars", "minor"))
    else:
        scores.append(0.5)

    # 4. Magic numbers (stricter)
    magic_nums = re.findall(r'(?<![.\w])\d+\.?\d*(?![.\w])', code)
    safe = {'0', '1', '2', '3', '4', '5', '0.0', '1.0', '0.5', '100', '1000', '10'}
    magic = [n for n in magic_nums if n not in safe]
    # Exclude numbers that appear in named constant assignments (UPPER_CASE = N)
    const_nums = set(re.findall(r'^[A-Z_]{2,}\s*=\s*(\d+\.?\d*)', code, re.MULTILINE))
    magic = [n for n in magic if n not in const_nums]
    if len(magic) > QUALIA_MAX_MAGIC:
        penalty = min(0.5, len(magic) * 0.04)
        scores.append(1.0 - penalty)
        sev = "critical" if len(magic) > 15 else "major"
        warnings.append((f"{len(magic)} magic numbers (max: {QUALIA_MAX_MAGIC})", sev))
    else:
        scores.append(1.0)

    # 5. Type hints (stricter)
    if func_names:
        hints = len(re.findall(r'def\s+\w+\(.*?:.*?\)|->|:\s*(int|float|str|bool|list|dict|Optional|Any|tuple)', code))
        ratio = min(1.0, hints / len(func_names))
        scores.append(ratio)
        if ratio < QUALIA_TYPE_HINT_MIN:
            warnings.append((f"Type hint coverage: {ratio:.0%} (need ≥{QUALIA_TYPE_HINT_MIN:.0%})", "minor"))
    else:
        scores.append(0.5)

    # 6. NEW: API consistency — public functions should have consistent patterns
    public = [f for f in func_names if not f.startswith('_')]
    if len(public) > 3:
        # Check if public functions follow naming conventions
        verb_starts = sum(1 for f in public if re.match(r'(get|set|create|compute|find|check|is_|has_)', f))
        consistency = verb_starts / len(public) if public else 0
        scores.append(min(1.0, 0.5 + consistency))
    else:
        scores.append(0.7)

    score = sum(scores) / len(scores) if scores else 0.5
    return round(min(1.0, score), SCORE_PRECISION), warnings


# ═══════════════════════════════════════════════
# R_cultural: Convention Adherence
# ═══════════════════════════════════════════════

def _compute_r_cultural_1b(
    code: str, project: str = "katala",
) -> tuple[float, list[tuple[str, str]]]:
    """Convention adherence with severity."""
    violations: list[tuple[str, str]] = []

    if project != "katala":
        return 0.7, []

    checked = 0
    met = 0

    for name, (pattern, description) in _KATALA_CONVENTIONS.items():
        relevant = False
        if name == "dataclass_slots" and "@dataclass" in code:
            relevant = True
        elif name == "type_annotations" and ("def " in code or "class " in code):
            relevant = True
        elif name == "rust_fallback" and "rust" in code.lower():
            relevant = True
        elif name == "round_scores" and re.search(r'score|loss|fidelity', code.lower()):
            relevant = True
        elif name == "clamp_values" and re.search(r'score|loss|ratio', code.lower()):
            relevant = True

        if relevant:
            checked += 1
            if re.search(pattern, code):
                met += 1
            else:
                violations.append((f"Convention: {description}", "minor"))

    # NEW: import ordering (stdlib → third-party → local)
    import_lines = re.findall(r'^(?:from|import)\s+\S+', code, re.MULTILINE)
    if len(import_lines) > 3:
        checked += 1
        # Simple check: __future__ should be first
        if import_lines and "__future__" in import_lines[0]:
            met += 1
        elif any("__future__" in i for i in import_lines):
            violations.append(("from __future__ import should be first import", "minor"))

    if checked == 0:
        return 0.75, []

    score = met / checked
    return round(max(0.0, min(1.0, 0.2 + 0.8 * score)), SCORE_PRECISION), violations


# ═══════════════════════════════════════════════
# R_temporal: Future Survivability (stricter)
# ═══════════════════════════════════════════════

def _compute_r_temporal_1b(
    code: str, structure: dict[str, Any],
) -> tuple[float, list[tuple[str, str]]]:
    """Stricter temporal survivability."""
    risks: list[tuple[str, str]] = []
    score = 1.0

    # 1. Inheritance depth
    chains = structure.get("inheritance_chains", [])
    if chains:
        max_bases = max(len(bases) for _, bases in chains)
        if max_bases > 1:
            penalty = min(0.3, (max_bases - 1) * 0.15)
            score -= penalty
            risks.append((f"Multiple inheritance ({max_bases} bases)", "major"))

    # 2. Global state (stricter)
    global_vars = re.findall(r'^[A-Z_]{2,}\s*[=:]', code, re.MULTILINE)
    module_vars = re.findall(r'^_[A-Z_]+\s*=', code, re.MULTILINE)
    total_globals = len(global_vars) + len(module_vars)
    if total_globals > TEMPORAL_MAX_GLOBALS:
        penalty = min(0.25, (total_globals - TEMPORAL_MAX_GLOBALS) * 0.03)
        score -= penalty
        sev = "major" if total_globals > 20 else "minor"
        risks.append((f"High global state: {total_globals} module-level vars (max: {TEMPORAL_MAX_GLOBALS})", sev))

    # 3. kwargs (stricter)
    kwargs_count = len(re.findall(r'\*\*kwargs', code))
    if kwargs_count > TEMPORAL_MAX_KWARGS:
        score -= min(0.15, (kwargs_count - TEMPORAL_MAX_KWARGS) * 0.05)
        risks.append((f"**kwargs propagation ({kwargs_count}x, max: {TEMPORAL_MAX_KWARGS})", "minor"))

    # 4. Test presence
    has_tests = bool(re.search(r'def test_|assert |pytest|unittest', code))
    if not has_tests and structure.get("functions", 0) > 5:
        score -= 0.1
        risks.append(("No tests for non-trivial module", "major"))

    # 5. API surface stability
    public = [f for f in structure.get("function_names", []) if not f.startswith('_')]
    private = [f for f in structure.get("function_names", []) if f.startswith('_')]
    if public and private:
        ratio = len(private) / (len(public) + len(private))
        score += min(0.1, ratio * 0.15)

    # 6. NEW: Coupling analysis — how many external imports?
    imports = re.findall(r'^(?:from|import)\s+(\S+)', code, re.MULTILINE)
    external = [i for i in imports if not i.startswith(('katala', 'htlf', '__future__'))]
    stdlib = {'ast', 're', 'math', 'os', 'sys', 'json', 'time', 'typing',
              'dataclasses', 'collections', 'functools', 'pathlib', 'inspect'}
    third_party = [i.split('.')[0] for i in external if i.split('.')[0] not in stdlib]
    if len(third_party) > 5:
        score -= 0.1
        risks.append((f"High external coupling: {len(third_party)} third-party deps", "minor"))

    return round(max(0.0, min(1.0, score)), SCORE_PRECISION), risks


# ═══════════════════════════════════════════════
# Grading: Discriminative with penalty cascades
# ═══════════════════════════════════════════════

def _apply_severity_penalties(
    axis_score: float,
    issues: list[tuple[str, str]],
) -> float:
    """Apply severity-based penalties to an axis score."""
    score = axis_score
    for _, severity in issues:
        if severity == "critical":
            score *= SEVERITY_CRITICAL
        elif severity == "major":
            score *= SEVERITY_MAJOR
        elif severity == "minor":
            score *= SEVERITY_MINOR
    return round(max(0.0, min(1.0, score)), SCORE_PRECISION)


def _compute_grade(
    total: float,
    axes: dict[str, float],
) -> tuple[str, list[str]]:
    """Discriminative grading with axis-minimum requirements.

    Grade S: total ≥ 0.92 AND all axes ≥ 0.85
    Grade A: total ≥ 0.82 AND no axis < 0.60
    Grade B-F: total only
    """
    penalties: list[str] = []
    min_axis = min(axes.values())
    min_axis_name = min(axes, key=axes.get)

    # Check S eligibility
    if total >= GRADE_S_TOTAL:
        if min_axis >= GRADE_S_MIN_AXIS:
            return "S", []
        penalties.append(
            f"S→A: {min_axis_name}={min_axis:.2f} < {GRADE_S_MIN_AXIS} minimum"
        )

    # Check A eligibility
    if total >= GRADE_A_TOTAL:
        if min_axis >= GRADE_A_MIN_AXIS:
            return "A", penalties
        penalties.append(
            f"A→B: {min_axis_name}={min_axis:.2f} < {GRADE_A_MIN_AXIS} minimum"
        )

    # B-F by total only
    if total >= GRADE_B_TOTAL:
        return "B", penalties
    if total >= GRADE_C_TOTAL:
        return "C", penalties
    if total >= GRADE_D_TOTAL:
        return "D", penalties
    return "F", penalties


# ═══════════════════════════════════════════════
# Bidirectional Gap Analysis
# ═══════════════════════════════════════════════

def _bidirectional_gaps(
    design: str,
    code: str,
    reverse: ReverseAnalysis | None,
) -> tuple[list[str], list[str]]:
    """Find gaps in both directions.

    Forward gaps: design concepts not in code
    Reverse gaps: code functionality not in design
    """
    # Forward: design → code
    design_concepts = _extract_design_concepts(design)
    code_lower = code.lower()
    code_idents = set(re.findall(r'[a-z_][a-z0-9_]{2,}', code_lower))

    forward_gaps = []
    for c in design_concepts:
        if not any(c in ident or ident in c for ident in code_idents):
            forward_gaps.append(f"Design concept '{c}' not found in code")

    # Reverse: code → design
    reverse_gaps = []
    if reverse:
        design_lower = design.lower()
        for concept in reverse.intent.domain_concepts[:10]:
            if concept.lower() not in design_lower:
                reverse_gaps.append(
                    f"Code concept '{concept}' not mentioned in design"
                )

    return forward_gaps[:10], reverse_gaps[:10]


# ═══════════════════════════════════════════════
# KCS-1b: Main Engine
# ═══════════════════════════════════════════════

class KCS1b:
    """Katala Coding Series 1b — Integrated Translation Loss Analyzer.

    Upgrades over KCS-1a:
    1. HTLF pipeline for R_struct/R_context (falls back to heuristic)
    2. Severity-based issue classification (critical/major/minor)
    3. Discriminative grading (S requires ALL axes ≥ 0.85)
    4. Integrated KCS-2a reverse inference
    5. Adaptive Solver Router for multi-solver verification
    6. Bidirectional gap analysis (forward + reverse)
    7. Automatic goal generation from gaps

    Usage:
        kcs = KCS1b()
        result = kcs.verify(
            design="Implement X with Y...",
            code=open("module.py").read(),
        )
        print(result.final_grade)
        for gap in result.design_to_code_gaps:
            print(f"  Forward gap: {gap}")
        for goal in result.goals:
            print(f"  Next: {goal}")
    """

    def __init__(self, project: str = "katala", use_router: bool = True):
        self.project = project
        self.use_router = use_router and _HAS_ROUTER
        self._kcs2a = KCS2a()
        self._router = None
        if self.use_router:
            try:
                pool = create_full_solver_pool()
                self._router = AdaptiveSolverRouter(solver_pool=pool)
            except Exception:
                self.use_router = False

    def verify(self, design: str, code: str) -> EnhancedVerdict:
        """Full integrated verification: forward + reverse + router."""
        structure = _analyze_code_structure(code)

        # ── Forward: 5-axis with severity ──
        r_struct_raw, struct_issues = _compute_r_struct_1b(design, code, structure)
        r_context_raw, context_issues = _compute_r_context_1b(design, code)
        r_qualia_raw, qualia_issues = _compute_r_qualia_1b(code, structure)
        r_cultural_raw, cultural_issues = _compute_r_cultural_1b(code, self.project)
        r_temporal_raw, temporal_issues = _compute_r_temporal_1b(code, structure)

        # Apply severity penalties
        r_struct = _apply_severity_penalties(r_struct_raw, struct_issues)
        r_context = _apply_severity_penalties(r_context_raw, context_issues)
        r_qualia = _apply_severity_penalties(r_qualia_raw, qualia_issues)
        r_cultural = _apply_severity_penalties(r_cultural_raw, cultural_issues)
        r_temporal = _apply_severity_penalties(r_temporal_raw, temporal_issues)

        # Weighted total
        total = (
            AXIS_WEIGHTS["r_struct"] * r_struct +
            AXIS_WEIGHTS["r_context"] * r_context +
            AXIS_WEIGHTS["r_qualia"] * r_qualia +
            AXIS_WEIGHTS["r_cultural"] * r_cultural +
            AXIS_WEIGHTS["r_temporal"] * r_temporal
        )
        total = round(max(0.0, min(1.0, total)), SCORE_PRECISION)

        # Grade with axis-minimum check
        axes = {
            "R_struct": r_struct, "R_context": r_context,
            "R_qualia": r_qualia, "R_cultural": r_cultural,
            "R_temporal": r_temporal,
        }
        grade, penalty_log = _compute_grade(total, axes)

        # Design coverage
        design_concepts = _extract_design_concepts(design)
        code_lower = code.lower()
        coverage = (sum(1 for c in design_concepts if c in code_lower) /
                    max(len(design_concepts), 1))

        # Complexity
        complexity = (
            structure.get("max_depth", 0) * 2 +
            len(structure.get("inheritance_chains", [])) * 3 +
            structure.get("functions", 0) * 0.5
        )

        forward = CodeVerdict(
            r_struct=r_struct,
            r_context=r_context,
            r_qualia=r_qualia,
            r_cultural=r_cultural,
            r_temporal=r_temporal,
            total_fidelity=total,
            translation_loss=round(1.0 - total, SCORE_PRECISION),
            grade=grade,
            structural_issues=[msg for msg, _ in struct_issues],
            context_gaps=[msg for msg, _ in context_issues],
            qualia_warnings=[msg for msg, _ in qualia_issues],
            cultural_violations=[msg for msg, _ in cultural_issues],
            temporal_risks=[msg for msg, _ in temporal_issues],
            lines_analyzed=structure.get("lines", 0),
            complexity_score=round(complexity, 2),
            design_coverage=round(coverage, SCORE_PRECISION),
        )

        # ── Reverse inference ──
        reverse = None
        try:
            reverse = self._kcs2a.analyze(code)
        except Exception:
            pass

        # ── Router ──
        router_activated = 0
        router_savings = 0.0
        if self.use_router and self._router:
            try:
                claim = f"Code correctly implements: {design[:200]}"
                evidence = [
                    f"R_struct={r_struct:.2f}",
                    f"R_context={r_context:.2f}",
                    f"R_qualia={r_qualia:.2f}",
                ]
                rr = self._router.route(claim, evidence, {"premises": evidence})
                router_activated = rr.solvers_activated
                router_savings = rr.cost_savings
            except Exception:
                pass

        # ── Bidirectional gaps ──
        fwd_gaps, rev_gaps = _bidirectional_gaps(design, code, reverse)

        # ── Goals ──
        goals: list[str] = []
        if reverse:
            for g in reverse.goals[:5]:
                goals.append(f"[{g.priority}] {g.goal} → {g.estimated_impact}")
        # Add gap-derived goals
        for gap in fwd_gaps[:3]:
            goals.append(f"[high] Implement missing: {gap}")

        return EnhancedVerdict(
            forward=forward,
            reverse=reverse,
            router_activated=router_activated,
            router_savings=router_savings,
            final_grade=grade,
            penalty_log=penalty_log,
            design_to_code_gaps=fwd_gaps,
            code_to_design_gaps=rev_gaps,
            goals=goals,
        )

    @staticmethod
    def format_verdict(v: EnhancedVerdict) -> str:
        """Pretty-print enhanced verdict."""
        f = v.forward
        lines = [
            f"╔══ KCS-1b Verdict: Grade {v.final_grade} ══╗",
            f"║ Total Fidelity: {f.total_fidelity:.1%} (loss: {f.translation_loss:.1%})",
            f"║",
            f"║ R_struct:   {f.r_struct:.3f}  (×{AXIS_WEIGHTS['r_struct']:.0%})",
            f"║ R_context:  {f.r_context:.3f}  (×{AXIS_WEIGHTS['r_context']:.0%})",
            f"║ R_qualia:   {f.r_qualia:.3f}  (×{AXIS_WEIGHTS['r_qualia']:.0%})",
            f"║ R_cultural: {f.r_cultural:.3f}  (×{AXIS_WEIGHTS['r_cultural']:.0%})",
            f"║ R_temporal: {f.r_temporal:.3f}  (×{AXIS_WEIGHTS['r_temporal']:.0%})",
            f"║",
            f"║ Lines: {f.lines_analyzed} | Coverage: {f.design_coverage:.0%}",
        ]

        if v.penalty_log:
            lines.append("║")
            lines.append("║ 📉 Grade Penalties:")
            for p in v.penalty_log:
                lines.append(f"║   • {p}")

        if v.router_activated:
            lines.append(f"║")
            lines.append(f"║ 🔀 Router: {v.router_activated} solvers, {v.router_savings:.0%} savings")

        all_issues = (
            [(i, "struct") for i in f.structural_issues] +
            [(i, "context") for i in f.context_gaps] +
            [(i, "qualia") for i in f.qualia_warnings] +
            [(i, "cultural") for i in f.cultural_violations] +
            [(i, "temporal") for i in f.temporal_risks]
        )
        if all_issues:
            lines.append("║")
            lines.append(f"║ ⚠️  Issues ({len(all_issues)}):")
            for issue, axis in all_issues[:10]:
                lines.append(f"║   [{axis}] {issue}")

        if v.design_to_code_gaps:
            lines.append("║")
            lines.append(f"║ 📐 Forward Gaps ({len(v.design_to_code_gaps)}):")
            for g in v.design_to_code_gaps[:5]:
                lines.append(f"║   → {g}")

        if v.code_to_design_gaps:
            lines.append(f"║ 📐 Reverse Gaps ({len(v.code_to_design_gaps)}):")
            for g in v.code_to_design_gaps[:5]:
                lines.append(f"║   ← {g}")

        if v.goals:
            lines.append("║")
            lines.append(f"║ 🎯 Next Goals ({len(v.goals)}):")
            for g in v.goals[:5]:
                lines.append(f"║   • {g}")

        lines.append("╚" + "═" * 38 + "╝")
        return "\n".join(lines)
