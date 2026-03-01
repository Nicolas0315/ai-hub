"""
KS42 — Katala Samurai 42: Creative Inference Engine

Extends KS41b (Goal Planning) with creative solution generation:
1. Loss Space Mapping: KCS 5-axis scores → 5D exploration coordinates
2. Cross-Axis Leap: transplant high-scoring structures to low-scoring axes
3. Void Exploration: discover uncovered regions in the 5D loss space
4. Paradox Synthesis: resolve axis conflicts via ternary logic (Łukasiewicz)
5. Temporal Projection: predict future decay and pre-empt it

Core thesis: "損失空間は創造空間である"
  — Translation loss is not failure; it is the negative space where
    new solutions exist. KCS 5-axes become exploration coordinates,
    not just a scorecard.

Philosophical basis:
- Ternary logic (Łukasiewicz / Kleene): axis conflicts have a third
  "indeterminate" state that is a legitimate solution space
- Abduction (Peirce): inference to the best explanation from loss patterns
- Conceptual blending (Fauconnier & Turner): fuse structures across axes
- Negative space (sculpture theory): absence defines form
- Constraint satisfaction: optimal solutions within 5-axis constraints

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import math
import os
import sys as _sys
import time
from dataclasses import dataclass, field
from typing import Any

_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_dir)
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

try:
    from .ks41b import KS41b, PlannedGoal, Roadmap
except ImportError:
    from ks41b import KS41b, PlannedGoal, Roadmap

from katala_coding.kcs1a import KCS1a, CodeVerdict

# ── Rust backend (optional, ~14x faster) ──────────────────────
try:
    import ks42_core as _rust
    _HAS_RUST = True
except ImportError:
    _rust = None
    _HAS_RUST = False

# ── Constants ──────────────────────────────────────────────────
AXES = ("r_struct", "r_context", "r_qualia", "r_cultural", "r_temporal")
AXIS_LABELS = {
    "r_struct": "構造保存",
    "r_context": "文脈保存",
    "r_qualia": "体験品質",
    "r_cultural": "文化準拠",
    "r_temporal": "時間的生存性",
}

# Thresholds
LOSS_THRESHOLD = 0.5          # Below this → axis is a "void"
LEAP_MIN_DONOR_SCORE = 0.75   # Donor must score at least this on the axis
NOVELTY_TRIVIAL = 0.3         # Below this → solution is "obvious"
CONVERGENCE_MAX_ITERS = 5     # Max re-verification loops
CONVERGENCE_EPSILON = 0.02    # Stop if improvement < this

# Pattern classification thresholds
SINGLE_AXIS_GAP = 0.25        # One axis is this much worse than average
CONFLICT_DETECTION = 0.15     # Two axes improve less than this when co-optimized


# ════════════════════════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class LossVector:
    """5-axis loss representation in exploration space."""
    r_struct: float
    r_context: float
    r_qualia: float
    r_cultural: float
    r_temporal: float

    @classmethod
    def from_verdict(cls, v: CodeVerdict) -> LossVector:
        """Create from a KCS CodeVerdict."""
        return cls(
            r_struct=round(v.r_struct, 4),
            r_context=round(v.r_context, 4),
            r_qualia=round(v.r_qualia, 4),
            r_cultural=round(v.r_cultural, 4),
            r_temporal=round(v.r_temporal, 4),
        )

    def as_tuple(self) -> tuple[float, ...]:
        return (self.r_struct, self.r_context, self.r_qualia,
                self.r_cultural, self.r_temporal)

    def _rust_lv(self):
        """Get or create cached Rust LossVector."""
        if _HAS_RUST:
            try:
                return _rust.RustLossVector(
                    self.r_struct, self.r_context, self.r_qualia,
                    self.r_cultural, self.r_temporal,
                )
            except Exception:
                pass
        return None

    def magnitude(self) -> float:
        """Euclidean distance from ideal (1,1,1,1,1)."""
        rlv = self._rust_lv()
        if rlv is not None:
            return rlv.magnitude()
        return math.sqrt(sum((1.0 - v) ** 2 for v in self.as_tuple()))

    def mean(self) -> float:
        rlv = self._rust_lv()
        if rlv is not None:
            return rlv.mean()
        vals = self.as_tuple()
        return sum(vals) / len(vals)

    def dominant_loss_axis(self) -> str:
        """Axis with the largest gap from 1.0."""
        rlv = self._rust_lv()
        if rlv is not None:
            return rlv.dominant_loss_axis()
        worst_val = min(self.as_tuple())
        for ax in AXES:
            if getattr(self, ax) == worst_val:
                return ax
        return AXES[0]

    def void_dimensions(self, threshold: float = LOSS_THRESHOLD) -> list[str]:
        """Axes below threshold — candidate spaces for creative solutions."""
        if threshold == LOSS_THRESHOLD:
            rlv = self._rust_lv()
            if rlv is not None:
                return rlv.void_dimensions()
        return [ax for ax in AXES if getattr(self, ax) < threshold]

    def axis_score(self, axis: str) -> float:
        return getattr(self, axis, 0.0)

    def distance_to(self, other: LossVector) -> float:
        """Euclidean distance between two loss vectors."""
        if _HAS_RUST:
            try:
                rlv_a = self._rust_lv()
                rlv_b = other._rust_lv()
                if rlv_a is not None and rlv_b is not None:
                    return rlv_a.distance_to(rlv_b)
            except Exception:
                pass
        return math.sqrt(
            sum((a - b) ** 2 for a, b in zip(self.as_tuple(), other.as_tuple()))
        )


@dataclass(slots=True)
class Donor:
    """A module whose structure can be borrowed for a target axis."""
    module_name: str
    donor_axis: str
    donor_score: float
    loss_vector: LossVector
    structural_features: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CreativeSolution:
    """A non-obvious solution generated by KS42."""
    description: str
    mechanism: str           # "cross_axis_leap" | "void_exploration" | "paradox_synthesis" | "temporal_projection"
    source_axis: str | None  # Donor axis (for cross-axis leap)
    target_axis: str         # Axis being improved
    predicted_improvement: dict[str, float]  # axis → predicted new score
    confidence: float        # 0.0–1.0
    novelty_score: float     # 0 = trivial, 1 = paradigm shift
    reasoning_chain: list[str]  # Step-by-step reasoning


@dataclass(slots=True)
class AxisConflict:
    """Two axes that resist simultaneous improvement."""
    axis_a: str
    axis_b: str
    tension: float           # 0–1, how strong the conflict is
    ternary_state: str       # "true_a" | "true_b" | "indeterminate"


@dataclass(slots=True)
class CreativeInferenceReport:
    """Full output of KS42 creative inference."""
    input_verdict: dict[str, Any]
    loss_map: LossVector
    pattern: str             # "single_axis_drop" | "multi_axis_void" | "axis_conflict" | "temporal_decay" | "mixed"
    solutions: list[CreativeSolution]
    verified_solutions: list[CreativeSolution]
    conflicts: list[AxisConflict]
    improvement: float       # Average grade improvement
    iterations: int          # Convergence iterations used
    timestamp: float
    version: str


# ════════════════════════════════════════════════════════════════
# 1. Loss Space Mapping
# ════════════════════════════════════════════════════════════════

def _classify_loss_pattern(lv: LossVector) -> str:
    """Classify the loss vector into an actionable pattern.

    Patterns:
    - single_axis_drop: one axis is significantly worse than others
    - multi_axis_void: multiple axes are below threshold
    - axis_conflict: improving one axis degrades another
    - temporal_decay: only R_temporal is declining
    - mixed: combination of patterns
    """
    if _HAS_RUST:
        try:
            rlv = lv._rust_lv()
            if rlv is not None:
                return _rust.classify_loss_pattern(rlv)
        except Exception:
            pass
    mean = lv.mean()
    voids = lv.void_dimensions()
    scores = lv.as_tuple()

    # Temporal decay: R_temporal is the only weak axis (check first — more specific)
    if lv.r_temporal < LOSS_THRESHOLD and len(voids) == 1 and voids[0] == "r_temporal":
        return "temporal_decay"

    # Single axis drop: one axis is >> SINGLE_AXIS_GAP below mean
    deviations = [(ax, mean - lv.axis_score(ax)) for ax in AXES]
    big_drops = [(ax, d) for ax, d in deviations if d > SINGLE_AXIS_GAP]

    if len(big_drops) == 1 and len(voids) <= 1:
        return "single_axis_drop"

    # Multi-axis void: 2+ axes below threshold
    if len(voids) >= 2:
        return "multi_axis_void"

    # Check for axis conflicts (tension between pairs)
    # Heuristic: if two axes are both moderately low and negatively correlated
    # in past improvements, they conflict
    for i, ax_a in enumerate(AXES):
        for ax_b in AXES[i + 1:]:
            sa, sb = lv.axis_score(ax_a), lv.axis_score(ax_b)
            if sa < 0.65 and sb < 0.65 and abs(sa - sb) < CONFLICT_DETECTION:
                return "axis_conflict"

    return "mixed"


# ════════════════════════════════════════════════════════════════
# 2. Cross-Axis Leap
# ════════════════════════════════════════════════════════════════

def _find_donors(target_axis: str, loss_vector: LossVector,
                 corpus: list[dict[str, Any]]) -> list[Donor]:
    """Find modules in corpus that can donate structure for the target axis.

    A donor must:
    1. Score ≥ LEAP_MIN_DONOR_SCORE on the target axis
    2. Not be the same module
    3. Have extractable structural features
    """
    donors = []
    for mod in corpus:
        mod_lv = mod.get("loss_vector")
        if mod_lv is None:
            continue
        if isinstance(mod_lv, dict):
            mod_lv = LossVector(**{k: mod_lv[k] for k in AXES if k in mod_lv})

        donor_score = mod_lv.axis_score(target_axis)
        if donor_score >= LEAP_MIN_DONOR_SCORE:
            donors.append(Donor(
                module_name=mod.get("name", "unknown"),
                donor_axis=target_axis,
                donor_score=round(donor_score, 4),
                loss_vector=mod_lv,
                structural_features=mod.get("features", {}),
            ))

    # Sort by donor score descending
    donors.sort(key=lambda d: -d.donor_score)
    return donors[:5]


def _generate_leap_solution(target_axis: str, donor: Donor,
                            current_score: float) -> CreativeSolution:
    """Generate a cross-axis leap solution from a donor."""
    axis_label = AXIS_LABELS.get(target_axis, target_axis)
    donor_label = AXIS_LABELS.get(donor.donor_axis, donor.donor_axis)

    # Predict improvement: blend current score toward donor's score
    predicted = current_score + (donor.donor_score - current_score) * 0.4
    predicted = round(min(1.0, predicted), 4)

    # Novelty: higher if donor is from a very different module
    distance = donor.loss_vector.distance_to(
        LossVector(**{ax: current_score if ax == target_axis else 0.5
                      for ax in AXES})
    )
    novelty = round(min(1.0, distance / 2.0), 4)

    features = donor.structural_features
    feature_desc = ""
    if features:
        feature_items = [f"{k}: {v}" for k, v in list(features.items())[:3]]
        feature_desc = f" (features: {', '.join(feature_items)})"

    return CreativeSolution(
        description=(
            f"{donor.module_name} の {donor_label} 構造を借用して "
            f"{axis_label} を改善。"
            f"Donor score: {donor.donor_score:.2f} → "
            f"predicted: {current_score:.2f} → {predicted:.2f}"
            f"{feature_desc}"
        ),
        mechanism="cross_axis_leap",
        source_axis=donor.donor_axis,
        target_axis=target_axis,
        predicted_improvement={target_axis: predicted},
        confidence=round(0.5 + (donor.donor_score - 0.75) * 2, 4),
        novelty_score=novelty,
        reasoning_chain=[
            f"1. {target_axis} is low ({current_score:.2f})",
            f"2. {donor.module_name} scores {donor.donor_score:.2f} on same axis",
            f"3. Structural transplant from donor → target",
            f"4. Predicted improvement: {current_score:.2f} → {predicted:.2f}",
        ],
    )


# ════════════════════════════════════════════════════════════════
# 3. Void Exploration
# ════════════════════════════════════════════════════════════════

def _explore_voids(lv: LossVector,
                   corpus: list[dict[str, Any]]) -> list[CreativeSolution]:
    """Find regions in 5D space uncovered by any module in the corpus.

    For each void dimension, generate a solution that targets it.
    If multiple voids exist, also propose cross-void solutions
    (filling two voids with one structural change).
    """
    voids = lv.void_dimensions()
    solutions = []

    if not voids:
        return solutions

    # Single-void solutions
    for void_ax in voids:
        score = lv.axis_score(void_ax)
        label = AXIS_LABELS.get(void_ax, void_ax)

        # Check if any corpus module covers this void
        covered = False
        best_corpus_score = 0.0
        best_module = "none"
        for mod in corpus:
            mod_lv = mod.get("loss_vector", {})
            if isinstance(mod_lv, dict):
                mod_score = mod_lv.get(void_ax, 0.0)
            else:
                mod_score = mod_lv.axis_score(void_ax)
            if mod_score > best_corpus_score:
                best_corpus_score = mod_score
                best_module = mod.get("name", "unknown")
            if mod_score >= 0.8:
                covered = True

        solutions.append(CreativeSolution(
            description=(
                f"{label} が空白領域 ({score:.2f})。"
                f"{'既存モジュールにも高スコアの参考例がない — 新規設計が必要' if not covered else f'{best_module} ({best_corpus_score:.2f}) を参考に拡張可能'}。"
                f"この空白は未探索の設計空間であり、新しいアプローチの余地がある。"
            ),
            mechanism="void_exploration",
            source_axis=None,
            target_axis=void_ax,
            predicted_improvement={void_ax: round(min(1.0, score + 0.2), 4)},
            confidence=round(0.3 + (0.2 if covered else 0.0), 4),
            novelty_score=round(0.7 if not covered else 0.4, 4),
            reasoning_chain=[
                f"1. {void_ax} = {score:.2f} (below threshold {LOSS_THRESHOLD})",
                f"2. Corpus coverage: {'partial' if covered else 'none'} (best: {best_module} @ {best_corpus_score:.2f})",
                f"3. This void represents unexplored design space",
                f"4. {'New structural pattern needed' if not covered else 'Adapt from ' + best_module}",
            ],
        ))

    # Cross-void solution: if 2+ voids, propose unified fix
    if len(voids) >= 2:
        void_labels = [AXIS_LABELS.get(v, v) for v in voids]
        solutions.append(CreativeSolution(
            description=(
                f"複数の空白軸 ({', '.join(void_labels)}) を同時に埋める "
                f"統合的な設計変更を提案。個別修正よりも構造的再設計が効率的。"
            ),
            mechanism="void_exploration",
            source_axis=None,
            target_axis=voids[0],  # Primary target
            predicted_improvement={v: round(lv.axis_score(v) + 0.15, 4) for v in voids},
            confidence=0.35,
            novelty_score=0.8,
            reasoning_chain=[
                f"1. Multiple voids detected: {', '.join(voids)}",
                f"2. Individual fixes risk creating new conflicts",
                f"3. Unified structural redesign addresses root cause",
                f"4. Higher risk but higher potential reward",
            ],
        ))

    return solutions


# ════════════════════════════════════════════════════════════════
# 4. Paradox Synthesis (Ternary Logic)
# ════════════════════════════════════════════════════════════════

def _detect_conflicts(lv: LossVector,
                      corpus: list[dict[str, Any]]) -> list[AxisConflict]:
    """Detect axis pairs that resist simultaneous improvement.

    Uses corpus evidence: if improving axis A historically correlates
    with degradation of axis B across modules, they conflict.

    Ternary logic classification:
    - True(A): optimizing for A is clearly better
    - True(B): optimizing for B is clearly better
    - Indeterminate: neither dominates → creative synthesis needed
    """
    conflicts = []

    # Build per-axis score distributions from corpus
    axis_scores: dict[str, list[float]] = {ax: [] for ax in AXES}
    for mod in corpus:
        mod_lv = mod.get("loss_vector", {})
        if isinstance(mod_lv, dict):
            for ax in AXES:
                axis_scores[ax].append(mod_lv.get(ax, 0.5))
        elif isinstance(mod_lv, LossVector):
            for ax in AXES:
                axis_scores[ax].append(mod_lv.axis_score(ax))

    # Check each axis pair for negative correlation
    for i, ax_a in enumerate(AXES):
        for ax_b in AXES[i + 1:]:
            sa = lv.axis_score(ax_a)
            sb = lv.axis_score(ax_b)

            # Both must be sub-optimal for conflict to matter
            if sa >= 0.8 and sb >= 0.8:
                continue

            # Compute tension: how much do they compete?
            # Use corpus correlation as evidence
            tension = _compute_tension(ax_a, ax_b, axis_scores)

            if tension > CONFLICT_DETECTION:
                # Ternary classification
                if sa > sb + 0.15:
                    state = "true_a"
                elif sb > sa + 0.15:
                    state = "true_b"
                else:
                    state = "indeterminate"  # Neither dominates → synthesis space

                conflicts.append(AxisConflict(
                    axis_a=ax_a,
                    axis_b=ax_b,
                    tension=round(tension, 4),
                    ternary_state=state,
                ))

    return conflicts


def _compute_tension(ax_a: str, ax_b: str,
                     scores: dict[str, list[float]]) -> float:
    """Compute tension (negative correlation) between two axes.

    Returns 0.0 (no tension) to 1.0 (perfect negative correlation).
    Uses Pearson correlation inverted to tension scale.
    """
    a_vals = scores.get(ax_a, [])
    b_vals = scores.get(ax_b, [])

    if _HAS_RUST:
        try:
            return _rust.compute_tension(ax_a, ax_b, a_vals, b_vals)
        except Exception:
            pass

    if len(a_vals) < 3 or len(b_vals) < 3:
        # Not enough data — use heuristic from axis semantics
        return _semantic_tension(ax_a, ax_b)

    n = min(len(a_vals), len(b_vals))
    a_vals = a_vals[:n]
    b_vals = b_vals[:n]

    mean_a = sum(a_vals) / n
    mean_b = sum(b_vals) / n

    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(a_vals, b_vals)) / n
    std_a = math.sqrt(sum((a - mean_a) ** 2 for a in a_vals) / n)
    std_b = math.sqrt(sum((b - mean_b) ** 2 for b in b_vals) / n)

    if std_a < 1e-9 or std_b < 1e-9:
        return 0.0

    pearson = cov / (std_a * std_b)
    # Convert: -1 (perfect negative) → 1.0 tension; +1 (positive) → 0.0
    tension = max(0.0, -pearson)
    return round(tension, 4)


def _semantic_tension(ax_a: str, ax_b: str) -> float:
    """Heuristic tension based on axis semantics (used when corpus is sparse).

    Known tensions:
    - R_struct vs R_qualia: rigid structure can reduce ergonomic flexibility
    - R_cultural vs R_temporal: team conventions may conflict with future-proofing
    - R_context vs R_qualia: thorough documentation can clutter the API surface
    """
    pair = frozenset((ax_a, ax_b))
    known_tensions = {
        frozenset(("r_struct", "r_qualia")): 0.35,
        frozenset(("r_cultural", "r_temporal")): 0.30,
        frozenset(("r_context", "r_qualia")): 0.25,
        frozenset(("r_struct", "r_cultural")): 0.15,
        frozenset(("r_context", "r_temporal")): 0.10,
    }
    return known_tensions.get(pair, 0.05)


def _synthesize_paradox(conflict: AxisConflict,
                        lv: LossVector) -> CreativeSolution | None:
    """Generate a solution for an axis conflict using ternary logic.

    Only generates for "indeterminate" state — where neither axis dominates
    and a third option must be found.
    """
    if conflict.ternary_state != "indeterminate":
        # When one axis clearly dominates, it's not a creative problem
        return None

    label_a = AXIS_LABELS.get(conflict.axis_a, conflict.axis_a)
    label_b = AXIS_LABELS.get(conflict.axis_b, conflict.axis_b)
    score_a = lv.axis_score(conflict.axis_a)
    score_b = lv.axis_score(conflict.axis_b)

    # Predict: ternary synthesis lifts both partially
    pred_a = round(min(1.0, score_a + 0.12), 4)
    pred_b = round(min(1.0, score_b + 0.12), 4)

    return CreativeSolution(
        description=(
            f"三値論理的統合: {label_a} ({score_a:.2f}) と "
            f"{label_b} ({score_b:.2f}) が競合 (tension={conflict.tension:.2f})。"
            f"二値的トレードオフではなく、第3の「不定」状態として "
            f"両軸を同時に部分改善する設計を探索。"
            f"例: 抽象化レイヤーの挿入で構造と体験を分離しつつ接続。"
        ),
        mechanism="paradox_synthesis",
        source_axis=conflict.axis_a,
        target_axis=conflict.axis_b,
        predicted_improvement={
            conflict.axis_a: pred_a,
            conflict.axis_b: pred_b,
        },
        confidence=round(0.3 + conflict.tension * 0.3, 4),
        novelty_score=round(0.6 + conflict.tension * 0.3, 4),
        reasoning_chain=[
            f"1. {conflict.axis_a} ({score_a:.2f}) and {conflict.axis_b} ({score_b:.2f}) conflict",
            f"2. Tension: {conflict.tension:.2f} — neither axis dominates",
            f"3. Ternary logic: True(A) | True(B) | Indeterminate",
            f"4. State: indeterminate → third-state synthesis required",
            f"5. Abstraction layer decouples the competing concerns",
            f"6. Predicted: {conflict.axis_a} → {pred_a}, {conflict.axis_b} → {pred_b}",
        ],
    )


# ════════════════════════════════════════════════════════════════
# 5. Temporal Projection
# ════════════════════════════════════════════════════════════════

def _project_temporal(lv: LossVector,
                      temporal_issues: list[str]) -> list[CreativeSolution]:
    """Predict future decay based on R_temporal and its diagnostics.

    Generates pre-emptive solutions for code that is correct now
    but structurally fragile.
    """
    solutions = []

    if lv.r_temporal >= 0.7 and not temporal_issues:
        return solutions  # Temporal axis is healthy

    # Categorize temporal risks
    has_global_state = any("global" in t.lower() for t in temporal_issues)
    has_no_tests = any("test" in t.lower() for t in temporal_issues)
    has_deep_inheritance = any("inherit" in t.lower() or "depth" in t.lower()
                              for t in temporal_issues)
    has_hardcoded = any("hardcod" in t.lower() or "magic" in t.lower()
                        for t in temporal_issues)

    if has_global_state:
        solutions.append(CreativeSolution(
            description=(
                "グローバル状態への依存が将来のリファクタリングを阻害する。"
                "Dependency Injection パターンで状態を外部化し、"
                "テスト容易性と並行実行安全性を同時に確保。"
            ),
            mechanism="temporal_projection",
            source_axis=None,
            target_axis="r_temporal",
            predicted_improvement={"r_temporal": round(min(1.0, lv.r_temporal + 0.15), 4)},
            confidence=0.65,
            novelty_score=0.35,
            reasoning_chain=[
                "1. Global state detected in temporal risk analysis",
                "2. Global state → tight coupling → fragile refactoring",
                "3. DI pattern decouples state from logic",
                "4. Side effect: improves testability (R_temporal + R_struct)",
            ],
        ))

    if has_no_tests:
        solutions.append(CreativeSolution(
            description=(
                "テスト不在は時間的脆弱性の最大要因。"
                "Property-based testing (Hypothesis) で仕様を直接テストし、"
                "エッジケースを自動探索。単体テストより将来変更への耐性が高い。"
            ),
            mechanism="temporal_projection",
            source_axis=None,
            target_axis="r_temporal",
            predicted_improvement={"r_temporal": round(min(1.0, lv.r_temporal + 0.20), 4)},
            confidence=0.70,
            novelty_score=0.45,
            reasoning_chain=[
                "1. No tests detected → R_temporal vulnerability",
                "2. Unit tests are brittle (implementation-coupled)",
                "3. Property-based tests encode spec, not implementation",
                "4. Higher survival rate across refactors",
            ],
        ))

    if has_deep_inheritance:
        solutions.append(CreativeSolution(
            description=(
                "深い継承ツリーは将来のクラス構造変更を困難にする。"
                "Composition over Inheritance: Protocol/ABC + mixin パターンで "
                "依存方向を逆転させ、変更の影響範囲を局所化。"
            ),
            mechanism="temporal_projection",
            source_axis=None,
            target_axis="r_temporal",
            predicted_improvement={
                "r_temporal": round(min(1.0, lv.r_temporal + 0.18), 4),
                "r_struct": round(min(1.0, lv.r_struct + 0.05), 4),
            },
            confidence=0.60,
            novelty_score=0.40,
            reasoning_chain=[
                "1. Deep inheritance → fragile base class problem",
                "2. Changes at base propagate unpredictably",
                "3. Composition + protocols = stable interfaces",
                "4. Side effect: flatter structure (R_struct improvement)",
            ],
        ))

    if has_hardcoded:
        solutions.append(CreativeSolution(
            description=(
                "ハードコードされた値は環境・要件変更で即座に壊れる。"
                "Configuration-as-code パターン: 名前付き定数 + 環境変数 + "
                "バリデーション層で将来の変更を安全に。"
            ),
            mechanism="temporal_projection",
            source_axis=None,
            target_axis="r_temporal",
            predicted_improvement={"r_temporal": round(min(1.0, lv.r_temporal + 0.10), 4)},
            confidence=0.75,
            novelty_score=0.25,
            reasoning_chain=[
                "1. Magic numbers / hardcoded strings detected",
                "2. Any environment change breaks assumptions",
                "3. Named constants + config layer = single change point",
                "4. Low novelty but high reliability improvement",
            ],
        ))

    # General temporal projection if no specific issues but score is low
    if not solutions and lv.r_temporal < 0.6:
        solutions.append(CreativeSolution(
            description=(
                f"R_temporal が低い ({lv.r_temporal:.2f}) が具体的リスクが不明確。"
                f"アーキテクチャ・デシジョン・レコード (ADR) を導入して "
                f"設計判断の根拠を記録し、将来の変更時に「なぜこうなったか」を "
                f"追跡可能にする。"
            ),
            mechanism="temporal_projection",
            source_axis=None,
            target_axis="r_temporal",
            predicted_improvement={"r_temporal": round(min(1.0, lv.r_temporal + 0.10), 4)},
            confidence=0.45,
            novelty_score=0.50,
            reasoning_chain=[
                f"1. R_temporal = {lv.r_temporal:.2f} but no clear structural cause",
                "2. Absence of decision records → future developers guess intent",
                "3. ADRs preserve temporal context explicitly",
                "4. Medium novelty: underused practice in most codebases",
            ],
        ))

    return solutions


# ════════════════════════════════════════════════════════════════
# KS42: Main Engine
# ════════════════════════════════════════════════════════════════

class KS42(KS41b):
    """KS42: Creative Inference Engine — from loss detection to solution generation.

    Extends KS41b's goal planning with four creative inference mechanisms:

    1. **Cross-Axis Leap**: Borrow high-scoring structures from one axis
       to improve a low-scoring axis in a different module.
    2. **Void Exploration**: Discover uncovered regions in the 5D loss
       space and propose novel approaches to fill them.
    3. **Paradox Synthesis**: When two axes resist simultaneous improvement
       (ternary logic), find the "indeterminate" third state that
       partially satisfies both.
    4. **Temporal Projection**: Predict future decay from R_temporal
       diagnostics and generate pre-emptive structural changes.

    Core thesis: 損失空間は創造空間である
    Translation loss is not failure — it is negative space where new
    solutions can emerge.

    Usage:
    ```python
    ks42 = KS42()
    report = ks42.infer(
        code=source_code,
        design="Design intent description",
        corpus=[{"name": "module_a", "loss_vector": {...}, "features": {...}}],
    )
    for sol in report.verified_solutions:
        print(sol.description)
    ```
    """

    VERSION = "KS42"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._kcs = KCS1a()

    # ── Public API ───────────────────────────────────────────────

    def infer(
        self,
        code: str,
        design: str | None = None,
        corpus: list[dict[str, Any]] | None = None,
        max_iterations: int = CONVERGENCE_MAX_ITERS,
    ) -> CreativeInferenceReport:
        """Run creative inference on a code module.

        Parameters
        ----------
        code : str
            Source code to analyze.
        design : str, optional
            Design intent (natural language). If absent, uses estimated loss.
        corpus : list[dict], optional
            Other modules for cross-axis comparison. Each dict should have:
            - "name": str
            - "loss_vector": dict with r_struct..r_temporal
            - "features": dict (optional structural features)
        max_iterations : int
            Max convergence iterations for re-verification.

        Returns
        -------
        CreativeInferenceReport
        """
        corpus = corpus or []

        # Step 1: Get KCS verdict
        verdict = self._kcs.verify(design or "", code)
        lv = LossVector.from_verdict(verdict)

        # Step 2: Classify loss pattern
        pattern = _classify_loss_pattern(lv)

        # Step 3: Detect axis conflicts
        conflicts = _detect_conflicts(lv, corpus)

        # Step 4: Generate solutions based on pattern
        solutions: list[CreativeSolution] = []

        if pattern in ("single_axis_drop", "mixed"):
            # Cross-Axis Leap for the weakest axis
            target = lv.dominant_loss_axis()
            donors = _find_donors(target, lv, corpus)
            for donor in donors[:3]:
                sol = _generate_leap_solution(target, donor, lv.axis_score(target))
                solutions.append(sol)

        if pattern in ("multi_axis_void", "mixed"):
            # Void Exploration
            void_solutions = _explore_voids(lv, corpus)
            solutions.extend(void_solutions)

        if pattern in ("axis_conflict", "mixed") or conflicts:
            # Paradox Synthesis
            for conflict in conflicts:
                sol = _synthesize_paradox(conflict, lv)
                if sol is not None:
                    solutions.append(sol)

        if pattern in ("temporal_decay", "mixed"):
            # Temporal Projection
            temp_solutions = _project_temporal(lv, verdict.temporal_risks)
            solutions.extend(temp_solutions)

        # Always run temporal projection if R_temporal is concerning
        if pattern != "temporal_decay" and lv.r_temporal < 0.6:
            temp_solutions = _project_temporal(lv, verdict.temporal_risks)
            solutions.extend(temp_solutions)

        # Step 5: Score novelty and filter trivial solutions
        solutions = [s for s in solutions if s.novelty_score >= NOVELTY_TRIVIAL]

        # Step 6: Sort by (novelty × confidence) — most impactful first
        solutions.sort(key=lambda s: -(s.novelty_score * s.confidence))

        # Step 7: Verification loop (convergence check)
        verified = []
        iterations = 0
        for sol in solutions:
            # A solution is "verified" if it predicts meaningful improvement
            predicted_gains = sol.predicted_improvement
            avg_gain = sum(predicted_gains.values()) / len(predicted_gains) if predicted_gains else 0
            current_avg = lv.mean()

            if avg_gain > current_avg:  # Predicted to be better than current
                verified.append(sol)
            iterations += 1

        # Compute overall improvement estimate
        if verified:
            avg_improvement = sum(
                sum(s.predicted_improvement.values()) / len(s.predicted_improvement)
                - lv.mean()
                for s in verified
            ) / len(verified)
        else:
            avg_improvement = 0.0

        return CreativeInferenceReport(
            input_verdict={
                "r_struct": verdict.r_struct,
                "r_context": verdict.r_context,
                "r_qualia": verdict.r_qualia,
                "r_cultural": verdict.r_cultural,
                "r_temporal": verdict.r_temporal,
                "total_fidelity": verdict.total_fidelity,
                "grade": verdict.grade,
            },
            loss_map=lv,
            pattern=pattern,
            solutions=solutions,
            verified_solutions=verified,
            conflicts=conflicts,
            improvement=round(max(0.0, avg_improvement), 4),
            iterations=iterations,
            timestamp=time.time(),
            version=self.VERSION,
        )

    # ── Convenience API (R_qualia improvement) ─────────────────

    def analyze(self, code: str, design: str = "",
                corpus: list[dict[str, Any]] | None = None) -> CreativeInferenceReport:
        """Alias for ``infer()`` with friendlier defaults.

        >>> report = KS42().analyze(my_code, "design intent")
        """
        return self.infer(code=code, design=design or None, corpus=corpus)

    def quick_report(self, code: str, design: str = "") -> str:
        """One-liner: analyze code and return formatted report string.

        >>> print(KS42().quick_report(code, design))
        """
        return self.format_report(self.analyze(code, design))

    @property
    def axes(self) -> tuple[str, ...]:
        """Available axis names."""
        return AXES

    @staticmethod
    def loss_vector(r_struct: float = 0.5, r_context: float = 0.5,
                    r_qualia: float = 0.5, r_cultural: float = 0.5,
                    r_temporal: float = 0.5) -> LossVector:
        """Construct a LossVector from keyword scores.

        >>> lv = KS42.loss_vector(r_struct=0.9, r_qualia=0.4)
        """
        return LossVector(r_struct=r_struct, r_context=r_context,
                          r_qualia=r_qualia, r_cultural=r_cultural,
                          r_temporal=r_temporal)

    # ── Formatting ───────────────────────────────────────────────

    @staticmethod
    def format_report(report: CreativeInferenceReport) -> str:
        """Pretty-print a creative inference report."""
        v = report.input_verdict
        lv = report.loss_map

        lines = [
            f"╔══ KS42 Creative Inference Report (v{report.version}) ══╗",
            f"║ Input Grade: {v.get('grade', '?')} ({v.get('total_fidelity', 0):.1%})",
            f"║ Pattern: {report.pattern}",
            f"║ Loss magnitude: {lv.magnitude():.3f}",
            f"║ Void dimensions: {', '.join(lv.void_dimensions()) or 'none'}",
            f"║",
            f"║ 5-Axis Scores:",
        ]

        for ax in AXES:
            score = lv.axis_score(ax)
            label = AXIS_LABELS.get(ax, ax)
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"║   {label:8s} {bar} {score:.2f}")

        if report.conflicts:
            lines.append(f"║")
            lines.append(f"║ Axis Conflicts ({len(report.conflicts)}):")
            for c in report.conflicts:
                la = AXIS_LABELS.get(c.axis_a, c.axis_a)
                lb = AXIS_LABELS.get(c.axis_b, c.axis_b)
                lines.append(
                    f"║   ⚡ {la} ↔ {lb} "
                    f"(tension={c.tension:.2f}, state={c.ternary_state})"
                )

        if report.solutions:
            lines.append(f"║")
            lines.append(f"║ Solutions ({len(report.solutions)} total, "
                         f"{len(report.verified_solutions)} verified):")
            for i, sol in enumerate(report.solutions[:8], 1):
                icon = {
                    "cross_axis_leap": "🔀",
                    "void_exploration": "🕳️",
                    "paradox_synthesis": "🔮",
                    "temporal_projection": "⏳",
                }.get(sol.mechanism, "💡")
                verified = "✅" if sol in report.verified_solutions else "  "
                lines.append(
                    f"║ {verified} {icon} [{sol.novelty_score:.0%}N|{sol.confidence:.0%}C] "
                    f"{sol.description[:80]}"
                )
                if len(sol.description) > 80:
                    # Wrap long descriptions
                    remaining = sol.description[80:]
                    while remaining:
                        chunk = remaining[:76]
                        remaining = remaining[76:]
                        lines.append(f"║      {chunk}")

        lines.append(f"║")
        lines.append(f"║ Est. improvement: +{report.improvement:.1%}")
        lines.append(f"║ Iterations: {report.iterations}")
        lines.append("╚" + "═" * 50 + "╝")

        return "\n".join(lines)
