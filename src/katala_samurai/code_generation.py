"""
Code Generation Engine — KCS-powered feedback loop for verified code generation.

Architecture:
  1. Design intent → LLM generates code
  2. KCS-1b verifies design→code translation loss
  3. Issues → targeted fix suggestions
  4. LLM regenerates → KCS re-verifies
  5. Loop until grade ≥ B or max iterations

This is the INVERSE of KCS: KCS measures loss, this engine MINIMIZES loss.

Benchmark target: コード生成 65%→92%

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

VERSION = "1.0.0"

# ── KCS imports ──
try:
    from katala_coding.kcs1b import KCS1b, KCS1bResult
    _HAS_KCS1B = True
except ImportError:
    _HAS_KCS1B = False

try:
    from katala_coding.kcs2a import KCS2a
    _HAS_KCS2A = True
except ImportError:
    _HAS_KCS2A = False


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

MAX_ITERATIONS = 5
TARGET_GRADE = "B"  # Minimum acceptable grade
GRADE_ORDER = {"S": 4, "A": 3, "B": 2, "C": 1, "D": 0}

# Fix strategy templates by axis
FIX_STRATEGIES = {
    "R_struct": [
        "Add type hints to all function parameters and return values",
        "Extract nested logic into named helper functions (max depth 3)",
        "Add error handling for edge cases",
        "Split functions longer than 30 lines",
    ],
    "R_context": [
        "Add module-level docstring explaining purpose and design intent",
        "Add docstrings to all public functions with Args/Returns",
        "Add inline comments for non-obvious logic",
        "Use descriptive variable names that reflect domain concepts",
    ],
    "R_qualia": [
        "Follow existing code conventions (naming, structure patterns)",
        "Use named constants instead of magic numbers",
        "Add logging at key decision points",
        "Structure code to match the mental model in the design doc",
    ],
    "R_cultural": [
        "Use standard library patterns where possible",
        "Follow PEP 8 / Rust conventions consistently",
        "Use idiomatic constructs (list comprehensions, pattern matching)",
    ],
    "R_temporal": [
        "Avoid deprecated APIs",
        "Use current best practices (dataclasses, typing, pathlib)",
        "Pin dependency versions",
    ],
}

# Code quality patterns to detect and fix
QUALITY_PATTERNS = {
    "magic_number": re.compile(r'(?<!["\'])\b(?:0\.\d+|\d{2,})\b(?!["\'])'),
    "bare_except": re.compile(r'\bexcept\s*:'),
    "todo_fixme": re.compile(r'#\s*(TODO|FIXME|HACK|XXX)', re.IGNORECASE),
    "long_function": re.compile(r'^(def |fn )\w+.*:', re.MULTILINE),
    "deep_nesting": re.compile(r'^(\s{16,})\S', re.MULTILINE),  # 4+ indent levels
    "no_docstring": re.compile(r'def \w+\([^)]*\).*:\s*\n\s+(?!"""|\'\'\')'),
    "global_var": re.compile(r'^\s*global\s+\w+', re.MULTILINE),
}


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CodeIssue:
    """Specific issue found in generated code."""
    axis: str          # Which HTLF axis (R_struct, R_context, etc.)
    severity: str      # "critical" | "major" | "minor"
    description: str
    line: Optional[int] = None
    fix_suggestion: str = ""


@dataclass
class GenerationResult:
    """Result of a code generation attempt."""
    code: str
    grade: str = "D"
    fidelity: float = 0.0
    axis_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[CodeIssue] = field(default_factory=list)
    iteration: int = 0
    converged: bool = False


@dataclass
class GenerationSession:
    """Full generation session tracking."""
    design_intent: str
    language: str = "python"
    iterations: List[GenerationResult] = field(default_factory=list)
    total_time: float = 0.0
    final_grade: str = "D"
    improvement_trajectory: List[float] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Code Quality Analyzer (static, no LLM needed)
# ═══════════════════════════════════════════════════════════════════════════

class CodeQualityAnalyzer:
    """Static analysis of generated code quality."""

    def analyze(self, code: str, language: str = "python") -> List[CodeIssue]:
        """Analyze code for common quality issues."""
        issues = []

        lines = code.split("\n")

        # Magic numbers
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#") or line.strip().startswith("//"):
                continue
            # Skip import lines, string literals, data tables
            if any(kw in line for kw in ["import ", "from ", "version", "VERSION"]):
                continue
            matches = QUALITY_PATTERNS["magic_number"].findall(line)
            # Filter: keep only suspicious numeric literals
            for m in matches:
                try:
                    val = float(m)
                    if val not in {0, 1, 2, -1, 0.0, 1.0, 0.5, 100, 10}:
                        issues.append(CodeIssue(
                            axis="R_qualia",
                            severity="minor",
                            description=f"Magic number {m}",
                            line=i,
                            fix_suggestion=f"Extract {m} to a named constant",
                        ))
                except ValueError:
                    pass

        # Bare except
        for i, line in enumerate(lines, 1):
            if QUALITY_PATTERNS["bare_except"].search(line):
                issues.append(CodeIssue(
                    axis="R_struct",
                    severity="major",
                    description="Bare except clause",
                    line=i,
                    fix_suggestion="Specify exception type: except ValueError:",
                ))

        # TODO/FIXME (incomplete implementation)
        for i, line in enumerate(lines, 1):
            m = QUALITY_PATTERNS["todo_fixme"].search(line)
            if m:
                issues.append(CodeIssue(
                    axis="R_struct",
                    severity="major",
                    description=f"{m.group(1)} marker found — incomplete implementation",
                    line=i,
                    fix_suggestion="Resolve the TODO/FIXME before finalizing",
                ))

        # Deep nesting
        for i, line in enumerate(lines, 1):
            if QUALITY_PATTERNS["deep_nesting"].match(line):
                issues.append(CodeIssue(
                    axis="R_struct",
                    severity="major",
                    description="Deep nesting (4+ levels)",
                    line=i,
                    fix_suggestion="Extract nested logic into helper functions",
                ))

        # Missing docstrings
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*(def |class )\w+', line):
                # Check next non-empty line for docstring
                for j in range(i, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        if not (next_line.startswith('"""') or next_line.startswith("'''")):
                            issues.append(CodeIssue(
                                axis="R_context",
                                severity="minor",
                                description="Missing docstring",
                                line=i,
                                fix_suggestion="Add docstring explaining purpose, args, return",
                            ))
                        break

        # Long functions (count lines between def statements)
        func_starts = []
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*(def |fn )\w+', line):
                func_starts.append(i)

        for idx, start in enumerate(func_starts):
            end = func_starts[idx + 1] - 1 if idx + 1 < len(func_starts) else len(lines)
            func_len = end - start
            if func_len > 50:
                issues.append(CodeIssue(
                    axis="R_struct",
                    severity="major",
                    description=f"Long function ({func_len} lines)",
                    line=start,
                    fix_suggestion="Split into smaller focused functions",
                ))

        return issues

    def compute_scores(self, code: str, design: str, issues: List[CodeIssue]) -> Dict[str, float]:
        """Compute per-axis scores based on static analysis."""

        # Base scores
        scores = {
            "R_struct": 0.80,
            "R_context": 0.70,
            "R_qualia": 0.75,
            "R_cultural": 0.85,
            "R_temporal": 0.90,
        }

        # Penalize based on issues
        severity_penalty = {"critical": 0.15, "major": 0.05, "minor": 0.02}

        for issue in issues:
            axis = issue.axis
            penalty = severity_penalty.get(issue.severity, 0.02)
            if axis in scores:
                scores[axis] = max(scores[axis] - penalty, 0.0)

        # Bonus: design concept coverage
        design_words = set(design.lower().split())
        code_lower = code.lower()
        concept_coverage = sum(1 for w in design_words if w in code_lower) / max(len(design_words), 1)
        scores["R_context"] = min(scores["R_context"] + concept_coverage * 0.15, 1.0)

        # Bonus: type hints present
        type_hint_count = len(re.findall(r':\s*(int|str|float|bool|List|Dict|Optional|Any|Tuple)', code))
        if type_hint_count >= 3:
            scores["R_struct"] = min(scores["R_struct"] + 0.05, 1.0)

        # Bonus: docstring coverage
        func_count = len(re.findall(r'\bdef \w+', code))
        doc_count = len(re.findall(r'"""[\s\S]*?"""', code))
        if func_count > 0:
            doc_ratio = min(doc_count / func_count, 1.0)
            scores["R_context"] = min(scores["R_context"] + doc_ratio * 0.10, 1.0)

        return {k: round(v, 4) for k, v in scores.items()}


# ═══════════════════════════════════════════════════════════════════════════
# Fix Suggestion Generator
# ═══════════════════════════════════════════════════════════════════════════

class FixSuggestionGenerator:
    """Generate targeted fix suggestions based on KCS analysis."""

    def generate(self, issues: List[CodeIssue], axis_scores: Dict[str, float]) -> List[str]:
        """Generate prioritized fix suggestions."""
        suggestions = []

        # Find weakest axis
        if axis_scores:
            weakest_axis = min(axis_scores, key=axis_scores.get)
            weakest_score = axis_scores[weakest_axis]

            if weakest_score < 0.6:
                suggestions.append(f"PRIORITY: {weakest_axis} is critically low ({weakest_score:.2f})")
                # Add axis-specific strategies
                for strategy in FIX_STRATEGIES.get(weakest_axis, [])[:2]:
                    suggestions.append(f"  → {strategy}")

        # Group issues by severity
        critical = [i for i in issues if i.severity == "critical"]
        major = [i for i in issues if i.severity == "major"]

        for issue in critical[:3]:
            suggestions.append(f"CRITICAL L{issue.line}: {issue.description}")
            if issue.fix_suggestion:
                suggestions.append(f"  → {issue.fix_suggestion}")

        for issue in major[:5]:
            suggestions.append(f"MAJOR L{issue.line}: {issue.description}")
            if issue.fix_suggestion:
                suggestions.append(f"  → {issue.fix_suggestion}")

        return suggestions


# ═══════════════════════════════════════════════════════════════════════════
# Code Generation Engine
# ═══════════════════════════════════════════════════════════════════════════

class CodeGenerationEngine:
    """KCS-powered verified code generation with feedback loop.

    Flow:
      design_intent → generate_code() → KCS verify → fix suggestions → regenerate
                                ↑                           |
                                └───────────────────────────┘

    The engine doesn't call LLMs directly — it wraps whatever code generator
    the caller provides (LLM, template, human) with KCS quality gates.
    """

    def __init__(self):
        self.analyzer = CodeQualityAnalyzer()
        self.fix_gen = FixSuggestionGenerator()
        self.kcs1b = KCS1b() if _HAS_KCS1B else None
        self.kcs2a = KCS2a() if _HAS_KCS2A else None

    def verify_generation(
        self,
        design: str,
        code: str,
        language: str = "python",
    ) -> GenerationResult:
        """Verify a single code generation attempt.

        Args:
            design: Design intent / specification text.
            code: Generated code to verify.
            language: Programming language.

        Returns:
            GenerationResult with grade, scores, and issues.
        """
        # Static analysis
        static_issues = self.analyzer.analyze(code, language)

        # KCS-1b verification (if available)
        if self.kcs1b:
            try:
                kcs_result = self.kcs1b.verify(design, code)
                axis_scores = {
                    "R_struct": kcs_result.r_struct,
                    "R_context": kcs_result.r_context,
                    "R_qualia": kcs_result.r_qualia,
                    "R_cultural": kcs_result.r_cultural,
                    "R_temporal": kcs_result.r_temporal,
                }
                grade = kcs_result.grade
                fidelity = kcs_result.fidelity
                # Merge KCS issues with static issues
                for issue in kcs_result.issues:
                    static_issues.append(CodeIssue(
                        axis=issue.get("axis", "R_struct"),
                        severity=issue.get("severity", "minor"),
                        description=issue.get("description", str(issue)),
                    ))
            except Exception:
                axis_scores = self.analyzer.compute_scores(code, design, static_issues)
                fidelity = sum(axis_scores.values()) / max(len(axis_scores), 1)
                grade = self._compute_grade(fidelity, axis_scores)
        else:
            axis_scores = self.analyzer.compute_scores(code, design, static_issues)
            fidelity = sum(axis_scores.values()) / max(len(axis_scores), 1)
            grade = self._compute_grade(fidelity, axis_scores)

        return GenerationResult(
            code=code,
            grade=grade,
            fidelity=fidelity,
            axis_scores=axis_scores,
            issues=static_issues,
        )

    def feedback_loop(
        self,
        design: str,
        generator_fn: Callable[[str, List[str]], str],
        language: str = "python",
        max_iterations: int = MAX_ITERATIONS,
        target_grade: str = TARGET_GRADE,
    ) -> GenerationSession:
        """Run the full generation→verify→fix→regenerate loop.

        Args:
            design: Design intent / specification.
            generator_fn: Callable(design, fix_suggestions) → code string.
                         First call gets empty suggestions.
            language: Target language.
            max_iterations: Maximum loop iterations.
            target_grade: Minimum acceptable grade.

        Returns:
            GenerationSession with full trajectory.
        """
        session = GenerationSession(design_intent=design, language=language)
        start = time.time()
        suggestions: List[str] = []

        for i in range(max_iterations):
            # Generate
            code = generator_fn(design, suggestions)

            # Verify
            result = self.verify_generation(design, code, language)
            result.iteration = i + 1
            session.iterations.append(result)
            session.improvement_trajectory.append(result.fidelity)

            # Check convergence
            if GRADE_ORDER.get(result.grade, 0) >= GRADE_ORDER.get(target_grade, 2):
                result.converged = True
                break

            # Generate fix suggestions for next iteration
            suggestions = self.fix_gen.generate(result.issues, result.axis_scores)

            # Check for stagnation (same score ±0.01 for 2 iterations)
            if len(session.improvement_trajectory) >= 3:
                recent = session.improvement_trajectory[-3:]
                if max(recent) - min(recent) < 0.01:
                    break  # Stagnated

        session.total_time = time.time() - start
        session.final_grade = session.iterations[-1].grade if session.iterations else "D"

        return session

    def get_fix_prompt(self, result: GenerationResult) -> str:
        """Generate a human/LLM-readable fix prompt from verification results.

        Use this to feed back into an LLM for code improvement.
        """
        suggestions = self.fix_gen.generate(result.issues, result.axis_scores)

        parts = [
            f"Code grade: {result.grade} (fidelity: {result.fidelity:.3f})",
            f"Axis scores: {', '.join(f'{k}={v:.2f}' for k, v in result.axis_scores.items())}",
            "",
            "Issues to fix:",
        ]
        for s in suggestions:
            parts.append(f"  {s}")

        return "\n".join(parts)

    def _compute_grade(self, fidelity: float, scores: Dict[str, float]) -> str:
        """Compute grade from fidelity and axis scores."""
        min_score = min(scores.values()) if scores else 0
        if fidelity >= 0.85 and min_score >= 0.80:
            return "S"
        elif fidelity >= 0.75 and min_score >= 0.65:
            return "A"
        elif fidelity >= 0.60 and min_score >= 0.50:
            return "B"
        elif fidelity >= 0.45:
            return "C"
        else:
            return "D"


if __name__ == "__main__":
    engine = CodeGenerationEngine()

    # Test: verify a simple code snippet
    design = "Create a function that validates email addresses using regex"
    code = '''
def validate_email(email):
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
'''

    result = engine.verify_generation(design, code)
    print(f"Grade: {result.grade} Fidelity: {result.fidelity:.3f}")
    print(f"Scores: {result.axis_scores}")
    print(f"Issues: {len(result.issues)}")
    for issue in result.issues[:5]:
        print(f"  [{issue.severity}] {issue.axis}: {issue.description}")

    print(f"\n{engine.get_fix_prompt(result)}")
    print(f"\n✅ CodeGenerationEngine v{VERSION} OK")
