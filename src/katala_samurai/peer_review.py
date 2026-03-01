"""
Peer Review Engine — 査読レベルの批判生成

PhD研究者が行う査読を近似する:
1. 方法論批判: サンプルサイズ、統計手法、実験設計の妥当性
2. 論理構造批判: 前提→結論の飛躍、循環論法、未検証仮定の検出
3. 先行研究参照: 主張の新規性、既知の反例、引用不足の指摘
4. 再現性批判: 記述の曖昧さ、再現に必要な情報の欠落

論文DBは持たないが、ソルバー結果の統計的パターンと
LLMの知識を組み合わせて構造的批判を生成する。

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI), 2026-03-01
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── Named Constants ──
MIN_SOLVER_COUNT = 5
WEAK_AGREEMENT_THRESHOLD = 0.6
STRONG_AGREEMENT_THRESHOLD = 0.85
LOW_CONFIDENCE_THRESHOLD = 0.4
METHODOLOGY_WEIGHT = 0.30
LOGIC_WEIGHT = 0.30
NOVELTY_WEIGHT = 0.20
REPRODUCIBILITY_WEIGHT = 0.20
EVIDENCE_SUFFICIENCY_THRESHOLD = 3
QUANTIFICATION_KEYWORDS = [
    "数", "割合", "%", "倍", "比較", "統計", "有意", "p値", "相関",
    "number", "ratio", "percent", "significant", "correlation", "p-value",
    "sample", "サンプル", "N=", "n=", "標準偏差", "平均", "中央値",
]
HEDGE_WORDS = [
    "おそらく", "たぶん", "かもしれない", "可能性", "思われる",
    "perhaps", "maybe", "might", "possibly", "likely", "arguably",
    "suggest", "indicate", "appear", "seem",
]
CAUSAL_KEYWORDS = [
    "ため", "よって", "したがって", "結果", "原因", "because",
    "therefore", "consequently", "due to", "hence", "thus", "causes",
]
CIRCULAR_PATTERNS = [
    "定義上", "by definition", "自明", "trivially", "当然", "obviously",
]


@dataclass
class ReviewCritique:
    """Single critique point."""
    category: str  # methodology | logic | novelty | reproducibility
    severity: str  # critical | major | minor | suggestion
    description: str
    evidence: str = ""
    confidence: float = 0.5


@dataclass
class PeerReviewResult:
    """Full peer review output."""
    critiques: List[ReviewCritique] = field(default_factory=list)
    methodology_score: float = 0.5
    logic_score: float = 0.5
    novelty_score: float = 0.5
    reproducibility_score: float = 0.5
    overall_score: float = 0.5
    review_text: str = ""
    generation_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "critiques": [
                {
                    "category": c.category,
                    "severity": c.severity,
                    "description": c.description,
                    "evidence": c.evidence,
                    "confidence": c.confidence,
                }
                for c in self.critiques
            ],
            "methodology_score": self.methodology_score,
            "logic_score": self.logic_score,
            "novelty_score": self.novelty_score,
            "reproducibility_score": self.reproducibility_score,
            "overall_score": self.overall_score,
            "review_text": self.review_text,
            "generation_time_ms": self.generation_time_ms,
            "critique_count": len(self.critiques),
            "critical_count": sum(1 for c in self.critiques if c.severity == "critical"),
        }


class PeerReviewEngine:
    """Generate PhD-level peer review critiques from KS verification results.

    Uses solver results, semantic data, and structural analysis to
    produce specific, actionable critiques — not just confidence scores.
    """

    def __init__(self, llm_url: str = "http://localhost:11434"):
        self._llm_url = llm_url

    def review(
        self,
        claim_text: str,
        solver_results: Optional[List[Dict]] = None,
        semantic_data: Optional[Dict] = None,
        evidence: Optional[List[str]] = None,
        confidence: float = 0.5,
        verdict: str = "UNVERIFIED",
    ) -> PeerReviewResult:
        """Generate peer review of a claim and its verification.

        Args:
            claim_text: The original claim being reviewed.
            solver_results: List of solver output dicts from KS pipeline.
            semantic_data: Semantic extraction results.
            evidence: Supporting evidence list.
            confidence: KS confidence score.
            verdict: KS verdict string.

        Returns:
            PeerReviewResult with structured critiques.
        """
        start = time.time()
        critiques: List[ReviewCritique] = []
        solver_results = solver_results or []
        evidence = evidence or []

        # ── 1. Methodology Critique ──
        method_critiques = self._critique_methodology(
            claim_text, evidence, solver_results, confidence
        )
        critiques.extend(method_critiques)

        # ── 2. Logic Structure Critique ──
        logic_critiques = self._critique_logic(
            claim_text, semantic_data, solver_results
        )
        critiques.extend(logic_critiques)

        # ── 3. Novelty Assessment ──
        novelty_critiques = self._critique_novelty(
            claim_text, semantic_data
        )
        critiques.extend(novelty_critiques)

        # ── 4. Reproducibility Critique ──
        repro_critiques = self._critique_reproducibility(
            claim_text, evidence, solver_results
        )
        critiques.extend(repro_critiques)

        # ── Score Calculation ──
        method_score = self._category_score(
            [c for c in critiques if c.category == "methodology"]
        )
        logic_score = self._category_score(
            [c for c in critiques if c.category == "logic"]
        )
        novelty_score = self._category_score(
            [c for c in critiques if c.category == "novelty"]
        )
        repro_score = self._category_score(
            [c for c in critiques if c.category == "reproducibility"]
        )

        overall = (
            method_score * METHODOLOGY_WEIGHT
            + logic_score * LOGIC_WEIGHT
            + novelty_score * NOVELTY_WEIGHT
            + repro_score * REPRODUCIBILITY_WEIGHT
        )

        # Generate review text
        review_text = self._generate_review_text(
            claim_text, critiques, overall, verdict, confidence
        )

        elapsed = (time.time() - start) * 1000

        return PeerReviewResult(
            critiques=critiques,
            methodology_score=round(method_score, 3),
            logic_score=round(logic_score, 3),
            novelty_score=round(novelty_score, 3),
            reproducibility_score=round(repro_score, 3),
            overall_score=round(overall, 3),
            review_text=review_text,
            generation_time_ms=round(elapsed, 1),
        )

    # ── Methodology ──

    def _critique_methodology(
        self,
        claim_text: str,
        evidence: List[str],
        solver_results: List[Dict],
        confidence: float,
    ) -> List[ReviewCritique]:
        critiques = []

        # Check evidence sufficiency
        if len(evidence) < EVIDENCE_SUFFICIENCY_THRESHOLD:
            critiques.append(ReviewCritique(
                category="methodology",
                severity="major",
                description=f"エビデンス不足: {len(evidence)}件のみ提示。"
                    f"最低{EVIDENCE_SUFFICIENCY_THRESHOLD}件の独立した証拠源が必要。",
                evidence=f"提示されたエビデンス数: {len(evidence)}",
                confidence=0.8,
            ))

        # Check quantification
        has_quant = any(kw in claim_text for kw in QUANTIFICATION_KEYWORDS)
        has_numbers = any(c.isdigit() for c in claim_text)
        if not has_quant and not has_numbers:
            critiques.append(ReviewCritique(
                category="methodology",
                severity="major",
                description="定量的根拠の欠如: 主張に数値・統計が含まれていない。"
                    "効果量、サンプルサイズ、信頼区間などの定量化が必要。",
                evidence="主張テキストに定量的指標なし",
                confidence=0.7,
            ))

        # Solver disagreement analysis
        if solver_results:
            passed = sum(1 for r in solver_results if r.get("passed", False))
            total = len(solver_results)
            agreement = passed / total if total > 0 else 0

            if agreement < WEAK_AGREEMENT_THRESHOLD:
                critiques.append(ReviewCritique(
                    category="methodology",
                    severity="critical",
                    description=f"ソルバー間の合意が低い ({passed}/{total} = "
                        f"{agreement:.0%})。独立検証者間の一致率が{WEAK_AGREEMENT_THRESHOLD:.0%}未満は"
                        "結論の頑健性に疑問がある。",
                    evidence=f"passed={passed}, total={total}, agreement={agreement:.3f}",
                    confidence=0.85,
                ))
            elif agreement < STRONG_AGREEMENT_THRESHOLD:
                critiques.append(ReviewCritique(
                    category="methodology",
                    severity="minor",
                    description=f"ソルバー合意率 {agreement:.0%} は中程度。"
                        "一部のソルバーが反証パターンを検出している可能性がある。",
                    evidence=f"passed={passed}/{total}",
                    confidence=0.6,
                ))

        # Low confidence warning
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            critiques.append(ReviewCritique(
                category="methodology",
                severity="critical",
                description=f"検証信頼度が低い (conf={confidence:.3f})。"
                    "信頼区間の下限が有意水準を下回っている可能性。",
                evidence=f"confidence={confidence}",
                confidence=0.9,
            ))

        # Check for hedging in evidence
        hedge_count = sum(
            1 for e in evidence
            for hw in HEDGE_WORDS
            if hw in e
        )
        if hedge_count > 0 and evidence:
            ratio = hedge_count / len(evidence)
            if ratio > 0.3:
                critiques.append(ReviewCritique(
                    category="methodology",
                    severity="minor",
                    description=f"エビデンスに曖昧表現が多い ({hedge_count}件): "
                        "「おそらく」「可能性がある」等の断定を避ける表現は"
                        "根拠の強度を弱める。",
                    evidence=f"hedge_ratio={ratio:.2f}",
                    confidence=0.6,
                ))

        if not critiques:
            critiques.append(ReviewCritique(
                category="methodology",
                severity="suggestion",
                description="方法論的に明示的な問題は検出されなかった。"
                    "ただし、外部データベースとの照合は未実施。",
                confidence=0.4,
            ))

        return critiques

    # ── Logic ──

    def _critique_logic(
        self,
        claim_text: str,
        semantic_data: Optional[Dict],
        solver_results: List[Dict],
    ) -> List[ReviewCritique]:
        critiques = []

        # Check for causal claims without causal evidence
        has_causal = any(kw in claim_text for kw in CAUSAL_KEYWORDS)
        if has_causal:
            # Look for actual causal mechanism
            has_mechanism = False
            if semantic_data:
                relations = semantic_data.get("relations", [])
                has_mechanism = any(
                    r.get("type") in ("causal", "implies", "causes")
                    for r in relations
                ) if relations else False

            if not has_mechanism:
                critiques.append(ReviewCritique(
                    category="logic",
                    severity="major",
                    description="因果関係の主張があるが因果メカニズムが未提示。"
                        "相関と因果の混同の可能性。交絡変数の検討が必要。",
                    evidence="因果キーワード検出、因果関係の構造的記述なし",
                    confidence=0.75,
                ))

        # Check for circular reasoning
        for pattern in CIRCULAR_PATTERNS:
            if pattern in claim_text:
                critiques.append(ReviewCritique(
                    category="logic",
                    severity="critical",
                    description=f"循環論法の可能性: 「{pattern}」は"
                        "定義に基づく自明な主張を示唆。独立した証拠なしに"
                        "結論が前提に含まれている。",
                    evidence=f"detected_pattern='{pattern}'",
                    confidence=0.7,
                ))
                break

        # Proposition coverage analysis
        if semantic_data:
            props = semantic_data.get("propositions", [])
            entities = semantic_data.get("entities", [])

            if props and len(props) > 1:
                # Check if all propositions are verified by solvers
                if solver_results:
                    verified_fraction = sum(
                        1 for r in solver_results if r.get("passed", False)
                    ) / max(len(solver_results), 1)

                    if verified_fraction > 0.8 and len(props) <= 2:
                        critiques.append(ReviewCritique(
                            category="logic",
                            severity="minor",
                            description="主張が単純化されすぎている可能性。"
                                f"{len(props)}個の命題のみで複雑な主張を支えている。"
                                "暗黙の前提が見落とされていないか検討が必要。",
                            evidence=f"prop_count={len(props)}, entity_count={len(entities)}",
                            confidence=0.5,
                        ))

            if not entities:
                critiques.append(ReviewCritique(
                    category="logic",
                    severity="minor",
                    description="具体的なエンティティ（人物・場所・数値）が"
                        "抽出されなかった。主張が抽象的すぎて反証可能性が低い。",
                    evidence="entities=[]",
                    confidence=0.6,
                ))

        # Universal claim detection
        universal_markers = [
            "すべて", "全て", "必ず", "常に", "絶対", "あらゆる",
            "all", "every", "always", "never", "none", "no one",
        ]
        if any(m in claim_text for m in universal_markers):
            critiques.append(ReviewCritique(
                category="logic",
                severity="major",
                description="全称命題を含む主張。単一の反例で反証可能だが、"
                    "全称の証明には網羅的検証が必要。"
                    "存在量化（「〜の場合がある」）への緩和を検討。",
                evidence="universal_quantifier_detected",
                confidence=0.7,
            ))

        if not critiques:
            critiques.append(ReviewCritique(
                category="logic",
                severity="suggestion",
                description="論理構造に明示的な欠陥は検出されなかった。",
                confidence=0.4,
            ))

        return critiques

    # ── Novelty ──

    def _critique_novelty(
        self,
        claim_text: str,
        semantic_data: Optional[Dict],
    ) -> List[ReviewCritique]:
        critiques = []

        # Domain identification
        domain = "general"
        if semantic_data:
            domain = semantic_data.get("domain", "general")

        # Check for well-known claim patterns
        known_patterns = {
            "地球は太陽の周りを": ("astronomy", "既知の天文学的事実"),
            "水は100度で沸騰": ("physics", "基礎物理学の常識"),
            "E=mc": ("physics", "アインシュタインの質量-エネルギー等価"),
            "DNAは二重らせん": ("biology", "ワトソン-クリック構造"),
            "地球は平ら": ("pseudoscience", "反証済みの主張"),
        }

        for pattern, (pat_domain, description) in known_patterns.items():
            if pattern in claim_text:
                critiques.append(ReviewCritique(
                    category="novelty",
                    severity="minor",
                    description=f"既知の{pat_domain}的事実: {description}。"
                        "新規性はない。先行研究への言及として適切だが、"
                        "独自の貢献としては不十分。",
                    evidence=f"matched_pattern='{pattern}'",
                    confidence=0.85,
                ))
                break

        # Length-based novelty heuristic (longer = more specific = potentially novel)
        text_len = len(claim_text)
        if text_len < 20:
            critiques.append(ReviewCritique(
                category="novelty",
                severity="minor",
                description="主張が短すぎて新規性の評価が困難。"
                    "具体的な条件、対象、方法を含めることで評価可能になる。",
                evidence=f"claim_length={text_len}",
                confidence=0.5,
            ))

        # Cross-domain check
        if semantic_data:
            entities = semantic_data.get("entities", [])
            domain_count = len(set(
                e.get("domain", domain) for e in entities
                if isinstance(e, dict)
            )) if entities and isinstance(entities[0], dict) else 0

            if domain_count >= 2:
                critiques.append(ReviewCritique(
                    category="novelty",
                    severity="suggestion",
                    description=f"複数ドメイン ({domain_count}領域) にまたがる主張。"
                        "学際的な新規性の可能性がある。"
                        "ただし各ドメインの専門家による検証が必要。",
                    evidence=f"domain_count={domain_count}",
                    confidence=0.5,
                ))

        if not critiques:
            critiques.append(ReviewCritique(
                category="novelty",
                severity="suggestion",
                description="新規性の自動評価には限界がある。"
                    "論文DBとの照合による先行研究チェックが推奨される。",
                confidence=0.3,
            ))

        return critiques

    # ── Reproducibility ──

    def _critique_reproducibility(
        self,
        claim_text: str,
        evidence: List[str],
        solver_results: List[Dict],
    ) -> List[ReviewCritique]:
        critiques = []

        # Check for method description
        method_keywords = [
            "方法", "手順", "プロトコル", "実験", "調査", "測定",
            "method", "procedure", "protocol", "experiment", "measure",
            "実装", "アルゴリズム", "パイプライン", "implementation",
        ]
        has_method = any(kw in claim_text for kw in method_keywords)
        evidence_has_method = any(
            any(kw in e for kw in method_keywords)
            for e in evidence
        )

        if not has_method and not evidence_has_method:
            critiques.append(ReviewCritique(
                category="reproducibility",
                severity="major",
                description="方法・手順の記述が不足。"
                    "第三者が同一条件で検証を再現するための情報が必要。"
                    "具体的な実験手順、使用ツール、パラメータの明記を推奨。",
                evidence="method_keywords_not_found",
                confidence=0.65,
            ))

        # Solver reproducibility: check consistency
        if solver_results and len(solver_results) >= MIN_SOLVER_COUNT:
            confidences = [
                r.get("confidence", 0.5) for r in solver_results
                if isinstance(r.get("confidence"), (int, float))
            ]
            if confidences:
                mean_conf = sum(confidences) / len(confidences)
                variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
                std_dev = math.sqrt(variance) if variance > 0 else 0

                if std_dev > 0.2:
                    critiques.append(ReviewCritique(
                        category="reproducibility",
                        severity="major",
                        description=f"ソルバー信頼度のばらつきが大きい "
                            f"(σ={std_dev:.3f})。検証結果の安定性に問題。"
                            "異なる検証手法間での再現性が低い。",
                        evidence=f"mean={mean_conf:.3f}, std={std_dev:.3f}, n={len(confidences)}",
                        confidence=0.7,
                    ))

                # Check for bimodal distribution (solvers strongly disagree)
                above = sum(1 for c in confidences if c > mean_conf + std_dev)
                below = sum(1 for c in confidences if c < mean_conf - std_dev)
                if above > len(confidences) * 0.3 and below > len(confidences) * 0.3:
                    critiques.append(ReviewCritique(
                        category="reproducibility",
                        severity="critical",
                        description="ソルバー信頼度が二峰性分布を示している。"
                            "検証者が明確に2グループに分裂しており、"
                            "根本的な前提の相違がある可能性。",
                        evidence=f"above_1σ={above}, below_1σ={below}, total={len(confidences)}",
                        confidence=0.75,
                    ))

        if not critiques:
            critiques.append(ReviewCritique(
                category="reproducibility",
                severity="suggestion",
                description="再現性に関する明示的な問題は検出されなかった。"
                    "ただし、独立した追試による確認が推奨される。",
                confidence=0.4,
            ))

        return critiques

    # ── Scoring ──

    def _category_score(self, critiques: List[ReviewCritique]) -> float:
        """Calculate score for a critique category.

        Fewer/milder critiques = higher score. No critiques = 0.8 (not 1.0,
        because absence of detected problems ≠ absence of problems).
        """
        if not critiques:
            return 0.8

        # Only count real issues, not suggestions
        issues = [c for c in critiques if c.severity != "suggestion"]
        if not issues:
            return 0.75

        severity_penalty = {
            "critical": 0.30,
            "major": 0.15,
            "minor": 0.05,
        }

        total_penalty = sum(
            severity_penalty.get(c.severity, 0) * c.confidence
            for c in issues
        )

        return max(0.0, min(1.0, 1.0 - total_penalty))

    # ── Text Generation ──

    def _generate_review_text(
        self,
        claim_text: str,
        critiques: List[ReviewCritique],
        overall_score: float,
        verdict: str,
        confidence: float,
    ) -> str:
        """Generate human-readable review text."""
        lines = []
        lines.append(f"## Peer Review: 「{claim_text[:80]}」")
        lines.append(f"KS Verdict: {verdict} (conf={confidence:.3f})")
        lines.append("")

        # Sort by severity
        severity_order = {"critical": 0, "major": 1, "minor": 2, "suggestion": 3}
        sorted_critiques = sorted(
            critiques, key=lambda c: severity_order.get(c.severity, 4)
        )

        critical = [c for c in sorted_critiques if c.severity == "critical"]
        major = [c for c in sorted_critiques if c.severity == "major"]
        minor = [c for c in sorted_critiques if c.severity == "minor"]

        if critical:
            lines.append("### 🔴 Critical Issues")
            for c in critical:
                lines.append(f"- [{c.category}] {c.description}")
            lines.append("")

        if major:
            lines.append("### 🟡 Major Issues")
            for c in major:
                lines.append(f"- [{c.category}] {c.description}")
            lines.append("")

        if minor:
            lines.append("### 🔵 Minor Issues")
            for c in minor:
                lines.append(f"- [{c.category}] {c.description}")
            lines.append("")

        # Decision
        if overall_score >= 0.7:
            decision = "Accept with minor revisions"
        elif overall_score >= 0.5:
            decision = "Major revision required"
        elif overall_score >= 0.3:
            decision = "Reject and resubmit"
        else:
            decision = "Reject"

        lines.append(f"### Decision: {decision} (score={overall_score:.3f})")

        return "\n".join(lines)
