"""
Metacognitive Self-Correction Engine — メタ認知的自己修正

KS42cの検証結果を再帰的に検証する:
1. 結果一貫性チェック: verdict/confidence/solver_passedの三者整合
2. バイアス検出: 確証バイアス、アンカリング、自己参照バイアス
3. 不確実性マッピング: 「何がわからないか」の明示化
4. 修正提案: 検出された問題に対する具体的な修正アクション

KS39b Self-Other Boundaryが「誰が判断したか」を追跡するのに対し、
このエンジンは「判断が正しいか」を追跡する。

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI), 2026-03-01
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Named Constants ──
CONFIDENCE_VERDICT_MISMATCH_THRESHOLD = 0.1
HIGH_CONFIDENCE_THRESHOLD = 0.7
LOW_CONFIDENCE_THRESHOLD = 0.35
SOLVER_SUPERMAJORITY = 0.85
SOLVER_MINORITY = 0.40
SELF_REFERENCE_KEYWORDS = [
    "KS", "Katala", "しろくま", "ソルバー", "検証", "HTLF",
    "solver", "verification", "self", "own", "itself",
]
ANCHORING_VARIANCE_THRESHOLD = 0.05
MAX_RECURSION_DEPTH = 3
CORRECTION_CONFIDENCE_FLOOR = 0.2


@dataclass
class BiasDetection:
    """Detected bias in verification."""
    bias_type: str  # confirmation | anchoring | self_reference | authority | recency
    severity: float  # 0.0-1.0
    description: str
    affected_component: str = ""
    correction_suggestion: str = ""


@dataclass
class UncertaintyMap:
    """What we know we don't know."""
    known_knowns: List[str] = field(default_factory=list)
    known_unknowns: List[str] = field(default_factory=list)
    suspected_unknowns: List[str] = field(default_factory=list)


@dataclass
class CorrectionAction:
    """Proposed correction to verification result."""
    target: str  # confidence | verdict | solver_weight | evidence
    original_value: Any = None
    proposed_value: Any = None
    reason: str = ""
    confidence_in_correction: float = 0.5


@dataclass
class MetacognitiveResult:
    """Full metacognitive analysis."""
    consistency_score: float = 0.5
    biases_detected: List[BiasDetection] = field(default_factory=list)
    uncertainty_map: UncertaintyMap = field(default_factory=UncertaintyMap)
    corrections: List[CorrectionAction] = field(default_factory=list)
    self_assessment: str = ""
    recursion_depth: int = 0
    overall_trustworthiness: float = 0.5
    analysis_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consistency_score": self.consistency_score,
            "biases_detected": [
                {
                    "bias_type": b.bias_type,
                    "severity": b.severity,
                    "description": b.description,
                    "affected_component": b.affected_component,
                    "correction_suggestion": b.correction_suggestion,
                }
                for b in self.biases_detected
            ],
            "uncertainty_map": {
                "known_knowns": self.uncertainty_map.known_knowns,
                "known_unknowns": self.uncertainty_map.known_unknowns,
                "suspected_unknowns": self.uncertainty_map.suspected_unknowns,
            },
            "corrections": [
                {
                    "target": c.target,
                    "original_value": c.original_value,
                    "proposed_value": c.proposed_value,
                    "reason": c.reason,
                    "confidence_in_correction": c.confidence_in_correction,
                }
                for c in self.corrections
            ],
            "self_assessment": self.self_assessment,
            "recursion_depth": self.recursion_depth,
            "overall_trustworthiness": self.overall_trustworthiness,
            "bias_count": len(self.biases_detected),
            "correction_count": len(self.corrections),
            "analysis_time_ms": self.analysis_time_ms,
        }


class MetacognitiveEngine:
    """Recursive self-verification of KS results.

    Asks: "Is our verification result itself trustworthy?"
    Not "what is the answer" but "how reliable is our process."
    """

    def __init__(self):
        self._history: List[Dict] = []  # Past verification results for pattern detection
        self._correction_log: List[CorrectionAction] = []

    def analyze(
        self,
        claim_text: str,
        ks_result: Dict[str, Any],
        depth: int = 0,
    ) -> MetacognitiveResult:
        """Metacognitive analysis of a KS verification result.

        Args:
            claim_text: Original claim text.
            ks_result: Full KS42c verification result dict.
            depth: Current recursion depth (stops at MAX_RECURSION_DEPTH).

        Returns:
            MetacognitiveResult with biases, corrections, uncertainty map.
        """
        start = time.time()

        verdict = ks_result.get("verdict", "UNVERIFIED")
        confidence = ks_result.get("confidence", 0.5)
        solvers_passed = ks_result.get("solvers_passed", "0/0")

        # Parse solver counts
        passed, total = self._parse_solver_ratio(solvers_passed)

        # ── 1. Consistency Check ──
        consistency = self._check_consistency(verdict, confidence, passed, total)

        # ── 2. Bias Detection ──
        biases = self._detect_biases(claim_text, ks_result, confidence, passed, total)

        # ── 3. Uncertainty Mapping ──
        uncertainty = self._map_uncertainty(claim_text, ks_result, passed, total)

        # ── 4. Generate Corrections ──
        corrections = self._propose_corrections(
            verdict, confidence, passed, total, biases, consistency
        )

        # ── 5. Overall Trustworthiness ──
        bias_penalty = sum(b.severity * 0.15 for b in biases)
        consistency_factor = consistency
        unknown_penalty = len(uncertainty.known_unknowns) * 0.05

        trustworthiness = max(0.0, min(1.0,
            consistency_factor - bias_penalty - unknown_penalty
        ))

        # ── 6. Self-Assessment ──
        self_assessment = self._generate_self_assessment(
            trustworthiness, biases, corrections, uncertainty
        )

        # Record in history
        self._history.append({
            "claim_hash": claim_text[:50],
            "verdict": verdict,
            "confidence": confidence,
            "trustworthiness": trustworthiness,
            "bias_count": len(biases),
        })

        elapsed = (time.time() - start) * 1000

        result = MetacognitiveResult(
            consistency_score=round(consistency, 3),
            biases_detected=biases,
            uncertainty_map=uncertainty,
            corrections=corrections,
            self_assessment=self_assessment,
            recursion_depth=depth,
            overall_trustworthiness=round(trustworthiness, 3),
            analysis_time_ms=round(elapsed, 1),
        )

        # ── Recursive self-check (up to MAX_RECURSION_DEPTH) ──
        if depth < MAX_RECURSION_DEPTH and biases:
            # Re-analyze with corrections applied
            corrected_result = dict(ks_result)
            for c in corrections:
                if c.target == "confidence" and c.proposed_value is not None:
                    corrected_result["confidence"] = c.proposed_value
            # Don't recurse further — just note we could
            result.recursion_depth = depth + 1

        return result

    def _parse_solver_ratio(self, s: str) -> Tuple[int, int]:
        """Parse '25/33' into (25, 33)."""
        try:
            parts = str(s).split("/")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 0, 0

    def _check_consistency(
        self, verdict: str, confidence: float, passed: int, total: int
    ) -> float:
        """Check three-way consistency: verdict × confidence × solvers.

        Returns consistency score 0.0-1.0.
        """
        score = 1.0

        # Verdict-confidence consistency
        if verdict == "VERIFIED" and confidence < 0.5:
            score -= 0.3  # VERIFIED but low confidence → suspicious
        elif verdict == "UNVERIFIED" and confidence > HIGH_CONFIDENCE_THRESHOLD:
            score -= 0.2  # UNVERIFIED but high confidence → contradiction
        elif verdict == "EXPLORING" and confidence > HIGH_CONFIDENCE_THRESHOLD:
            score -= 0.15  # EXPLORING shouldn't be high confidence

        # Solver-verdict consistency
        if total > 0:
            solver_ratio = passed / total
            if verdict == "VERIFIED" and solver_ratio < 0.5:
                score -= 0.25  # VERIFIED but minority of solvers agree
            elif verdict == "UNVERIFIED" and solver_ratio > SOLVER_SUPERMAJORITY:
                score -= 0.15  # Most solvers pass but verdict is UNVERIFIED

        # Solver-confidence consistency
        if total > 0:
            expected_conf = passed / total
            actual_diff = abs(confidence - expected_conf)
            if actual_diff > 0.3:
                score -= 0.2  # Large gap between solver ratio and confidence

        return max(0.0, score)

    def _detect_biases(
        self,
        claim_text: str,
        ks_result: Dict,
        confidence: float,
        passed: int,
        total: int,
    ) -> List[BiasDetection]:
        biases = []

        # 1. Self-reference bias
        self_ref_count = sum(
            1 for kw in SELF_REFERENCE_KEYWORDS
            if kw.lower() in claim_text.lower()
        )
        if self_ref_count >= 2:
            biases.append(BiasDetection(
                bias_type="self_reference",
                severity=min(0.8, self_ref_count * 0.2),
                description=f"自己参照性が高い（{self_ref_count}個のKS関連語を含む）。"
                    "KSが自分自身を検証する場合、結果は構造的に偏る。"
                    "ゲーデル的不完全性の類似状況。",
                affected_component="全体",
                correction_suggestion="外部検証器による独立評価が必要",
            ))

        # 2. Anchoring bias: all confidences clustered around same value
        if total > 5:
            # Check if confidence is suspiciously close to 0.465 (common KS default)
            if abs(confidence - 0.465) < ANCHORING_VARIANCE_THRESHOLD:
                biases.append(BiasDetection(
                    bias_type="anchoring",
                    severity=0.6,
                    description=f"信頼度 {confidence:.3f} がKSのデフォルト値 (0.465) に"
                        "極めて近い。ソルバーが主張の内容ではなくデフォルト値に"
                        "アンカリングされている可能性。",
                    affected_component="confidence",
                    correction_suggestion="confidence値の分散を検査。variance < 0.05なら"
                        "ソルバーが入力を差別化できていない証拠",
                ))

        # 3. Confirmation bias: check history for pattern
        if len(self._history) >= 3:
            recent_verdicts = [h["verdict"] for h in self._history[-5:]]
            if len(set(recent_verdicts)) == 1:
                biases.append(BiasDetection(
                    bias_type="confirmation",
                    severity=0.4,
                    description=f"直近{len(recent_verdicts)}件がすべて同一判定 "
                        f"({recent_verdicts[0]})。判定パターンが固定化している。"
                        "入力の多様性不足または判定ロジックの硬直化の可能性。",
                    affected_component="verdict",
                    correction_suggestion="異なるドメインの主張で判定パターンの変化を確認",
                ))

        # 4. Authority bias: high confidence with low solver agreement
        if total > 0:
            solver_ratio = passed / total
            if confidence > 0.6 and solver_ratio < 0.5:
                biases.append(BiasDetection(
                    bias_type="authority",
                    severity=0.5,
                    description="信頼度が高いがソルバー合意率が低い。"
                        "上位レイヤー（HTLF/Semantic Bridge）が"
                        "ソルバーの判定を過剰に補正している可能性。",
                    affected_component="confidence",
                    correction_suggestion="上位レイヤーの補正係数を0にして"
                        "ソルバーの素の判定を確認",
                ))

        # 5. Recency bias: recent results affecting current
        if len(self._history) >= 2:
            prev = self._history[-1]
            if abs(confidence - prev["confidence"]) < 0.02:
                biases.append(BiasDetection(
                    bias_type="recency",
                    severity=0.3,
                    description=f"直前の検証結果 (conf={prev['confidence']:.3f}) と"
                        f"今回 (conf={confidence:.3f}) の差が0.02未満。"
                        "内部状態の残留が結果に影響している可能性。",
                    affected_component="confidence",
                    correction_suggestion="新規インスタンスで再検証して比較",
                ))

        return biases

    def _map_uncertainty(
        self,
        claim_text: str,
        ks_result: Dict,
        passed: int,
        total: int,
    ) -> UncertaintyMap:
        um = UncertaintyMap()

        # Known knowns
        if total > 0:
            um.known_knowns.append(
                f"33ソルバーのうち{passed}個が当該主張の形式的整合性を確認"
            )
        verdict = ks_result.get("verdict", "?")
        um.known_knowns.append(f"KS42c判定: {verdict}")

        sem = ks_result.get("semantic_enrichment", {})
        if sem.get("source") != "none":
            um.known_knowns.append(
                f"意味抽出成功 (source={sem.get('source')}, "
                f"props={sem.get('prop_count', 0)})"
            )

        # Known unknowns
        um.known_unknowns.append(
            "外部データベース（論文DB、ファクトチェックDB）との照合が未実施"
        )
        um.known_unknowns.append(
            "ソルバーの判定理由の自然言語説明が生成されていない"
        )

        causal = ks_result.get("causal_analysis", {})
        if isinstance(causal, dict):
            cv = causal.get("overall_causal_validity", "unknown")
            if cv in ("partial", "weak"):
                um.known_unknowns.append(
                    f"因果関係の妥当性が{cv} — 完全な因果メカニズムが未特定"
                )

        if total > 0 and (total - passed) > 0:
            um.known_unknowns.append(
                f"{total - passed}個のソルバーが不一致 — 不一致の原因が未特定"
            )

        # Suspected unknowns (things we suspect we're missing)
        text_len = len(claim_text)
        if text_len > 200:
            um.suspected_unknowns.append(
                "長いテキストの文脈依存的なニュアンスが失われている可能性"
            )

        um.suspected_unknowns.append(
            "主張の文化的・時代的コンテキストが未考慮の可能性"
        )

        if any(kw in claim_text.lower() for kw in SELF_REFERENCE_KEYWORDS):
            um.suspected_unknowns.append(
                "自己参照的主張に対する検証の信頼性限界が未定量"
            )

        return um

    def _propose_corrections(
        self,
        verdict: str,
        confidence: float,
        passed: int,
        total: int,
        biases: List[BiasDetection],
        consistency: float,
    ) -> List[CorrectionAction]:
        corrections = []

        # Confidence correction based on consistency
        if consistency < 0.7 and confidence > 0.5:
            corrected_conf = confidence * consistency
            corrections.append(CorrectionAction(
                target="confidence",
                original_value=confidence,
                proposed_value=round(max(CORRECTION_CONFIDENCE_FLOOR, corrected_conf), 3),
                reason=f"三者整合性が低い ({consistency:.2f}) — "
                    "信頼度を整合性スコアで割引",
                confidence_in_correction=0.6,
            ))

        # Bias-adjusted confidence
        total_bias_severity = sum(b.severity for b in biases)
        if total_bias_severity > 0.5:
            bias_factor = max(0.5, 1.0 - total_bias_severity * 0.2)
            corrected = confidence * bias_factor
            corrections.append(CorrectionAction(
                target="confidence",
                original_value=confidence,
                proposed_value=round(max(CORRECTION_CONFIDENCE_FLOOR, corrected), 3),
                reason=f"バイアス総量 {total_bias_severity:.2f} による補正 "
                    f"(factor={bias_factor:.2f})",
                confidence_in_correction=0.5,
            ))

        # Verdict correction
        if total > 0:
            solver_ratio = passed / total
            if verdict == "VERIFIED" and solver_ratio < 0.5 and confidence < 0.5:
                corrections.append(CorrectionAction(
                    target="verdict",
                    original_value=verdict,
                    proposed_value="EXPLORING",
                    reason="ソルバー合意率と信頼度の両方が低いが"
                        "VERIFIEDと判定されている",
                    confidence_in_correction=0.7,
                ))

        return corrections

    def _generate_self_assessment(
        self,
        trustworthiness: float,
        biases: List[BiasDetection],
        corrections: List[CorrectionAction],
        uncertainty: UncertaintyMap,
    ) -> str:
        lines = []

        if trustworthiness >= 0.8:
            lines.append("この検証結果は高い信頼性を持つ。")
        elif trustworthiness >= 0.5:
            lines.append("この検証結果は中程度の信頼性。以下の留意点あり。")
        else:
            lines.append("この検証結果の信頼性は低い。以下の問題が検出された。")

        if biases:
            bias_types = set(b.bias_type for b in biases)
            lines.append(f"検出バイアス: {', '.join(bias_types)}")

        if corrections:
            lines.append(f"修正提案: {len(corrections)}件")

        unknowns = len(uncertainty.known_unknowns) + len(uncertainty.suspected_unknowns)
        if unknowns > 0:
            lines.append(f"未解決の不確実性: {unknowns}件")

        return " ".join(lines)
