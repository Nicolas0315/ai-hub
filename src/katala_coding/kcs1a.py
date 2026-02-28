"""KCS-1a: Katala Coding Series — Design-to-Code Translation Loss Analyzer.

Self-referential application of KS40c's 5-axis HTLF model to code generation.
Measures how much "meaning" is lost when translating:
  Design Intent (natural language) → Implementation (code)

5-Axis Code Translation Model:
  R_struct:   Does the code structure mirror the design structure?
  R_context:  Is the philosophical/theoretical context preserved in the code?
  R_qualia:   Does the code "feel right" to the designer? (API ergonomics, naming)
  R_cultural: Are team-specific conventions and shared mental models preserved?
  R_temporal: Will this code survive future evolution without structural decay?

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
Date: 2026-03-01
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field, asdict
from typing import Any

# ── Named Constants (extracted from magic numbers) ──
MAX_RECOMMENDED_NESTING = 4
MIN_FUNCTION_NAME_LENGTH = 3
LOW_CONCEPT_COVERAGE_THRESHOLD = 0.3
OVERENGINEERING_RATIO = 3.0
LOW_DOCSTRING_THRESHOLD = 0.5
MAX_LINE_LENGTH = 100
MAGIC_NUMBER_WARN_THRESHOLD = 5
LOW_TYPE_HINT_THRESHOLD = 0.3
HIGH_GLOBAL_STATE_THRESHOLD = 10
HEAVY_KWARGS_THRESHOLD = 3
HARDCODED_STRING_WARN_THRESHOLD = 5
MIN_FUNC_COUNT_FOR_TEST_CHECK = 5
SCORE_DECIMAL_PLACES = 4


@dataclass(slots=True)
class CodeVerdict:
    """KCS verification result."""
    # 5-axis scores (0=total loss, 1=perfect preservation)
    r_struct: float
    r_context: float
    r_qualia: float
    r_cultural: float
    r_temporal: float

    # Aggregate
    total_fidelity: float       # Weighted average of 5 axes
    translation_loss: float     # 1 - total_fidelity
    grade: str                  # S/A/B/C/D/F

    # Diagnostics
    structural_issues: list[str]
    context_gaps: list[str]
    qualia_warnings: list[str]
    cultural_violations: list[str]
    temporal_risks: list[str]

    # Meta
    lines_analyzed: int
    complexity_score: float
    design_coverage: float      # % of design concepts found in code


# ════════════════════════════════════════════
# R_struct: Design → Code Structure Preservation
# ════════════════════════════════════════════

def _analyze_code_structure(code: str) -> dict[str, Any]:
    """Parse code and extract structural features."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"parseable": False, "classes": 0, "functions": 0, "max_depth": 0,
                "inheritance_depth": 0, "lines": len(code.splitlines())}

    classes = []
    functions = []
    max_depth = 0
    inheritance_chains = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
            bases = [getattr(b, 'id', getattr(b, 'attr', '?')) for b in node.bases]
            if bases:
                inheritance_chains.append((node.name, bases))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(node.name)
            # Measure nesting depth
            depth = _nesting_depth(node)
            max_depth = max(max_depth, depth)

    return {
        "parseable": True,
        "classes": len(classes),
        "class_names": classes,
        "functions": len(functions),
        "function_names": functions,
        "max_depth": max_depth,
        "inheritance_chains": inheritance_chains,
        "lines": len(code.splitlines()),
    }


def _nesting_depth(node: ast.AST, current: int = 0) -> int:
    """Calculate maximum nesting depth of a function."""
    max_d = current
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.If | ast.For | ast.While | ast.With | ast.Try):
            max_d = max(max_d, _nesting_depth(child, current + 1))
        else:
            max_d = max(max_d, _nesting_depth(child, current))
    return max_d


def _extract_design_concepts(design_text: str) -> list[str]:
    """Extract key concepts from design intent text."""
    # Remove common filler words
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                 "have", "has", "had", "do", "does", "did", "will", "would",
                 "could", "should", "may", "might", "can", "shall", "must",
                 "to", "of", "in", "for", "on", "with", "at", "by", "from",
                 "this", "that", "these", "those", "it", "its", "and", "or",
                 "but", "not", "no", "if", "then", "else", "when", "where",
                 "what", "which", "who", "how", "all", "each", "every",
                 "も", "の", "は", "が", "を", "に", "で", "と", "する", "ある"}

    # Extract noun phrases and key terms
    words = re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}|[一-龯ぁ-んァ-ヴー]{2,}', design_text)
    concepts = [w.lower() for w in words if w.lower() not in stopwords]
    return list(dict.fromkeys(concepts))  # Deduplicate preserving order


def _compute_r_struct(design_text: str, code: str, structure: dict) -> tuple[float, list[str]]:
    """Measure structural preservation from design to code."""
    issues = []

    if not structure["parseable"]:
        return 0.1, ["Code has syntax errors — cannot parse"]

    # 1. Design concept → Code entity mapping
    design_concepts = _extract_design_concepts(design_text)
    code_entities = set()
    for name in structure.get("class_names", []):
        code_entities.add(name.lower())
        # Also add snake_case parts
        parts = re.findall(r'[A-Z][a-z]+|[a-z]+', name)
        code_entities.update(p.lower() for p in parts)
    for name in structure.get("function_names", []):
        code_entities.update(name.lower().split('_'))

    # Also scan for identifiers in code
    code_idents = set(re.findall(r'[a-z_][a-z0-9_]{2,}', code.lower()))
    code_entities.update(code_idents)

    if design_concepts:
        matched = sum(1 for c in design_concepts
                      if any(c in e or e in c for e in code_entities))
        concept_coverage = matched / len(design_concepts)
    else:
        concept_coverage = 0.5

    if concept_coverage < LOW_CONCEPT_COVERAGE_THRESHOLD:
        issues.append(f"Low design coverage: {concept_coverage:.0%} of concepts found in code")

    # 2. Complexity penalty
    depth_penalty = 0.0
    if structure["max_depth"] > MAX_RECOMMENDED_NESTING:
        depth_penalty = min(0.3, (structure["max_depth"] - MAX_RECOMMENDED_NESTING) * 0.1)
        issues.append(f"Deep nesting: {structure['max_depth']} levels (recommended ≤4)")

    # 3. Inheritance chain penalty (Composition > Inheritance)
    chain_penalty = 0.0
    for cls, bases in structure.get("inheritance_chains", []):
        if len(bases) > 2:
            chain_penalty += 0.1
            issues.append(f"Multiple inheritance: {cls}({', '.join(bases)})")

    # 4. Function count vs design complexity
    design_complexity = len(design_concepts)
    code_complexity = structure["functions"] + structure["classes"]
    if design_complexity > 0 and code_complexity > design_complexity * 3:
        over = code_complexity / design_complexity
        issues.append(f"Over-engineering: {code_complexity} code entities for {design_complexity} design concepts ({over:.1f}x)")
        chain_penalty += min(0.15, (over - 3) * 0.05)

    score = max(0.0, min(1.0,
        0.50 * concept_coverage +
        0.25 * (1.0 - depth_penalty) +
        0.25 * (1.0 - chain_penalty)
    ))

    return round(score, 4), issues


# ════════════════════════════════════════════
# R_context: Theoretical Context Preservation
# ════════════════════════════════════════════

# Philosophical/theoretical markers that should appear in docstrings/comments
_CONTEXT_MARKERS = {
    "quine": ["indeterminacy", "translation", "underdetermined", "behavioral evidence"],
    "duhem": ["holistic", "web of belief", "auxiliary", "not in isolation"],
    "kuhn": ["paradigm", "incommensurable", "revolution", "normal science"],
    "barthes": ["death of the author", "text", "reader", "arbitrary", "drift"],
    "behaviorist": ["observable", "behavioral", "response", "stimulus"],
    "pragmatist": ["pragmat", "usefulness", "cash value", "practical"],
    "sapir_whorf": ["linguistic relativity", "language shapes", "conceptual framework"],
    "holographic": ["holographic", "boundary", "bulk", "information", "surface"],
}


def _compute_r_context(design_text: str, code: str) -> tuple[float, list[str]]:
    """Measure how much theoretical context survives into code."""
    gaps = []
    design_lower = design_text.lower()
    code_lower = code.lower()

    # Extract comments and docstrings from code
    docstrings = re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', code, re.DOTALL)
    comments = re.findall(r'#\s*(.*)', code)
    doc_text = ' '.join(d[0] or d[1] for d in docstrings) + ' ' + ' '.join(comments)
    doc_text_lower = doc_text.lower()

    # Check which theoretical frameworks are referenced in design
    referenced_frameworks = []
    for framework, markers in _CONTEXT_MARKERS.items():
        if any(m in design_lower for m in markers) or framework in design_lower:
            referenced_frameworks.append(framework)

    if not referenced_frameworks:
        return 0.8, []  # No specific theoretical context to preserve

    # Check how many are preserved in code documentation
    preserved = 0
    for fw in referenced_frameworks:
        markers = _CONTEXT_MARKERS[fw]
        if fw in doc_text_lower or any(m in doc_text_lower for m in markers):
            preserved += 1
        else:
            gaps.append(f"Theoretical context lost: '{fw}' referenced in design but absent from code docs")

    preservation_ratio = preserved / len(referenced_frameworks)

    # Bonus: meaningful variable/function names that reflect theory
    theory_names = sum(1 for fw in referenced_frameworks
                       if re.search(rf'{fw}|{"_".join(fw.split())}', code_lower))
    naming_bonus = min(0.15, theory_names * 0.05)

    score = min(1.0, 0.7 * preservation_ratio + 0.15 * (1.0 if doc_text.strip() else 0.0) + naming_bonus + 0.15)

    return round(score, 4), gaps


# ════════════════════════════════════════════
# R_qualia: API Ergonomics & Developer Experience
# ════════════════════════════════════════════

def _compute_r_qualia(code: str, structure: dict) -> tuple[float, list[str]]:
    """Measure code 'feel' — naming quality, API clarity, readability."""
    warnings = []
    score_components = []

    # 1. Naming quality
    func_names = structure.get("function_names", [])
    bad_names = [n for n in func_names if len(n) < MIN_FUNCTION_NAME_LENGTH or n.startswith('_') and n.count('_') > 2]
    if func_names:
        naming_ratio = 1.0 - len(bad_names) / len(func_names)
        score_components.append(naming_ratio)
        if bad_names:
            warnings.append(f"Unclear function names: {bad_names[:3]}")
    else:
        score_components.append(0.5)

    # 2. Docstring coverage
    func_count = len(func_names)
    if func_count > 0:
        docstring_pattern = r'def\s+\w+.*?:\s*\n\s+"""'
        docstrings_found = len(re.findall(docstring_pattern, code))
        doc_ratio = min(1.0, docstrings_found / func_count)
        score_components.append(doc_ratio)
        if doc_ratio < LOW_DOCSTRING_THRESHOLD:
            warnings.append(f"Low docstring coverage: {doc_ratio:.0%}")
    else:
        score_components.append(0.5)

    # 3. Line length (readability)
    lines = code.splitlines()
    long_lines = sum(1 for l in lines if len(l) > MAX_LINE_LENGTH)
    if lines:
        length_ratio = 1.0 - min(1.0, long_lines / max(1, len(lines)))
        score_components.append(length_ratio)
        if long_lines > len(lines) * 0.1:
            warnings.append(f"{long_lines} lines exceed 100 chars")
    else:
        score_components.append(0.5)

    # 4. Magic number check
    magic_numbers = re.findall(r'(?<![.\w])\d+\.?\d*(?![.\w])', code)
    # Filter out common safe numbers (0, 1, 2, 100, etc.)
    safe = {'0', '1', '2', '0.0', '1.0', '0.5', '100', '1000', '10'}
    magic = [n for n in magic_numbers if n not in safe]
    if len(magic) > MAGIC_NUMBER_WARN_THRESHOLD:
        warnings.append(f"Many magic numbers: consider named constants ({len(magic)} found)")
        score_components.append(max(0.3, 1.0 - len(magic) * 0.03))
    else:
        score_components.append(1.0)

    # 5. Type hint presence
    type_hint_pattern = r'def\s+\w+\(.*?:.*?\)|->|:\s*(int|float|str|bool|list|dict|Optional|Any|tuple)'
    type_hints = len(re.findall(type_hint_pattern, code))
    if func_count > 0:
        hint_ratio = min(1.0, type_hints / func_count)
        score_components.append(hint_ratio)
        if hint_ratio < LOW_TYPE_HINT_THRESHOLD:
            warnings.append("Low type hint coverage")
    else:
        score_components.append(0.5)

    score = sum(score_components) / len(score_components) if score_components else 0.5
    return round(min(1.0, score), 4), warnings


# ════════════════════════════════════════════
# R_cultural: Team Convention Preservation
# ════════════════════════════════════════════

# Katala project conventions
_KATALA_CONVENTIONS = {
    "dataclass_slots": (r"@dataclass\(slots=True\)", "Use @dataclass(slots=True) for performance"),
    "type_annotations": (r"from __future__ import annotations", "Use future annotations for forward refs"),
    "rust_fallback": (r"if.*_has\(|RUST_AVAILABLE|Python fallback", "Rust functions must have Python fallback"),
    "round_scores": (r"round\(.*,\s*4\)", "Round scores to 4 decimal places"),
    "clamp_values": (r"min\(1\.0|max\(0\.0|clamp", "Clamp values to [0, 1]"),
}


def _compute_r_cultural(code: str, project: str = "katala") -> tuple[float, list[str]]:
    """Measure adherence to team/project conventions."""
    violations = []

    if project != "katala":
        return 0.7, []  # No conventions defined for other projects

    conventions_checked = 0
    conventions_met = 0

    for name, (pattern, description) in _KATALA_CONVENTIONS.items():
        # Only check if the convention is relevant to this code
        if name == "dataclass_slots" and "@dataclass" in code:
            conventions_checked += 1
            if re.search(pattern, code):
                conventions_met += 1
            else:
                violations.append(f"Convention: {description}")

        elif name == "type_annotations" and ("def " in code or "class " in code):
            conventions_checked += 1
            if re.search(pattern, code):
                conventions_met += 1
            # Don't warn — not all files need it

        elif name == "rust_fallback" and "rust" in code.lower():
            conventions_checked += 1
            if re.search(pattern, code):
                conventions_met += 1
            else:
                violations.append(f"Convention: {description}")

        elif name == "round_scores" and re.search(r'score|loss|fidelity', code.lower()):
            conventions_checked += 1
            if re.search(pattern, code):
                conventions_met += 1

        elif name == "clamp_values" and re.search(r'score|loss|ratio', code.lower()):
            conventions_checked += 1
            if re.search(pattern, code):
                conventions_met += 1

    if conventions_checked == 0:
        return 0.8, []

    score = conventions_met / conventions_checked
    return round(min(1.0, 0.3 + 0.7 * score), 4), violations


# ════════════════════════════════════════════
# R_temporal: Future Survivability
# ════════════════════════════════════════════

def _compute_r_temporal(code: str, structure: dict) -> tuple[float, list[str]]:
    """Predict code's survivability under future evolution."""
    risks = []
    score = 1.0

    # 1. Deep inheritance = fragile under change
    chains = structure.get("inheritance_chains", [])
    if chains:
        max_bases = max(len(bases) for _, bases in chains)
        if max_bases > 1:
            penalty = min(0.3, (max_bases - 1) * 0.15)
            score -= penalty
            risks.append(f"Multiple inheritance ({max_bases} bases) — fragile under evolution")

    # 2. Global state = hard to refactor
    global_vars = re.findall(r'^[A-Z_]{2,}\s*[=:]', code, re.MULTILINE)
    module_vars = re.findall(r'^_[A-Z_]+\s*=', code, re.MULTILINE)
    if len(global_vars) + len(module_vars) > HIGH_GLOBAL_STATE_THRESHOLD:
        penalty = min(0.2, (len(global_vars) + len(module_vars) - 10) * 0.02)
        score -= penalty
        risks.append(f"High global state: {len(global_vars) + len(module_vars)} module-level variables")

    # 3. Hardcoded values = brittle
    hardcoded = re.findall(r'(?:==|!=|>=|<=|>|<)\s*["\'][^"\']{5,}["\']', code)
    if len(hardcoded) > HARDCODED_STRING_WARN_THRESHOLD:
        score -= 0.1
        risks.append(f"Hardcoded string comparisons: {len(hardcoded)}")

    # 4. kwargs propagation = version coupling
    kwargs_pass = len(re.findall(r'\*\*kwargs', code))
    if kwargs_pass > HEAVY_KWARGS_THRESHOLD:
        score -= min(0.15, kwargs_pass * 0.03)
        risks.append(f"Heavy **kwargs propagation ({kwargs_pass}x) — tight version coupling")

    # 5. Test presence heuristic
    has_tests = bool(re.search(r'def test_|assert |pytest|unittest', code))
    if not has_tests and structure.get("functions", 0) > MIN_FUNC_COUNT_FOR_TEST_CHECK:
        score -= 0.1
        risks.append("No test functions detected for non-trivial module")

    # 6. Abstraction stability
    public_funcs = [f for f in structure.get("function_names", [])
                    if not f.startswith('_')]
    private_funcs = [f for f in structure.get("function_names", [])
                     if f.startswith('_')]
    if public_funcs and private_funcs:
        # High public/private ratio = stable API
        api_stability = len(private_funcs) / (len(public_funcs) + len(private_funcs))
        score += min(0.1, api_stability * 0.15)
    
    return round(max(0.0, min(1.0, score)), 4), risks


# ════════════════════════════════════════════
# KCS-1a: Main Engine
# ════════════════════════════════════════════

_GRADE_THRESHOLDS = [
    (0.90, "S"),
    (0.80, "A"),
    (0.65, "B"),
    (0.50, "C"),
    (0.35, "D"),
    (0.00, "F"),
]

_AXIS_WEIGHTS = {
    "r_struct": 0.30,
    "r_context": 0.20,
    "r_qualia": 0.20,
    "r_cultural": 0.15,
    "r_temporal": 0.15,
}


class KCS1a:
    """Katala Coding Series 1a — Design-to-Code Translation Loss Analyzer.
    
    Self-referential application of KS40c's HTLF 5-axis model.
    Measures translation fidelity from design intent to implementation.
    
    Usage:
        kcs = KCS1a()
        verdict = kcs.verify(
            design="Implement Quinean indeterminacy as dual output...",
            code=open("cultural_loss.py").read(),
        )
        print(verdict.grade, verdict.total_fidelity)
        for issue in verdict.structural_issues:
            print(f"  ⚠️ {issue}")
    """

    def __init__(self, project: str = "katala"):
        self.project = project

    def verify(self, design: str, code: str) -> CodeVerdict:
        """Run 5-axis verification on design→code translation."""
        structure = _analyze_code_structure(code)

        r_struct, struct_issues = _compute_r_struct(design, code, structure)
        r_context, context_gaps = _compute_r_context(design, code)
        r_qualia, qualia_warnings = _compute_r_qualia(code, structure)
        r_cultural, cultural_violations = _compute_r_cultural(code, self.project)
        r_temporal, temporal_risks = _compute_r_temporal(code, structure)

        # Weighted fidelity
        total = (
            _AXIS_WEIGHTS["r_struct"] * r_struct +
            _AXIS_WEIGHTS["r_context"] * r_context +
            _AXIS_WEIGHTS["r_qualia"] * r_qualia +
            _AXIS_WEIGHTS["r_cultural"] * r_cultural +
            _AXIS_WEIGHTS["r_temporal"] * r_temporal
        )
        total = round(max(0.0, min(1.0, total)), 4)

        # Grade
        grade = "F"
        for threshold, g in _GRADE_THRESHOLDS:
            if total >= threshold:
                grade = g
                break

        # Design coverage
        design_concepts = _extract_design_concepts(design)
        code_lower = code.lower()
        if design_concepts:
            coverage = sum(1 for c in design_concepts if c in code_lower) / len(design_concepts)
        else:
            coverage = 0.5

        # Complexity
        complexity = (
            structure.get("max_depth", 0) * 2 +
            len(structure.get("inheritance_chains", [])) * 3 +
            structure.get("functions", 0) * 0.5
        )

        return CodeVerdict(
            r_struct=r_struct,
            r_context=r_context,
            r_qualia=r_qualia,
            r_cultural=r_cultural,
            r_temporal=r_temporal,
            total_fidelity=total,
            translation_loss=round(1.0 - total, 4),
            grade=grade,
            structural_issues=struct_issues,
            context_gaps=context_gaps,
            qualia_warnings=qualia_warnings,
            cultural_violations=cultural_violations,
            temporal_risks=temporal_risks,
            lines_analyzed=structure.get("lines", 0),
            complexity_score=round(complexity, 2),
            design_coverage=round(coverage, 4),
        )

    def verify_file(self, design: str, file_path: str) -> CodeVerdict:
        """Verify a file against design intent."""
        with open(file_path, encoding="utf-8") as f:
            code = f.read()
        return self.verify(design, code)

    def verify_batch(self, pairs: list[tuple[str, str]]) -> list[CodeVerdict]:
        """Verify multiple (design, code) pairs."""
        return [self.verify(d, c) for d, c in pairs]

    def self_verify(self) -> CodeVerdict:
        """KCS verifies its own source code. Katala's self-referential moment."""
        import inspect
        my_source = inspect.getsource(type(self))
        # Include the whole module
        import katala_coding.kcs1a as this_module
        full_source = inspect.getsource(this_module)

        design = (
            "Implement a 5-axis code quality analyzer that applies HTLF's "
            "translation loss model (R_struct, R_context, R_qualia, R_cultural, "
            "R_temporal) to the design-to-code translation process. "
            "Use Quine's indeterminacy for context measurement, Kuhn's paradigm "
            "theory for temporal survivability, pragmatist approach for qualia "
            "(observable API ergonomics, not introspection). "
            "Follow Katala conventions: dataclass with slots, type annotations, "
            "round scores to 4 decimals, clamp values to [0,1]. "
            "Include docstrings, type hints, and separation of public/private API."
        )
        return self.verify(design, full_source)

    @staticmethod
    def format_verdict(v: CodeVerdict) -> str:
        """Pretty-print a verdict."""
        lines = [
            f"╔══ KCS-1a Verdict: Grade {v.grade} ══╗",
            f"║ Total Fidelity: {v.total_fidelity:.1%} (loss: {v.translation_loss:.1%})",
            f"║",
            f"║ R_struct:   {v.r_struct:.3f}  (design→code structure)",
            f"║ R_context:  {v.r_context:.3f}  (theoretical context)",
            f"║ R_qualia:   {v.r_qualia:.3f}  (API ergonomics)",
            f"║ R_cultural: {v.r_cultural:.3f}  (team conventions)",
            f"║ R_temporal: {v.r_temporal:.3f}  (future survivability)",
            f"║",
            f"║ Lines: {v.lines_analyzed} | Complexity: {v.complexity_score} | Coverage: {v.design_coverage:.0%}",
        ]
        if v.structural_issues:
            lines.append("║")
            lines.append("║ ⚠️  Structural Issues:")
            for i in v.structural_issues:
                lines.append(f"║   • {i}")
        if v.context_gaps:
            lines.append("║ 📚 Context Gaps:")
            for g in v.context_gaps:
                lines.append(f"║   • {g}")
        if v.qualia_warnings:
            lines.append("║ 🎨 Qualia Warnings:")
            for w in v.qualia_warnings:
                lines.append(f"║   • {w}")
        if v.cultural_violations:
            lines.append("║ 🏛️  Convention Violations:")
            for c in v.cultural_violations:
                lines.append(f"║   • {c}")
        if v.temporal_risks:
            lines.append("║ ⏳ Temporal Risks:")
            for t in v.temporal_risks:
                lines.append(f"║   • {t}")
        lines.append("╚" + "═" * 38 + "╝")
        return "\n".join(lines)
