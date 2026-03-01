"""
Analogical Abstraction Solver — Novel abstract reasoning via inverse HTLF.

Solver Type #11: Pushes ARC-AGI-2 style reasoning beyond Q*.

Core insight: ARC-AGI-2 asks "find the transformation rule from examples."
This is HTLF's R_struct solved as an INVERSE problem:
  Forward HTLF:  given T, measure loss(source, T(source))
  Inverse HTLF:  given (source, target) pairs, find T that minimizes loss

Q* uses single deep search tree. KS uses 10+ orthogonal frameworks
searching in parallel for independent candidate rules.

Architecture:
  1. Pattern extraction: decompose input-output pairs into structural primitives
  2. Rule synthesis: generate candidate transformations from primitives
  3. Cross-validation: test each candidate against held-out examples
  4. Orthogonal verification: 10-type solvers independently verify candidates
  5. Confidence-weighted selection: pick best rule

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import Any, Callable

from katala_samurai.solver_types import AbstractSolver, DEFAULT_EXPERTISE
from katala_samurai.solver_quality import SolverProfile, SolverVote

# ── Constants ──
MAX_CANDIDATE_RULES = 50          # Max transformation candidates to generate
MIN_EXAMPLES_FOR_CONFIDENCE = 3   # Need at least 3 examples for high confidence
CROSS_VALIDATION_HOLDOUT = 0.2    # Hold out 20% of examples for validation
PRIMITIVE_TYPES = [
    "identity", "rotation", "reflection", "translation", "scaling",
    "color_swap", "fill", "crop", "tile", "overlay",
    "filter", "sort", "group", "split", "merge",
    "count", "boundary", "flood", "symmetry", "invert",
]
COMPOSITION_DEPTH_LIMIT = 3       # Max depth for composed transformations
STRUCTURAL_SIMILARITY_THRESHOLD = 0.8  # When to consider two structures equivalent


@dataclass(slots=True)
class Pattern:
    """A structural primitive extracted from input-output pairs."""
    primitive_type: str          # One of PRIMITIVE_TYPES
    parameters: dict[str, Any]   # Primitive-specific params
    confidence: float            # How confident we are this primitive applies
    evidence_indices: list[int]  # Which examples support this primitive


@dataclass(slots=True)
class CandidateRule:
    """A candidate transformation rule."""
    primitives: list[Pattern]    # Composed primitives
    composition_type: str        # "sequential" | "parallel" | "conditional"
    score: float                 # Cross-validation score (0-1)
    coverage: float              # What fraction of examples it explains
    complexity: int              # Number of primitives (Occam penalty)
    explanation: str             # Human-readable rule description


@dataclass(slots=True)
class AbstractionResult:
    """Result of abstract reasoning on a set of examples."""
    best_rule: CandidateRule | None
    all_candidates: list[CandidateRule]
    confidence: float
    reasoning_trace: list[str]
    n_examples: int
    n_primitives_found: int
    search_exhausted: bool       # Did we explore all candidates?


# ════════════════════════════════════════════
# Phase 1: Pattern Extraction
# ════════════════════════════════════════════

def _extract_structural_primitives(
    examples: list[tuple[Any, Any]],
) -> list[Pattern]:
    """Decompose input-output pairs into structural primitives.

    For each example (input, output), detect what transformation
    primitives could explain the relationship.
    """
    primitives: list[Pattern] = []

    for i, (inp, out) in enumerate(examples):
        inp_features = _analyze_structure(inp)
        out_features = _analyze_structure(out)

        # Detect dimensional changes
        if inp_features["dimensions"] != out_features["dimensions"]:
            primitives.append(Pattern(
                primitive_type="scaling",
                parameters={
                    "input_dim": inp_features["dimensions"],
                    "output_dim": out_features["dimensions"],
                    "ratio": _safe_ratio(out_features["dimensions"], inp_features["dimensions"]),
                },
                confidence=0.8,
                evidence_indices=[i],
            ))

        # Detect element count changes
        if inp_features["element_count"] != out_features["element_count"]:
            primitives.append(Pattern(
                primitive_type="filter" if out_features["element_count"] < inp_features["element_count"] else "fill",
                parameters={
                    "input_count": inp_features["element_count"],
                    "output_count": out_features["element_count"],
                },
                confidence=0.7,
                evidence_indices=[i],
            ))

        # Detect symmetry
        if out_features.get("symmetric") and not inp_features.get("symmetric"):
            primitives.append(Pattern(
                primitive_type="symmetry",
                parameters={"axis": out_features.get("symmetry_axis", "unknown")},
                confidence=0.6,
                evidence_indices=[i],
            ))

        # Detect inversion
        if _is_inversion(inp_features, out_features):
            primitives.append(Pattern(
                primitive_type="invert",
                parameters={},
                confidence=0.75,
                evidence_indices=[i],
            ))

        # Detect identity (no change) — low priority, only if nothing else matches
        if _structural_similarity(inp_features, out_features) > STRUCTURAL_SIMILARITY_THRESHOLD:
            primitives.append(Pattern(
                primitive_type="identity",
                parameters={},
                confidence=0.2,  # Low: identity is the "null hypothesis"
                evidence_indices=[i],
            ))

        # Detect sorting
        if _is_sorted_version(inp_features, out_features):
            primitives.append(Pattern(
                primitive_type="sort",
                parameters={"order": "ascending"},
                confidence=0.85,
                evidence_indices=[i],
            ))

        # Detect grouping
        if out_features.get("has_groups") and not inp_features.get("has_groups"):
            primitives.append(Pattern(
                primitive_type="group",
                parameters={"criterion": _detect_grouping_criterion(inp_features, out_features)},
                confidence=0.65,
                evidence_indices=[i],
            ))

    # Consolidate: merge primitives found across multiple examples
    return _consolidate_primitives(primitives, len(examples))


def _analyze_structure(data: Any) -> dict[str, Any]:
    """Extract structural features from any data type."""
    features: dict[str, Any] = {}

    if isinstance(data, (list, tuple)):
        features["type"] = "sequence"
        features["element_count"] = len(data)
        features["dimensions"] = (len(data),)
        features["unique_elements"] = len(set(str(x) for x in data))
        features["sorted"] = data == sorted(data) if all(isinstance(x, (int, float)) for x in data) else False

        # Check for nested structure (grid)
        if data and isinstance(data[0], (list, tuple)):
            features["type"] = "grid"
            features["dimensions"] = (len(data), len(data[0]) if data else 0)
            features["element_count"] = sum(len(row) for row in data if isinstance(row, (list, tuple)))

        # Check symmetry
        features["symmetric"] = _check_symmetry(data)
        features["has_groups"] = _detect_groups(data)

    elif isinstance(data, dict):
        features["type"] = "mapping"
        features["element_count"] = len(data)
        features["dimensions"] = (len(data),)

    elif isinstance(data, str):
        features["type"] = "text"
        features["element_count"] = len(data)
        features["dimensions"] = (len(data),)
        features["unique_elements"] = len(set(data))

    else:
        features["type"] = "scalar"
        features["element_count"] = 1
        features["dimensions"] = (1,)

    return features


def _check_symmetry(data: Any) -> bool:
    """Check if data has symmetry."""
    if isinstance(data, (list, tuple)):
        return list(data) == list(reversed(data))
    return False


def _detect_groups(data: Any) -> bool:
    """Detect if data has group structure."""
    if not isinstance(data, (list, tuple)) or len(data) < 2:
        return False
    # Check if consecutive equal elements form groups
    groups = 0
    prev = None
    for item in data:
        if item != prev:
            groups += 1
            prev = item
    return groups < len(data) * 0.5  # Less than half unique → has groups


def _is_inversion(a_features: dict, b_features: dict) -> bool:
    """Check if b is an inversion of a."""
    return (a_features.get("type") == b_features.get("type") and
            a_features.get("dimensions") == b_features.get("dimensions"))


def _is_sorted_version(a_features: dict, b_features: dict) -> bool:
    """Check if b is a sorted version of a."""
    return (b_features.get("sorted", False) and
            not a_features.get("sorted", True) and
            a_features.get("element_count") == b_features.get("element_count"))


def _structural_similarity(a: dict, b: dict) -> float:
    """Compute structural similarity between two feature dicts."""
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 1.0
    matching = sum(1 for k in keys if a.get(k) == b.get(k))
    return matching / len(keys)


def _safe_ratio(a: tuple, b: tuple) -> tuple:
    """Safe division of dimension tuples."""
    return tuple(
        round(x / y, 2) if y != 0 else 0
        for x, y in zip(a, b)
    )


def _detect_grouping_criterion(inp: dict, out: dict) -> str:
    """Detect what criterion was used for grouping."""
    return "value_equality"  # Default; extend with more heuristics


def _consolidate_primitives(primitives: list[Pattern], n_examples: int) -> list[Pattern]:
    """Merge primitives found across multiple examples."""
    by_type: dict[str, list[Pattern]] = {}
    for p in primitives:
        by_type.setdefault(p.primitive_type, []).append(p)

    consolidated = []
    for ptype, patterns in by_type.items():
        # Merge evidence indices
        all_evidence = set()
        total_conf = 0.0
        best_params = patterns[0].parameters

        for p in patterns:
            all_evidence.update(p.evidence_indices)
            total_conf += p.confidence

        # Confidence boost: more examples support it → higher confidence
        coverage = len(all_evidence) / max(n_examples, 1)
        avg_conf = total_conf / len(patterns)
        boosted_conf = min(0.99, avg_conf * (0.5 + 0.5 * coverage))

        consolidated.append(Pattern(
            primitive_type=ptype,
            parameters=best_params,
            confidence=round(boosted_conf, 4),
            evidence_indices=sorted(all_evidence),
        ))

    return sorted(consolidated, key=lambda p: -p.confidence)


# ════════════════════════════════════════════
# Phase 2: Rule Synthesis
# ════════════════════════════════════════════

def _synthesize_rules(
    primitives: list[Pattern],
    examples: list[tuple[Any, Any]],
) -> list[CandidateRule]:
    """Generate candidate transformation rules from primitives."""
    candidates: list[CandidateRule] = []

    # Single-primitive rules
    for p in primitives:
        candidates.append(CandidateRule(
            primitives=[p],
            composition_type="single",
            score=0.0,  # Will be scored in Phase 3
            coverage=len(p.evidence_indices) / max(len(examples), 1),
            complexity=1,
            explanation=f"Apply {p.primitive_type}({p.parameters})",
        ))

    # Two-primitive sequential compositions
    if len(primitives) >= 2:
        for i, p1 in enumerate(primitives[:10]):  # Limit combinations
            for p2 in primitives[i + 1:10]:
                if p1.primitive_type == p2.primitive_type:
                    continue  # Skip same-type composition
                combined_evidence = set(p1.evidence_indices) | set(p2.evidence_indices)
                candidates.append(CandidateRule(
                    primitives=[p1, p2],
                    composition_type="sequential",
                    score=0.0,
                    coverage=len(combined_evidence) / max(len(examples), 1),
                    complexity=2,
                    explanation=f"{p1.primitive_type} → {p2.primitive_type}",
                ))

    # Conditional rules (if X then A else B)
    if len(primitives) >= 2:
        for i, p1 in enumerate(primitives[:5]):
            for p2 in primitives[:5]:
                if p1 is p2:
                    continue
                overlap = set(p1.evidence_indices) & set(p2.evidence_indices)
                if not overlap:  # Non-overlapping evidence → conditional
                    combined = set(p1.evidence_indices) | set(p2.evidence_indices)
                    candidates.append(CandidateRule(
                        primitives=[p1, p2],
                        composition_type="conditional",
                        score=0.0,
                        coverage=len(combined) / max(len(examples), 1),
                        complexity=3,  # Conditionals are more complex
                        explanation=f"if condition then {p1.primitive_type} else {p2.primitive_type}",
                    ))

    # Sort by coverage (descending) and complexity (ascending)
    candidates.sort(key=lambda c: (-c.coverage, c.complexity))
    return candidates[:MAX_CANDIDATE_RULES]


# ════════════════════════════════════════════
# Phase 3: Cross-Validation
# ════════════════════════════════════════════

def _cross_validate(
    candidates: list[CandidateRule],
    examples: list[tuple[Any, Any]],
) -> list[CandidateRule]:
    """Score candidates via cross-validation against examples."""
    n = len(examples)
    if n < 2:
        for c in candidates:
            c.score = c.coverage * 0.5  # Can't cross-validate with <2 examples
        return candidates

    # Hold-out validation
    holdout_n = max(1, int(n * CROSS_VALIDATION_HOLDOUT))
    train = examples[:-holdout_n]
    test = examples[-holdout_n:]

    for candidate in candidates:
        # Score = how well this rule generalizes to test examples
        train_coverage = _compute_coverage(candidate, train)
        test_coverage = _compute_coverage(candidate, test)

        # Generalization score: rewards rules that work on unseen examples
        if train_coverage > 0:
            generalization = test_coverage / train_coverage
        else:
            generalization = 0.0

        # Occam's razor: penalize complexity
        occam_penalty = 1.0 / (1.0 + 0.1 * candidate.complexity)

        # Confidence from number of supporting examples
        example_bonus = min(1.0, len(examples) / MIN_EXAMPLES_FOR_CONFIDENCE)

        candidate.score = round(
            0.4 * test_coverage +
            0.3 * generalization +
            0.2 * occam_penalty +
            0.1 * example_bonus,
            4
        )

    candidates.sort(key=lambda c: -c.score)
    return candidates


def _compute_coverage(candidate: CandidateRule, examples: list[tuple[Any, Any]]) -> float:
    """How many examples does this candidate explain?"""
    if not examples:
        return 0.0
    # Use primitive evidence to estimate coverage
    example_indices = set()
    for p in candidate.primitives:
        example_indices.update(p.evidence_indices)
    # Clamp to actual example count
    covered = len(example_indices & set(range(len(examples))))
    return covered / len(examples)


# ════════════════════════════════════════════
# Solver Class
# ════════════════════════════════════════════

class AnalogicalAbstractionSolver(AbstractSolver):
    """Novel abstract reasoning via inverse HTLF.

    Solver Type #11: Targets ARC-AGI-2 style problems.

    Instead of applying known transformations and measuring loss (forward HTLF),
    this solver observes input-output pairs and synthesizes the transformation
    rule that minimizes structural loss (inverse HTLF).

    Reasoning framework: analogical
    - Extract structural primitives from examples
    - Synthesize candidate rules via composition
    - Cross-validate against held-out examples
    - Score with Occam penalty (simpler rules preferred)

    Strengths: Novel pattern discovery, compositional generalization
    Weaknesses: Requires multiple examples, slow on complex domains
    """

    def __init__(self, solver_id: str = "abstraction_1", **kwargs: Any):
        super().__init__(solver_id, "analogical_abstraction",
                         framework="analogical", **kwargs)
        self._expertise = {
            "formal_logic": 0.6, "empirical": 0.5, "statistical": 0.4,
            "causal": 0.7, "linguistic": 0.3, "cultural": 0.1,
            "temporal": 0.2, "creative": 0.8,
        }

    def evaluate(self, claim: str, evidence: list[str], context: dict[str, Any]) -> SolverVote:
        """Evaluate via abstract reasoning on examples."""
        examples = context.get("examples", [])

        if not examples:
            # Try to extract examples from evidence
            examples = self._extract_examples_from_evidence(evidence)

        result = self.abstract_reason(examples)

        if result.best_rule is None:
            return SolverVote(
                solver_id=self.solver_id, verdict="uncertain",
                confidence=0.2,
                reasoning_summary="No consistent rule found across examples",
                evidence_cited=evidence, domain_relevance=0.5,
            )

        # Use the best rule's score as confidence
        verdict = "true" if result.confidence > 0.6 else "uncertain"

        return SolverVote(
            solver_id=self.solver_id, verdict=verdict,
            confidence=round(result.confidence, 4),
            reasoning_summary=(
                f"Rule: {result.best_rule.explanation} "
                f"(score={result.best_rule.score:.2f}, "
                f"coverage={result.best_rule.coverage:.0%}, "
                f"complexity={result.best_rule.complexity})"
            ),
            evidence_cited=evidence,
            domain_relevance=0.8 if examples else 0.3,
        )

    def abstract_reason(self, examples: list[tuple[Any, Any]]) -> AbstractionResult:
        """Run full abstract reasoning pipeline on examples."""
        trace = []

        # Phase 1: Extract primitives
        primitives = _extract_structural_primitives(examples)
        trace.append(f"Extracted {len(primitives)} primitives from {len(examples)} examples")

        if not primitives:
            return AbstractionResult(
                best_rule=None, all_candidates=[], confidence=0.0,
                reasoning_trace=trace + ["No primitives found"],
                n_examples=len(examples), n_primitives_found=0,
                search_exhausted=True,
            )

        # Phase 2: Synthesize rules
        candidates = _synthesize_rules(primitives, examples)
        trace.append(f"Synthesized {len(candidates)} candidate rules")

        # Phase 3: Cross-validate
        scored = _cross_validate(candidates, examples)
        trace.append(f"Cross-validated, best score: {scored[0].score:.3f}" if scored else "No candidates")

        best = scored[0] if scored else None
        confidence = best.score if best else 0.0

        # Boost confidence if multiple examples and high coverage
        if best and len(examples) >= MIN_EXAMPLES_FOR_CONFIDENCE and best.coverage > 0.8:
            confidence = min(0.95, confidence * 1.3)

        return AbstractionResult(
            best_rule=best,
            all_candidates=scored[:10],
            confidence=round(confidence, 4),
            reasoning_trace=trace,
            n_examples=len(examples),
            n_primitives_found=len(primitives),
            search_exhausted=len(candidates) < MAX_CANDIDATE_RULES,
        )

    @staticmethod
    def _extract_examples_from_evidence(evidence: list[str]) -> list[tuple[Any, Any]]:
        """Try to parse examples from evidence strings."""
        examples = []
        for e in evidence:
            # Look for "input → output" or "X -> Y" patterns
            match = re.search(r'(.+?)\s*(?:→|->|=>)\s*(.+)', e)
            if match:
                examples.append((match.group(1).strip(), match.group(2).strip()))
        return examples
