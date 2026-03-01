"""
Tacit Knowledge Approximation — 暗黙知の数値的近似

PhDの暗黙知（直感、嗅覚、経験則）を近似する:
1. ドメイン経験プロファイル: 過去の検証履歴から「経験」を蓄積
2. パターン認識: 高頻度パターンの自動検出と重み付け
3. 異常検知: 「なんか変」をフォーマライズ — 統計的外れ値検出
4. 暗黙の事前分布: ドメインごとの base rate を学習

暗黙知の本質は「言語化できない判断」なので完全な近似は不可能。
可能な範囲でのheuristic approximation。

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI), 2026-03-01
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Named Constants ──
MIN_OBSERVATIONS_FOR_PATTERN = 5
ANOMALY_Z_THRESHOLD = 2.0
DECAY_HALF_LIFE = 50  # episodes until weight halves
BASE_RATE_PRIOR_STRENGTH = 5  # pseudo-observations for prior
PATTERN_SIGNIFICANCE_THRESHOLD = 0.6
MAX_PATTERNS = 100


@dataclass
class DomainProfile:
    """Accumulated 'experience' in a domain."""
    domain: str
    observation_count: int = 0
    verified_count: int = 0
    unverified_count: int = 0
    exploring_count: int = 0
    avg_confidence: float = 0.5
    confidence_history: List[float] = field(default_factory=list)
    common_patterns: Dict[str, int] = field(default_factory=dict)

    @property
    def base_rate(self) -> float:
        """Prior probability of VERIFIED in this domain."""
        if self.observation_count == 0:
            return 0.5
        return self.verified_count / self.observation_count

    @property
    def experience_level(self) -> str:
        if self.observation_count >= 100:
            return "expert"
        elif self.observation_count >= 30:
            return "intermediate"
        elif self.observation_count >= 10:
            return "novice"
        else:
            return "unfamiliar"


@dataclass
class AnomalySignal:
    """Something that 'feels wrong' — statistical anomaly."""
    signal_type: str  # confidence_outlier | verdict_unusual | pattern_break
    severity: float
    description: str
    expected_value: float = 0.0
    actual_value: float = 0.0
    z_score: float = 0.0


@dataclass
class TacitInsight:
    """An insight derived from tacit knowledge patterns."""
    insight_text: str
    basis: str  # pattern | anomaly | base_rate | cross_domain
    confidence: float = 0.5
    domain: str = "general"


@dataclass
class TacitKnowledgeResult:
    """Full tacit knowledge analysis."""
    domain: str = "general"
    experience_level: str = "unfamiliar"
    base_rate: float = 0.5
    anomalies: List[AnomalySignal] = field(default_factory=list)
    insights: List[TacitInsight] = field(default_factory=list)
    gut_feeling: float = 0.5  # Heuristic "intuition" score
    gut_feeling_basis: str = ""
    adjustment: float = 0.0  # Suggested confidence adjustment
    analysis_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "experience_level": self.experience_level,
            "base_rate": self.base_rate,
            "anomalies": [
                {
                    "type": a.signal_type,
                    "severity": a.severity,
                    "description": a.description,
                    "z_score": a.z_score,
                }
                for a in self.anomalies
            ],
            "insights": [
                {
                    "text": i.insight_text,
                    "basis": i.basis,
                    "confidence": i.confidence,
                    "domain": i.domain,
                }
                for i in self.insights
            ],
            "gut_feeling": self.gut_feeling,
            "gut_feeling_basis": self.gut_feeling_basis,
            "adjustment": self.adjustment,
            "anomaly_count": len(self.anomalies),
            "insight_count": len(self.insights),
            "analysis_time_ms": self.analysis_time_ms,
        }


class TacitKnowledgeEngine:
    """Approximate PhD-level tacit knowledge through pattern accumulation.

    Learns from verification history to build domain profiles,
    detect anomalies, and generate heuristic insights.
    """

    def __init__(self):
        self.profiles: Dict[str, DomainProfile] = {}
        self._global_history: List[Dict] = []
        self._pattern_cache: Dict[str, float] = {}

    def analyze(
        self,
        claim_text: str,
        domain: str = "general",
        confidence: float = 0.5,
        verdict: str = "UNVERIFIED",
        solver_results: Optional[List[Dict]] = None,
        semantic_data: Optional[Dict] = None,
    ) -> TacitKnowledgeResult:
        """Apply tacit knowledge to assess a verification result.

        Args:
            claim_text: The claim being verified.
            domain: Detected domain.
            confidence: KS confidence.
            verdict: KS verdict.
            solver_results: Solver outputs.
            semantic_data: Semantic extraction.

        Returns:
            TacitKnowledgeResult with gut feeling, anomalies, insights.
        """
        start = time.time()
        solver_results = solver_results or []

        # Get or create domain profile
        if domain not in self.profiles:
            self.profiles[domain] = DomainProfile(domain=domain)
        profile = self.profiles[domain]

        # ── 1. Anomaly Detection ──
        anomalies = self._detect_anomalies(
            confidence, verdict, profile, solver_results
        )

        # ── 2. Pattern-Based Insights ──
        insights = self._generate_insights(
            claim_text, domain, confidence, verdict,
            profile, semantic_data
        )

        # ── 3. Gut Feeling (heuristic intuition) ──
        gut, gut_basis = self._compute_gut_feeling(
            confidence, verdict, profile, anomalies, solver_results
        )

        # ── 4. Confidence Adjustment ──
        adjustment = self._compute_adjustment(
            confidence, profile.base_rate, gut, anomalies
        )

        # ── 5. Update Profile (learn from this observation) ──
        self._update_profile(profile, claim_text, confidence, verdict)

        elapsed = (time.time() - start) * 1000

        return TacitKnowledgeResult(
            domain=domain,
            experience_level=profile.experience_level,
            base_rate=round(profile.base_rate, 3),
            anomalies=anomalies,
            insights=insights,
            gut_feeling=round(gut, 3),
            gut_feeling_basis=gut_basis,
            adjustment=round(adjustment, 4),
            analysis_time_ms=round(elapsed, 1),
        )

    def _detect_anomalies(
        self,
        confidence: float,
        verdict: str,
        profile: DomainProfile,
        solver_results: List[Dict],
    ) -> List[AnomalySignal]:
        anomalies = []

        # Confidence vs historical distribution
        if profile.confidence_history and len(profile.confidence_history) >= MIN_OBSERVATIONS_FOR_PATTERN:
            hist = profile.confidence_history
            mean = sum(hist) / len(hist)
            variance = sum((x - mean) ** 2 for x in hist) / len(hist)
            std = math.sqrt(variance) if variance > 0 else 0.01

            z = (confidence - mean) / std if std > 0 else 0
            if abs(z) > ANOMALY_Z_THRESHOLD:
                direction = "高い" if z > 0 else "低い"
                anomalies.append(AnomalySignal(
                    signal_type="confidence_outlier",
                    severity=min(1.0, abs(z) / 4.0),
                    description=(
                        f"このドメインの過去{len(hist)}件の平均 {mean:.3f} に対し "
                        f"今回 {confidence:.3f} は統計的に有意に{direction} "
                        f"(z={z:.2f}, σ={std:.3f})"
                    ),
                    expected_value=mean,
                    actual_value=confidence,
                    z_score=round(z, 2),
                ))

        # Verdict vs base rate
        if profile.observation_count >= MIN_OBSERVATIONS_FOR_PATTERN:
            expected_verified_rate = profile.base_rate
            if verdict == "VERIFIED" and expected_verified_rate < 0.2:
                anomalies.append(AnomalySignal(
                    signal_type="verdict_unusual",
                    severity=0.7,
                    description=(
                        f"このドメインでVERIFIED率は{expected_verified_rate:.0%}だが "
                        "今回VERIFIEDと判定された — 稀な判定"
                    ),
                    expected_value=expected_verified_rate,
                    actual_value=1.0,
                ))
            elif verdict == "UNVERIFIED" and expected_verified_rate > 0.8:
                anomalies.append(AnomalySignal(
                    signal_type="verdict_unusual",
                    severity=0.5,
                    description=(
                        f"このドメインでVERIFIED率は{expected_verified_rate:.0%}だが "
                        "今回UNVERIFIEDと判定された — 稀な否定"
                    ),
                    expected_value=expected_verified_rate,
                    actual_value=0.0,
                ))

        # Solver consensus anomaly
        if solver_results:
            confs = [
                r.get("confidence", 0.5) for r in solver_results
                if isinstance(r.get("confidence"), (int, float))
            ]
            if confs and len(confs) >= 5:
                mean_c = sum(confs) / len(confs)
                var_c = sum((x - mean_c) ** 2 for x in confs) / len(confs)
                # Nearly zero variance = suspicious (all identical → likely default)
                if var_c < 0.001 and len(confs) > 10:
                    anomalies.append(AnomalySignal(
                        signal_type="pattern_break",
                        severity=0.6,
                        description=(
                            f"ソルバー信頼度の分散が極端に小さい (var={var_c:.6f})。"
                            "全ソルバーがほぼ同一値を返しており、"
                            "入力の弁別に失敗している可能性"
                        ),
                        expected_value=0.01,  # Minimum expected variance
                        actual_value=var_c,
                    ))

        return anomalies

    def _generate_insights(
        self,
        claim_text: str,
        domain: str,
        confidence: float,
        verdict: str,
        profile: DomainProfile,
        semantic_data: Optional[Dict],
    ) -> List[TacitInsight]:
        insights = []

        # Base rate insight
        if profile.observation_count >= MIN_OBSERVATIONS_FOR_PATTERN:
            br = profile.base_rate
            insights.append(TacitInsight(
                insight_text=(
                    f"{domain}ドメインの事前確率: "
                    f"VERIFIED={br:.0%} (過去{profile.observation_count}件の経験則)"
                ),
                basis="base_rate",
                confidence=min(0.9, profile.observation_count / 100),
                domain=domain,
            ))

        # Pattern-based insight from claim text features
        text_len = len(claim_text)
        if text_len < 20 and profile.observation_count > 0:
            insights.append(TacitInsight(
                insight_text="短い主張は一般に検証精度が低い（情報量不足）",
                basis="pattern",
                confidence=0.6,
                domain=domain,
            ))

        # Semantic complexity insight
        if semantic_data:
            prop_count = semantic_data.get("prop_count", 0)
            if prop_count > 5:
                insights.append(TacitInsight(
                    insight_text=(
                        f"命題数 {prop_count} は高複雑度。"
                        "複合的主張は部分的に正しく部分的に誤りの可能性が高い"
                    ),
                    basis="pattern",
                    confidence=0.5,
                    domain=domain,
                ))

        # Domain-specific heuristics
        domain_heuristics = {
            "physics": "物理学の主張は数値検証が可能 — 定量的証拠を要求すべき",
            "logic": "論理学の主張は形式的証明が可能 — ソルバー結果を信頼",
            "biology": "生物学の主張は統計的有意性が重要 — サンプルサイズに注目",
            "general": "汎用ドメイン — ドメイン固有の判断基準が未利用",
        }
        if domain in domain_heuristics:
            insights.append(TacitInsight(
                insight_text=domain_heuristics[domain],
                basis="pattern",
                confidence=0.4,
                domain=domain,
            ))

        return insights

    def _compute_gut_feeling(
        self,
        confidence: float,
        verdict: str,
        profile: DomainProfile,
        anomalies: List[AnomalySignal],
        solver_results: List[Dict],
    ) -> Tuple[float, str]:
        """Compute heuristic 'gut feeling' score.

        Combines base rate, anomaly signals, and solver patterns
        into a single intuition score.

        Returns (score, basis_description).
        """
        components = []
        basis_parts = []

        # Component 1: Base rate (experience)
        if profile.observation_count >= MIN_OBSERVATIONS_FOR_PATTERN:
            br_weight = min(0.3, profile.observation_count / 200)
            components.append((profile.base_rate, br_weight))
            basis_parts.append(f"base_rate={profile.base_rate:.2f}")
        else:
            components.append((0.5, 0.1))  # Uninformative prior
            basis_parts.append("no_prior")

        # Component 2: Current confidence (calibrated)
        components.append((confidence, 0.3))
        basis_parts.append(f"ks_conf={confidence:.3f}")

        # Component 3: Anomaly penalty
        if anomalies:
            anomaly_penalty = sum(a.severity for a in anomalies) / len(anomalies)
            components.append((1.0 - anomaly_penalty, 0.2))
            basis_parts.append(f"anomaly_penalty={anomaly_penalty:.2f}")
        else:
            components.append((0.7, 0.1))  # No anomaly = slightly positive
            basis_parts.append("no_anomaly")

        # Component 4: Solver agreement pattern
        if solver_results:
            passed = sum(1 for r in solver_results if r.get("passed", False))
            total = len(solver_results)
            solver_ratio = passed / total if total > 0 else 0.5
            components.append((solver_ratio, 0.2))
            basis_parts.append(f"solver={passed}/{total}")

        # Weighted average
        total_weight = sum(w for _, w in components)
        if total_weight > 0:
            gut = sum(v * w for v, w in components) / total_weight
        else:
            gut = 0.5

        return (max(0.0, min(1.0, gut)), " + ".join(basis_parts))

    def _compute_adjustment(
        self,
        confidence: float,
        base_rate: float,
        gut_feeling: float,
        anomalies: List[AnomalySignal],
    ) -> float:
        """Compute suggested confidence adjustment.

        Positive = increase confidence, negative = decrease.
        """
        # Bayesian shrinkage toward base rate
        shrinkage = (base_rate - confidence) * 0.1

        # Anomaly-driven adjustment
        if anomalies:
            total_severity = sum(a.severity for a in anomalies)
            anomaly_adj = -total_severity * 0.05
        else:
            anomaly_adj = 0.0

        # Gut feeling adjustment
        gut_adj = (gut_feeling - confidence) * 0.05

        return shrinkage + anomaly_adj + gut_adj

    def _update_profile(
        self,
        profile: DomainProfile,
        claim_text: str,
        confidence: float,
        verdict: str,
    ):
        """Update domain profile with new observation."""
        profile.observation_count += 1
        if verdict == "VERIFIED":
            profile.verified_count += 1
        elif verdict == "UNVERIFIED":
            profile.unverified_count += 1
        else:
            profile.exploring_count += 1

        profile.confidence_history.append(confidence)
        # Keep bounded
        if len(profile.confidence_history) > 200:
            profile.confidence_history = profile.confidence_history[-200:]

        # Update running average
        n = profile.observation_count
        profile.avg_confidence = (
            profile.avg_confidence * (n - 1) + confidence
        ) / n

        # Track text patterns (simple bigrams)
        words = claim_text.split()[:10]
        for i in range(len(words) - 1):
            bigram = f"{words[i]}_{words[i+1]}"
            profile.common_patterns[bigram] = (
                profile.common_patterns.get(bigram, 0) + 1
            )
            # Prune if too many
            if len(profile.common_patterns) > MAX_PATTERNS:
                # Keep top patterns
                sorted_p = sorted(
                    profile.common_patterns.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                profile.common_patterns = dict(sorted_p[:MAX_PATTERNS // 2])

    def get_profile_summary(self) -> Dict[str, Any]:
        """Summary of all domain profiles."""
        return {
            domain: {
                "observations": p.observation_count,
                "base_rate": round(p.base_rate, 3),
                "experience_level": p.experience_level,
                "avg_confidence": round(p.avg_confidence, 3),
            }
            for domain, p in self.profiles.items()
        }
