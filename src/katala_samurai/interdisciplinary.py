"""
Interdisciplinary Integration Layer — 学際的統合 + 仮説生成

ソルバー間のcross-solver推論を実現する:
1. ドメイン分類: 各ソルバー結果をドメインにマッピング
2. 交差分析: 異なるドメインのソルバー結果間のパターン検出
3. 矛盾検出: ドメイン間の矛盾を新しい研究課題として特定
4. 仮説生成: 交差パターンから検証可能な新仮説を自動生成

ソルバーの独立性（Wiles型設計原則）は保ちつつ、
出力の事後統合で学際的知見を引き出す。

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI), 2026-03-01
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Named Constants ──
MIN_SOLVERS_FOR_ANALYSIS = 3
AGREEMENT_THRESHOLD = 0.7
DISAGREEMENT_THRESHOLD = 0.3
CROSS_DOMAIN_SIGNIFICANCE = 0.6
HYPOTHESIS_MIN_CONFIDENCE = 0.3
MAX_HYPOTHESES = 10

# ── Domain Taxonomy ──
# Maps solver IDs/types to academic domains
SOLVER_DOMAIN_MAP = {
    # Mathematical/Formal
    "S01": "logic",
    "S02": "logic",
    "S03": "topology",
    "S04": "set_theory",
    "S05": "algebra",
    "S06": "number_theory",
    "S07": "geometry",
    "S08": "measure_theory",
    "S09": "category_theory",
    "S10": "graph_theory",
    # Physical/Causal
    "S11": "probability",
    "S12": "spacetime",
    "S13": "information_theory",
    "S14": "dynamical_systems",
    "S15": "statistical_mechanics",
    "S16": "optimal_transport",
    "S17": "spectral_theory",
    # Geometric/Structural
    "S18": "differential_geometry",
    "S19": "metric_geometry",
    "S20": "algebraic_topology",
    "S21": "tropical_geometry",
    "S22": "symplectic_geometry",
    # Statistical/Empirical
    "S23": "bayesian",
    "S24": "frequentist",
    "S25": "computational",
    "S26": "adversarial",
    "S27": "ensemble",
    "S28": "semantic",
    # Extended KS42c solvers
    "S29": "causal_inference",
    "S30": "temporal",
    "S31": "cultural",
    "S32": "linguistic",
    "S33": "meta",
}

# Academic domain clusters for cross-domain analysis
DOMAIN_CLUSTERS = {
    "formal": {"logic", "set_theory", "algebra", "number_theory", "category_theory"},
    "geometric": {"topology", "geometry", "differential_geometry", "metric_geometry",
                   "algebraic_topology", "tropical_geometry", "symplectic_geometry"},
    "physical": {"spacetime", "dynamical_systems", "statistical_mechanics", "spectral_theory"},
    "statistical": {"probability", "bayesian", "frequentist", "computational",
                     "information_theory", "optimal_transport"},
    "empirical": {"adversarial", "ensemble", "semantic", "causal_inference"},
    "contextual": {"temporal", "cultural", "linguistic", "meta"},
}

# Known cross-domain bridges (paradigm-crossing connections)
KNOWN_BRIDGES = [
    ("topology", "algebra", "代数的位相幾何学: 位相不変量を代数構造で記述"),
    ("probability", "geometry", "情報幾何学: 確率分布を多様体として扱う"),
    ("logic", "category_theory", "トポス理論: 論理をカテゴリーで基礎づける"),
    ("dynamical_systems", "topology", "力学系の位相的分類 (Morse理論)"),
    ("statistical_mechanics", "information_theory", "エントロピーの統計力学的解釈"),
    ("spacetime", "differential_geometry", "一般相対論: 重力=曲率"),
    ("bayesian", "information_theory", "ベイズ推論と情報量"),
    ("causal_inference", "graph_theory", "因果DAGによる因果推論"),
    ("computational", "algebra", "計算量理論と代数構造"),
    ("adversarial", "dynamical_systems", "敵対的堅牢性と力学系の安定性"),
]


@dataclass
class DomainResult:
    """A solver result mapped to its domain."""
    solver_id: str
    domain: str
    cluster: str
    passed: bool
    confidence: float
    raw_result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossDomainPattern:
    """Pattern detected across domains."""
    domain_a: str
    domain_b: str
    cluster_a: str
    cluster_b: str
    pattern_type: str  # agreement | disagreement | partial | novel_bridge
    strength: float
    description: str
    solvers_a: List[str] = field(default_factory=list)
    solvers_b: List[str] = field(default_factory=list)


@dataclass
class GeneratedHypothesis:
    """Automatically generated hypothesis from cross-domain analysis."""
    hypothesis_text: str
    source_pattern: str
    domains_involved: List[str] = field(default_factory=list)
    confidence: float = 0.3
    testability: float = 0.5  # How testable is this hypothesis
    novelty: float = 0.5     # How novel is this hypothesis
    priority: float = 0.5    # Combined priority score


@dataclass
class InterdisciplinaryResult:
    """Full interdisciplinary analysis output."""
    domain_results: List[DomainResult] = field(default_factory=list)
    cluster_agreement: Dict[str, float] = field(default_factory=dict)
    cross_patterns: List[CrossDomainPattern] = field(default_factory=list)
    hypotheses: List[GeneratedHypothesis] = field(default_factory=list)
    integration_score: float = 0.5
    analysis_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_coverage": len(set(d.domain for d in self.domain_results)),
            "cluster_coverage": len(set(d.cluster for d in self.domain_results)),
            "cluster_agreement": self.cluster_agreement,
            "cross_patterns": [
                {
                    "type": p.pattern_type,
                    "domains": f"{p.domain_a}×{p.domain_b}",
                    "clusters": f"{p.cluster_a}×{p.cluster_b}",
                    "strength": p.strength,
                    "description": p.description,
                }
                for p in self.cross_patterns
            ],
            "hypotheses": [
                {
                    "text": h.hypothesis_text,
                    "source": h.source_pattern,
                    "domains": h.domains_involved,
                    "confidence": h.confidence,
                    "testability": h.testability,
                    "novelty": h.novelty,
                    "priority": h.priority,
                }
                for h in self.hypotheses
            ],
            "hypothesis_count": len(self.hypotheses),
            "pattern_count": len(self.cross_patterns),
            "integration_score": self.integration_score,
            "analysis_time_ms": self.analysis_time_ms,
        }


class InterdisciplinaryEngine:
    """Cross-solver reasoning for interdisciplinary integration and hypothesis generation.

    Maintains solver independence (Wiles-type) while performing
    post-hoc integration of their outputs to find cross-domain patterns.
    """

    def __init__(self):
        self._bridge_cache: Dict[Tuple[str, str], str] = {}
        for d_a, d_b, desc in KNOWN_BRIDGES:
            self._bridge_cache[(d_a, d_b)] = desc
            self._bridge_cache[(d_b, d_a)] = desc

    def analyze(
        self,
        claim_text: str,
        solver_results: List[Dict[str, Any]],
        semantic_data: Optional[Dict] = None,
    ) -> InterdisciplinaryResult:
        """Perform interdisciplinary analysis on solver outputs.

        Args:
            claim_text: The original claim.
            solver_results: List of solver result dicts (must have solver_id, passed, confidence).
            semantic_data: Optional semantic extraction data.

        Returns:
            InterdisciplinaryResult with patterns and hypotheses.
        """
        start = time.time()

        # ── 1. Map solvers to domains ──
        domain_results = self._map_to_domains(solver_results)

        # ── 2. Cluster-level agreement ──
        cluster_agreement = self._compute_cluster_agreement(domain_results)

        # ── 3. Cross-domain pattern detection ──
        cross_patterns = self._detect_cross_patterns(domain_results, cluster_agreement)

        # ── 4. Hypothesis generation ──
        hypotheses = self._generate_hypotheses(
            claim_text, cross_patterns, domain_results, semantic_data
        )

        # ── 5. Integration score ──
        integration_score = self._compute_integration_score(
            domain_results, cross_patterns, hypotheses
        )

        elapsed = (time.time() - start) * 1000

        return InterdisciplinaryResult(
            domain_results=domain_results,
            cluster_agreement=cluster_agreement,
            cross_patterns=cross_patterns,
            hypotheses=hypotheses,
            integration_score=round(integration_score, 3),
            analysis_time_ms=round(elapsed, 1),
        )

    def _map_to_domains(self, solver_results: List[Dict]) -> List[DomainResult]:
        """Map each solver result to an academic domain."""
        results = []
        for i, sr in enumerate(solver_results):
            solver_id = sr.get("solver_id", f"S{i+1:02d}")
            domain = SOLVER_DOMAIN_MAP.get(solver_id, "general")

            # Find cluster
            cluster = "unknown"
            for cl_name, cl_domains in DOMAIN_CLUSTERS.items():
                if domain in cl_domains:
                    cluster = cl_name
                    break

            results.append(DomainResult(
                solver_id=solver_id,
                domain=domain,
                cluster=cluster,
                passed=sr.get("passed", False),
                confidence=sr.get("confidence", 0.5),
                raw_result=sr,
            ))

        return results

    def _compute_cluster_agreement(
        self, domain_results: List[DomainResult]
    ) -> Dict[str, float]:
        """Compute agreement rate within each cluster."""
        cluster_votes: Dict[str, List[bool]] = {}

        for dr in domain_results:
            if dr.cluster not in cluster_votes:
                cluster_votes[dr.cluster] = []
            cluster_votes[dr.cluster].append(dr.passed)

        agreement = {}
        for cluster, votes in cluster_votes.items():
            if votes:
                true_ratio = sum(votes) / len(votes)
                # Agreement = how far from 50/50 (0.5 = no agreement, 1.0 = unanimous)
                agreement[cluster] = round(abs(true_ratio - 0.5) * 2, 3)

        return agreement

    def _detect_cross_patterns(
        self,
        domain_results: List[DomainResult],
        cluster_agreement: Dict[str, float],
    ) -> List[CrossDomainPattern]:
        """Detect patterns across domain clusters."""
        patterns = []

        # Group by cluster
        cluster_groups: Dict[str, List[DomainResult]] = {}
        for dr in domain_results:
            if dr.cluster not in cluster_groups:
                cluster_groups[dr.cluster] = []
            cluster_groups[dr.cluster].append(dr)

        clusters = list(cluster_groups.keys())

        # Pairwise cluster comparison
        for i, cl_a in enumerate(clusters):
            for cl_b in clusters[i+1:]:
                group_a = cluster_groups[cl_a]
                group_b = cluster_groups[cl_b]

                if len(group_a) < 1 or len(group_b) < 1:
                    continue

                # Agreement rates
                rate_a = sum(d.passed for d in group_a) / len(group_a)
                rate_b = sum(d.passed for d in group_b) / len(group_b)

                diff = abs(rate_a - rate_b)

                # Check for known bridge
                domains_a = set(d.domain for d in group_a)
                domains_b = set(d.domain for d in group_b)
                bridge_desc = None
                for da in domains_a:
                    for db in domains_b:
                        if (da, db) in self._bridge_cache:
                            bridge_desc = self._bridge_cache[(da, db)]
                            break

                if diff < DISAGREEMENT_THRESHOLD:
                    # Strong agreement between clusters
                    pattern_type = "agreement"
                    strength = 1.0 - diff
                    desc = (f"{cl_a}クラスタと{cl_b}クラスタが強く合意 "
                            f"({rate_a:.0%} vs {rate_b:.0%})")
                elif diff > AGREEMENT_THRESHOLD:
                    # Strong disagreement
                    pattern_type = "disagreement"
                    strength = diff
                    desc = (f"{cl_a}と{cl_b}が対立 "
                            f"({rate_a:.0%} vs {rate_b:.0%}) — "
                            "異なる分析フレームワークが矛盾する結論を導出")
                else:
                    # Partial overlap
                    pattern_type = "partial"
                    strength = 0.5
                    desc = f"{cl_a}と{cl_b}は部分的に一致 ({rate_a:.0%} vs {rate_b:.0%})"

                if bridge_desc:
                    pattern_type = "novel_bridge"
                    desc += f" [既知の橋渡し: {bridge_desc}]"
                    strength = min(1.0, strength + 0.2)

                patterns.append(CrossDomainPattern(
                    domain_a=", ".join(sorted(domains_a)[:3]),
                    domain_b=", ".join(sorted(domains_b)[:3]),
                    cluster_a=cl_a,
                    cluster_b=cl_b,
                    pattern_type=pattern_type,
                    strength=round(strength, 3),
                    description=desc,
                    solvers_a=[d.solver_id for d in group_a],
                    solvers_b=[d.solver_id for d in group_b],
                ))

        # Sort by significance
        patterns.sort(key=lambda p: p.strength, reverse=True)
        return patterns

    def _generate_hypotheses(
        self,
        claim_text: str,
        patterns: List[CrossDomainPattern],
        domain_results: List[DomainResult],
        semantic_data: Optional[Dict],
    ) -> List[GeneratedHypothesis]:
        """Generate testable hypotheses from cross-domain patterns."""
        hypotheses = []

        for pattern in patterns:
            if len(hypotheses) >= MAX_HYPOTHESES:
                break

            if pattern.pattern_type == "disagreement":
                # Disagreement → "why do these domains disagree?"
                h = GeneratedHypothesis(
                    hypothesis_text=(
                        f"「{claim_text[:50]}」に対して{pattern.cluster_a}的分析と"
                        f"{pattern.cluster_b}的分析が対立する原因は、"
                        f"主張の前提が{pattern.cluster_a}では成立するが"
                        f"{pattern.cluster_b}では成立しない条件が存在する"
                    ),
                    source_pattern=f"cluster_disagreement:{pattern.cluster_a}×{pattern.cluster_b}",
                    domains_involved=[pattern.cluster_a, pattern.cluster_b],
                    confidence=round(pattern.strength * 0.6, 3),
                    testability=0.7,  # Testable by isolating assumptions
                    novelty=0.8,      # Cross-domain disagreement is interesting
                )
                h.priority = round(
                    h.confidence * 0.3 + h.testability * 0.3 + h.novelty * 0.4, 3
                )
                hypotheses.append(h)

            elif pattern.pattern_type == "novel_bridge":
                # Known bridge activated → deeper investigation hypothesis
                h = GeneratedHypothesis(
                    hypothesis_text=(
                        f"「{claim_text[:50]}」の検証において"
                        f"{pattern.cluster_a}と{pattern.cluster_b}の間の"
                        f"既知の理論的橋渡し構造が活性化した — "
                        "この構造が主張の検証に対して転移可能であることを示唆"
                    ),
                    source_pattern=f"bridge_activation:{pattern.cluster_a}×{pattern.cluster_b}",
                    domains_involved=[pattern.cluster_a, pattern.cluster_b],
                    confidence=round(pattern.strength * 0.7, 3),
                    testability=0.6,
                    novelty=0.5,  # Bridge is known, application might be novel
                )
                h.priority = round(
                    h.confidence * 0.3 + h.testability * 0.3 + h.novelty * 0.4, 3
                )
                hypotheses.append(h)

            elif pattern.pattern_type == "agreement" and pattern.strength > 0.8:
                # Strong cross-cluster agreement → robustness hypothesis
                h = GeneratedHypothesis(
                    hypothesis_text=(
                        f"「{claim_text[:50]}」は{pattern.cluster_a}と"
                        f"{pattern.cluster_b}の両フレームワークで整合する — "
                        "この頑健性は主張の構造的妥当性を示唆する"
                    ),
                    source_pattern=f"strong_agreement:{pattern.cluster_a}×{pattern.cluster_b}",
                    domains_involved=[pattern.cluster_a, pattern.cluster_b],
                    confidence=round(pattern.strength * 0.8, 3),
                    testability=0.4,  # Less testable (confirmation, not discrimination)
                    novelty=0.3,      # Agreement is less surprising
                )
                h.priority = round(
                    h.confidence * 0.3 + h.testability * 0.3 + h.novelty * 0.4, 3
                )
                hypotheses.append(h)

        # Semantic-driven hypotheses
        if semantic_data:
            entities = semantic_data.get("entities", [])
            domain = semantic_data.get("domain", "general")

            if entities and len(entities) >= 2:
                # Multi-entity → interaction hypothesis
                entity_names = [
                    e if isinstance(e, str) else e.get("name", "?")
                    for e in entities[:3]
                ]
                h = GeneratedHypothesis(
                    hypothesis_text=(
                        f"{' × '.join(entity_names)} の間の相互作用が"
                        f"「{claim_text[:30]}」の成立条件に影響する"
                    ),
                    source_pattern="entity_interaction",
                    domains_involved=[domain],
                    confidence=0.4,
                    testability=0.8,  # Interactions are empirically testable
                    novelty=0.6,
                )
                h.priority = round(
                    h.confidence * 0.3 + h.testability * 0.3 + h.novelty * 0.4, 3
                )
                hypotheses.append(h)

        # Sort by priority
        hypotheses.sort(key=lambda h: h.priority, reverse=True)
        return hypotheses[:MAX_HYPOTHESES]

    def _compute_integration_score(
        self,
        domain_results: List[DomainResult],
        patterns: List[CrossDomainPattern],
        hypotheses: List[GeneratedHypothesis],
    ) -> float:
        """Overall integration score.

        High score = rich cross-domain analysis with actionable hypotheses.
        """
        if not domain_results:
            return 0.0

        # Domain diversity (0-1)
        unique_clusters = len(set(d.cluster for d in domain_results))
        total_clusters = len(DOMAIN_CLUSTERS)
        diversity = min(1.0, unique_clusters / max(total_clusters * 0.5, 1))

        # Pattern richness (0-1)
        pattern_score = min(1.0, len(patterns) * 0.15)

        # Hypothesis quality (0-1)
        if hypotheses:
            avg_priority = sum(h.priority for h in hypotheses) / len(hypotheses)
            hyp_score = min(1.0, avg_priority * 1.5)
        else:
            hyp_score = 0.0

        return diversity * 0.3 + pattern_score * 0.3 + hyp_score * 0.4
