"""KCS-2a: Design Intent Reverse Inference Engine.

Given code, infer what the original design intent *should have been*,
then identify gaps between inferred intent and actual implementation.
This directly addresses Goal Setting: "what should be built next?"

The reverse direction: Code → Design Intent → Next Goals

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
Date: 2026-03-01
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any

# ── Constants ──
MIN_CONCEPT_FREQUENCY = 2
GOAL_PRIORITY_HIGH = "high"
GOAL_PRIORITY_MEDIUM = "medium"
GOAL_PRIORITY_LOW = "low"
COVERAGE_THRESHOLD_GOOD = 0.7
COVERAGE_THRESHOLD_POOR = 0.4


@dataclass(slots=True)
class InferredIntent:
    """Reverse-inferred design intent from code analysis."""
    # What the code appears to be trying to do
    primary_purpose: str
    sub_purposes: list[str]

    # Concepts the code manipulates
    domain_concepts: list[str]
    theoretical_frameworks: list[str]

    # Detected patterns
    design_patterns: list[str]
    architectural_style: str  # "modular" | "monolithic" | "layered" | "pipeline"

    # Gaps: things the code tries to do but doesn't fully achieve
    incomplete_implementations: list[str]
    missing_tests: list[str]
    undocumented_decisions: list[str]


@dataclass(slots=True)
class NextGoal:
    """An automatically generated next goal with priority and rationale."""
    goal: str
    priority: str          # high / medium / low
    rationale: str
    estimated_impact: str  # Which axis this improves
    source: str            # "reverse_inference" | "gap_analysis" | "solver_feedback"


@dataclass(slots=True)
class ReverseAnalysis:
    """Full KCS-2a output: inferred intent + generated goals."""
    intent: InferredIntent
    goals: list[NextGoal]
    goal_confidence: float  # 0-1: how confident are we in these goals
    coverage_score: float   # How much of the code's intent is understood


# ── Theoretical Framework Detection ──

_FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    "quine_indeterminacy": [
        "indeterminacy", "underdetermined", "translation", "behavioral",
        "radical translation", "gavagai",
    ],
    "duhem_quine": [
        "holistic", "web of belief", "auxiliary", "not in isolation",
        "holistic_dependency",
    ],
    "kuhn_paradigm": [
        "paradigm", "incommensurable", "revolution", "normal science",
        "paradigm_shift", "paradigm_distance",
    ],
    "barthes_text": [
        "death of the author", "reader", "semantic drift", "arbitrary",
        "text_theory",
    ],
    "behaviorism": [
        "behavioral", "observable", "stimulus", "response",
        "operant", "behavioral_delta",
    ],
    "pragmatism": [
        "pragmat", "usefulness", "cash value", "practical consequence",
    ],
    "sapir_whorf": [
        "linguistic relativity", "language shapes", "conceptual framework",
        "sapir", "whorf",
    ],
    "holographic": [
        "holographic", "boundary", "bulk", "surface", "information",
        "holographic_principle",
    ],
    "information_theory": [
        "entropy", "mutual information", "channel capacity", "shannon",
        "bits", "compression",
    ],
    # ── Music Domain Frameworks (KS30b+) ──
    "harmonic_analysis": [
        "chroma", "chord", "key_estimate", "harmony", "tonal",
        "major", "minor", "detected_chords", "chroma_profile",
        "key_concepts", "dominant", "seventh", "progression",
    ],
    "spectral_processing": [
        "spectrogram", "fft", "stft", "griffin", "phase",
        "spectral_centroid", "n_fft", "hop_length", "magnitude",
        "frequency", "librosa", "mel", "mfcc",
    ],
    "spatial_audio": [
        "stereo", "panning", "surround", "positioning",
        "channel", "mono", "binaural", "spatial",
        "left", "right", "center",
    ],
    "rhythmic_structure": [
        "bpm", "tempo", "beat", "grid", "onset",
        "beat_track", "onset_strength", "rhythm",
        "syncopation", "meter", "time_signature",
    ],
    "music_generation": [
        "patch", "song_structure", "verse", "chorus", "bridge",
        "intro", "outro", "loop", "arrangement", "orchestration",
        "synthesis", "waveform", "audio_path",
    ],
    "psychoacoustics": [
        "loudness", "masking", "critical band", "perception",
        "timbre", "roughness", "dissonance", "consonance",
        "auditory", "hearing", "fletcher",
    ],
}


def _detect_frameworks(code_lower: str, doc_text: str) -> list[str]:
    """Detect theoretical frameworks referenced in code."""
    combined = code_lower + " " + doc_text.lower()
    found = []
    for framework, markers in _FRAMEWORK_SIGNATURES.items():
        if any(m in combined for m in markers):
            found.append(framework)
    return found


# ── Design Pattern Detection ──

_PATTERN_SIGNATURES: dict[str, str] = {
    "singleton": r"_CACHED_|_instance|__new__.*cls\._",
    "strategy": r"strategy|backend|fallback.*if.*else",
    "pipeline": r"pipeline|stage|step.*result|chain",
    "observer": r"callback|listener|on_event|subscribe",
    "factory": r"create_|make_|build_|factory",
    "bridge": r"bridge|adapter|rust_bridge|_has\(",
    "template_method": r"def\s+\w+.*:\s*\n.*super\(\)\.",
    "composite": r"children|components|add_child|traverse",
    "decorator_pattern": r"@\w+\ndef|wrapper|wrapped",
}


def _detect_patterns(code: str) -> list[str]:
    """Detect design patterns in code."""
    found = []
    code_lower = code.lower()
    for pattern, signature in _PATTERN_SIGNATURES.items():
        if re.search(signature, code_lower):
            found.append(pattern)
    return found


# ── Architecture Detection ──

def _detect_architecture(structure: dict) -> str:
    """Infer architectural style from code structure."""
    classes = structure.get("classes", 0)
    functions = structure.get("functions", 0)
    chains = structure.get("inheritance_chains", [])

    if chains and any(len(bases) > 0 for _, bases in chains):
        if len(chains) > 3:
            return "layered"
        return "modular"

    if classes == 0 and functions > 5:
        return "pipeline"

    if classes > 5:
        return "modular"

    return "monolithic"


# ── Code Structure Analysis (reused from kcs1a) ──

def _parse_structure(code: str) -> dict[str, Any]:
    """Parse code and extract structural features."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"parseable": False, "classes": 0, "functions": 0,
                "class_names": [], "function_names": [],
                "inheritance_chains": [], "lines": len(code.splitlines())}

    classes = []
    functions = []
    inheritance_chains = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
            bases = [getattr(b, 'id', getattr(b, 'attr', '?')) for b in node.bases]
            if bases:
                inheritance_chains.append((node.name, bases))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(node.name)

    return {
        "parseable": True,
        "classes": len(classes),
        "class_names": classes,
        "functions": len(functions),
        "function_names": functions,
        "inheritance_chains": inheritance_chains,
        "lines": len(code.splitlines()),
    }


# ── Gap Analysis ──

def _find_incomplete_implementations(code: str) -> list[str]:
    """Find TODO, FIXME, NotImplementedError, pass-only functions."""
    gaps = []

    # TODO/FIXME comments
    todos = re.findall(r'#\s*(TODO|FIXME|HACK|XXX|WARN)[\s:]+(.+)', code, re.IGNORECASE)
    for tag, msg in todos:
        gaps.append(f"{tag}: {msg.strip()}")

    # NotImplementedError
    not_impl = re.findall(r'raise\s+NotImplementedError\s*\(([^)]*)\)', code)
    for msg in not_impl:
        gaps.append(f"Not implemented: {msg.strip(chr(34)).strip(chr(39))}")

    # pass-only functions
    pass_funcs = re.findall(r'def\s+(\w+)\([^)]*\):\s*\n\s+pass\s*$', code, re.MULTILINE)
    for f in pass_funcs:
        gaps.append(f"Stub function: {f}()")

    return gaps


def _find_missing_tests(code: str, structure: dict) -> list[str]:
    """Identify functions that likely need tests but don't have them."""
    missing = []
    has_test_file = bool(re.search(r'def test_|assert |pytest|unittest', code))

    if not has_test_file:
        public_funcs = [f for f in structure.get("function_names", [])
                        if not f.startswith('_')]
        for f in public_funcs:
            missing.append(f"No test coverage: {f}()")

    return missing


def _find_undocumented_decisions(code: str, structure: dict) -> list[str]:
    """Find design decisions that lack documentation."""
    undocumented = []

    # Magic numbers without comments
    magic_lines = []
    for i, line in enumerate(code.splitlines(), 1):
        nums = re.findall(r'(?<![.\w])\d+\.\d+(?![.\w])', line)
        safe = {'0.0', '1.0', '0.5'}
        bad = [n for n in nums if n not in safe]
        if bad and '#' not in line:
            magic_lines.append(f"Line {i}: unexplained constant {', '.join(bad)}")

    if len(magic_lines) > 3:
        undocumented.append(f"{len(magic_lines)} lines with unexplained numeric constants")

    # Functions without docstrings
    func_names = structure.get("function_names", [])
    docstring_pattern = r'def\s+\w+.*?:\s*\n\s+"""'
    docstrings_found = len(re.findall(docstring_pattern, code))
    undoc_count = len(func_names) - docstrings_found
    if undoc_count > 0:
        undocumented.append(f"{undoc_count} functions without docstrings")

    return undocumented


# ── Purpose Inference ──

def _infer_purpose(code: str, structure: dict, frameworks: list[str]) -> tuple[str, list[str]]:
    """Infer the primary purpose and sub-purposes from code analysis."""
    code_lower = code.lower()

    # Extract module docstring
    module_doc = ""
    match = re.match(r'^"""(.*?)"""|^\'\'\'(.*?)\'\'\'', code, re.DOTALL)
    if match:
        module_doc = match.group(1) or match.group(2) or ""

    # Primary purpose from module docstring first line
    if module_doc:
        first_line = module_doc.strip().split('\n')[0].strip()
        primary = first_line if len(first_line) > 10 else "Unknown purpose"
    else:
        # Infer from class/function names
        classes = structure.get("class_names", [])
        if classes:
            primary = f"Implements {', '.join(classes[:3])}"
        else:
            primary = "Utility functions module"

    # Sub-purposes from class/function groupings
    sub_purposes = []
    funcs = structure.get("function_names", [])

    # Group functions by prefix
    prefixes: dict[str, list[str]] = {}
    for f in funcs:
        parts = f.lstrip('_').split('_')
        if len(parts) >= 2:
            prefix = parts[0]
            prefixes.setdefault(prefix, []).append(f)

    for prefix, group in prefixes.items():
        if len(group) >= MIN_CONCEPT_FREQUENCY:
            sub_purposes.append(f"{prefix}: {len(group)} related functions ({', '.join(group[:3])})")

    return primary, sub_purposes


def _extract_domain_concepts(code: str) -> list[str]:
    """Extract domain-specific concepts from code identifiers and comments."""
    # Extract from class names, function names, and comments
    identifiers = set(re.findall(r'[A-Z][a-z]+(?=[A-Z])|[a-z_]{3,}', code))

    # Filter out Python builtins and common words
    noise = {"self", "None", "True", "False", "return", "import", "from",
             "class", "def", "for", "while", "with", "try", "except",
             "raise", "pass", "break", "continue", "yield", "async",
             "await", "lambda", "str", "int", "float", "bool", "list",
             "dict", "set", "tuple", "type", "len", "range", "print",
             "isinstance", "hasattr", "getattr", "setattr", "super",
             "result", "value", "data", "text", "name", "key",
             "item", "items", "args", "kwargs", "index", "count"}

    concepts = [c for c in identifiers if c.lower() not in noise and len(c) > 3]

    # Count frequency and keep recurring concepts
    from collections import Counter
    freq = Counter(re.findall(r'\b(' + '|'.join(re.escape(c) for c in concepts) + r')\b', code))
    return [c for c, n in freq.most_common(20) if n >= MIN_CONCEPT_FREQUENCY]


# ── Goal Generation ──

def _generate_goals(
    intent: InferredIntent,
    solver_feedback: list[dict[str, Any]] | None = None,
) -> list[NextGoal]:
    """Generate prioritized next goals from reverse analysis + solver feedback."""
    goals: list[NextGoal] = []

    # 1. From incomplete implementations (high priority)
    for gap in intent.incomplete_implementations:
        goals.append(NextGoal(
            goal=f"Complete: {gap}",
            priority=GOAL_PRIORITY_HIGH,
            rationale="Incomplete implementation detected in code",
            estimated_impact="R_struct (structural completeness)",
            source="reverse_inference",
        ))

    # 2. From missing tests (medium priority)
    for test in intent.missing_tests[:5]:  # Cap at 5
        goals.append(NextGoal(
            goal=f"Add test: {test}",
            priority=GOAL_PRIORITY_MEDIUM,
            rationale="Public API without test coverage",
            estimated_impact="R_temporal (future survivability)",
            source="gap_analysis",
        ))

    # 3. From undocumented decisions (medium priority)
    for undoc in intent.undocumented_decisions:
        goals.append(NextGoal(
            goal=f"Document: {undoc}",
            priority=GOAL_PRIORITY_MEDIUM,
            rationale="Design decision without documentation",
            estimated_impact="R_context (theoretical context preservation)",
            source="gap_analysis",
        ))

    # 4. From detected frameworks without full implementation
    known_framework_modules = {
        "quine_indeterminacy": "cultural_loss",
        "kuhn_paradigm": "temporal_loss",
        "behaviorism": "qualia_engine",
        "holographic": "htlf",
        # Music domain: framework → expected module/concept
        "harmonic_analysis": "harmonic_structure",
        "spectral_processing": "spectrogram",
        "spatial_audio": "stereo",
        "rhythmic_structure": "beat_grid",
        "music_generation": "song_structure",
        "psychoacoustics": "perceptual_model",
    }
    for fw in intent.theoretical_frameworks:
        expected_module = known_framework_modules.get(fw)
        if expected_module and expected_module not in str(intent.domain_concepts):
            goals.append(NextGoal(
                goal=f"Deepen {fw} integration",
                priority=GOAL_PRIORITY_LOW,
                rationale=f"Framework {fw} referenced but may not be fully implemented",
                estimated_impact="R_context (theoretical depth)",
                source="reverse_inference",
            ))

    # 5. From multi-solver feedback (if provided)
    if solver_feedback:
        for feedback in solver_feedback:
            disagreement = feedback.get("disagreement_axis")
            confidence = feedback.get("avg_confidence", 0.5)
            if disagreement and confidence < 0.7:
                goals.append(NextGoal(
                    goal=f"Resolve solver disagreement on {disagreement}",
                    priority=GOAL_PRIORITY_HIGH,
                    rationale=f"Multi-solver confidence {confidence:.0%} below threshold",
                    estimated_impact="Multi-Solver Consensus + Goal Setting",
                    source="solver_feedback",
                ))

    # Sort by priority
    priority_order = {GOAL_PRIORITY_HIGH: 0, GOAL_PRIORITY_MEDIUM: 1, GOAL_PRIORITY_LOW: 2}
    goals.sort(key=lambda g: priority_order.get(g.priority, 3))

    return goals


# ════════════════════════════════════════════
# KCS-2a: Main Engine
# ════════════════════════════════════════════

class KCS2a:
    """Katala Coding Series 2a — Design Intent Reverse Inference.

    Given code, infers what the design intent should have been,
    identifies gaps, and generates prioritized next goals.

    This is the reverse direction of KCS-1a:
    - KCS-1a: Design → Code (forward, measures loss)
    - KCS-2a: Code → Design → Goals (reverse, generates direction)

    Together they form a bidirectional feedback loop that directly
    improves autonomous goal setting.
    """

    def analyze(
        self,
        code: str,
        solver_feedback: list[dict[str, Any]] | None = None,
    ) -> ReverseAnalysis:
        """Reverse-infer design intent and generate next goals.

        Parameters
        ----------
        code : str
            Source code to analyze.
        solver_feedback : list[dict], optional
            Multi-solver disagreement data for goal generation.

        Returns
        -------
        ReverseAnalysis
            Inferred intent + prioritized goals + confidence metrics.
        """
        structure = _parse_structure(code)
        code_lower = code.lower()

        # Extract docstrings/comments
        docstrings = re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', code, re.DOTALL)
        comments = re.findall(r'#\s*(.*)', code)
        doc_text = ' '.join(d[0] or d[1] for d in docstrings) + ' ' + ' '.join(comments)

        # Detect components
        frameworks = _detect_frameworks(code_lower, doc_text)
        patterns = _detect_patterns(code)
        architecture = _detect_architecture(structure)
        primary, sub_purposes = _infer_purpose(code, structure, frameworks)
        concepts = _extract_domain_concepts(code)

        # Find gaps
        incomplete = _find_incomplete_implementations(code)
        missing_tests = _find_missing_tests(code, structure)
        undocumented = _find_undocumented_decisions(code, structure)

        intent = InferredIntent(
            primary_purpose=primary,
            sub_purposes=sub_purposes,
            domain_concepts=concepts,
            theoretical_frameworks=frameworks,
            design_patterns=patterns,
            architectural_style=architecture,
            incomplete_implementations=incomplete,
            missing_tests=missing_tests,
            undocumented_decisions=undocumented,
        )

        # Generate goals
        goals = _generate_goals(intent, solver_feedback)

        # Confidence: based on how much we could extract
        signals = [
            bool(primary and primary != "Unknown purpose"),
            bool(frameworks),
            bool(concepts),
            bool(patterns),
            structure.get("parseable", False),
        ]
        goal_confidence = round(sum(signals) / len(signals), SCORE_DECIMAL_PLACES := 4)

        # Coverage: how much of the code's intent we understood
        total_funcs = len(structure.get("function_names", []))
        documented_funcs = len(re.findall(r'def\s+\w+.*?:\s*\n\s+"""', code))
        coverage = round(documented_funcs / max(1, total_funcs), 4)

        return ReverseAnalysis(
            intent=intent,
            goals=goals,
            goal_confidence=goal_confidence,
            coverage_score=coverage,
        )

    def analyze_file(self, file_path: str, **kwargs: Any) -> ReverseAnalysis:
        """Analyze a file and generate goals."""
        with open(file_path, encoding="utf-8") as f:
            return self.analyze(f.read(), **kwargs)

    @staticmethod
    def format_analysis(ra: ReverseAnalysis) -> str:
        """Pretty-print reverse analysis."""
        lines = [
            "╔══ KCS-2a Reverse Inference ══╗",
            f"║ Purpose: {ra.intent.primary_purpose[:60]}",
            f"║ Architecture: {ra.intent.architectural_style}",
            f"║ Frameworks: {', '.join(ra.intent.theoretical_frameworks) or 'none detected'}",
            f"║ Patterns: {', '.join(ra.intent.design_patterns) or 'none detected'}",
            f"║ Concepts: {', '.join(ra.intent.domain_concepts[:8]) or 'none'}",
            f"║ Confidence: {ra.goal_confidence:.0%} | Coverage: {ra.coverage_score:.0%}",
            "║",
        ]
        if ra.intent.incomplete_implementations:
            lines.append("║ 🔴 Incomplete:")
            for g in ra.intent.incomplete_implementations[:5]:
                lines.append(f"║   • {g}")
        if ra.goals:
            lines.append("║")
            lines.append(f"║ 🎯 Generated Goals ({len(ra.goals)}):")
            for g in ra.goals[:8]:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(g.priority, "⚪")
                lines.append(f"║   {icon} [{g.priority}] {g.goal}")
                lines.append(f"║     → Impact: {g.estimated_impact} | Source: {g.source}")
        lines.append("╚" + "═" * 36 + "╝")
        return "\n".join(lines)
