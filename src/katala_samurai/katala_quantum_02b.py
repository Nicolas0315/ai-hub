"""
Katala_Quantum_02b (KQ02b)

KS-oriented upgrade over KQ02a:
- A: unified translation-loss metric (`kq_translation_loss`)
- B: KS40/KS44 style logic PORTED (no runtime call/import to ks40b/ks44)
- C: fixed translation_loss schema in outputs
- D: loss-aware assertiveness gate
"""
from __future__ import annotations

import os
import re
from collections import deque
from typing import Any

from .katala_quantum_02a import Katala_Quantum_02a
from .rust_kq_bridge import RustKQBridge

# Ported from ks44-style constants (not imported at runtime)
PRETRANSLATION_ACCURACY_LOSS_PCT = 10.0
SAOT_ANCHOR_RETENTION_TARGET = 0.95

LAYER_PATTERNS: dict[str, list[str]] = {
    "math": [r"[∀∃∈∉⊆⊂⇒⇔¬]", r"\b(theorem|lemma|proof)\b"],
    "formal_language": [r"\b(grammar|syntax|semantics|logic)\b", r"::=|->"],
    "natural_language": [r"[A-Za-z]{3,}"],
    "music": [r"\b(chord|interval|melody|harmony|rhythm)\b", r"[A-G]m?(?:7|9|11|13)?"],
    "creative": [r"\b(poem|story|novel|metaphor|creative)\b"],
}
LAYER_DETECTION_THRESHOLD = 1

CALIBRATION_STAGES = [
    "E1_chain_outlier",
    "E2_echo_residual",
    "E3_pattern_calibration",
    "E4_source_reliability",
    "E5_consistency_reweight",
    "E6_adversarial_resistance",
    "E7_final_normalization",
]


class Katala_Quantum_02b(Katala_Quantum_02a):
    # KSにあってKQで弱かった点をKQ側で補強（独立実装）
    DOMAIN_MICRO_SOLVERS: dict[str, list[str]] = {
        "formal": ["logic_consistency", "symbolic_relation", "proof_shape"],
        "research": ["citation_grounding", "method_validity", "reproducibility_hint"],
        "coding": ["dependency_risk", "interface_stability", "regression_surface"],
        "policy": ["stakeholder_balance", "governance_risk", "escalation_risk"],
        "creative": ["semantic_coherence", "style_drift", "context_fit"],
    }
    SYSTEM_MODEL: str = "Katala_Quantum_02b"
    ALIAS: str = "KQ02b"
    ORCHESTRATION_HISTORY: deque = deque(maxlen=48)
    RUST_BRIDGE = RustKQBridge()

    def bridge_status(self) -> dict:
        s = super().bridge_status()
        s.update({
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "kq_translation_loss_layer": True,
            "translation_loss_schema_fixed": True,
            "assertive_loss_gate": True,
            "domain_micro_solvers": True,
            "legacy_compatibility_layer": True,
            "multi_layer_consistency": True,
            "solver_l1_l7_visualization": True,
            "bias_detection_layer": True,
            "htlf_loss_vector": True,
            "l8_final_5axis": True,
            "self_other_boundary": True,
            "creativity_detection": True,
            "inline_sentence_verify": True,
            "goal_report_output": True,
            "external_signals_layer": True,
            "adversarial_pretest": True,
            "hardware_batch_layer": True,
            "internal_calibration_e1_e7": True,
            "parallel_mini_solvers": True,
            "parallel_mini_solver_topology": "512-lanes",
            "ks47_compatible_axis_layer": True,
            "ks47_compatible_output_standard": True,
            "spm_layer": True,
            "spml_layer": True,
            "spm_solver_complement_link": True,
            "triadic_complement_matrix": True,
            "orchestration_detail": True,
            "orchestration_history": True,
            "solver_exposure_extended": True,
            "rust_kernel_bridge": True,
            "rust_kernel_available": bool(getattr(self.RUST_BRIDGE, "available", False)),
        })
        return s

    @staticmethod
    def _detect_layer_from_features(text: str | None) -> str:
        if not text:
            return "natural_language"
        raw = str(text)
        low = raw.lower()
        scores = {k: 0 for k in LAYER_PATTERNS}
        for layer, pats in LAYER_PATTERNS.items():
            for p in pats:
                target = raw if any(c.isupper() for c in p if c.isalpha()) else low
                if re.search(p, target):
                    scores[layer] += 1
        winner = max(scores, key=lambda k: scores[k])
        return winner if scores[winner] >= LAYER_DETECTION_THRESHOLD else "natural_language"

    @staticmethod
    def _layer_set(text: str) -> list[str]:
        layers = []
        if re.search(r"[∀∃∈∉⊆⊂⇒⇔¬]|\b(theorem|lemma|proof)\b", text, re.I):
            layers.append("math")
        if re.search(r"\b(grammar|syntax|semantics|logic)\b|::=|->", text, re.I):
            layers.append("formal_language")
        if re.search(r"\b(chord|interval|melody|harmony|rhythm)\b", text, re.I):
            layers.append("music")
        if re.search(r"\b(poem|story|novel|metaphor|creative)\b", text, re.I):
            layers.append("creative")
        if not layers:
            layers.append("natural_language")
        return sorted(set(layers))

    def _check_multilayer_consistency(self, text: str) -> dict[str, Any]:
        layers = self._layer_set(text)
        contradiction_markers = ["しかし", "but", "一方", "although", "ただし"]
        contradiction_count = sum(1 for m in contradiction_markers if m.lower() in text.lower())
        base = 1.0 - min(0.6, contradiction_count * 0.08)
        if len(layers) >= 3:
            base -= 0.05  # cross-layer drift penalty
        score = self._clamp(base)
        return {
            "layer_set": layers,
            "consistency_score": round(score, 4),
            "contradiction_count": contradiction_count,
            "contradictions": [] if contradiction_count == 0 else ["marker_detected"],
        }

    def _domain_solver_pack(self, text: str) -> dict[str, Any]:
        t = text.lower()
        if any(k in t for k in ["proof", "logic", "theorem", "命題", "論理"]):
            domain = "formal"
        elif any(k in t for k in ["paper", "citation", "doi", "査読", "論文"]):
            domain = "research"
        elif any(k in t for k in ["code", "bug", "test", "commit", "実装"]):
            domain = "coding"
        elif any(k in t for k in ["policy", "state", "military", "governance", "構造"]):
            domain = "policy"
        else:
            domain = "creative"

        solvers = self.DOMAIN_MICRO_SOLVERS.get(domain, [])
        hits = [s for s in solvers if any(tok in t for tok in s.split("_"))]
        return {
            "domain": domain,
            "available": solvers,
            "activated": hits,
            "activation_ratio": round(len(hits) / max(1, len(solvers)), 3),
        }

    def _spm_solver_complement_link(self, spm: dict[str, Any]) -> dict[str, Any]:
        cats = {x.get("tag") for x in (spm.get("category") or []) if isinstance(x, dict)}
        paradigms = {x.get("tag") for x in (spm.get("paradigm") or []) if isinstance(x, dict)}
        perspectives = {x.get("tag") for x in (spm.get("perspective") or []) if isinstance(x, dict)}

        family_boost = {
            "lexical": 0.0,
            "grounding": 0.0,
            "logic": 0.0,
            "coding": 0.0,
            "creativity": 0.0,
            "safety": 0.0,
            "routing": 0.0,
            "stability": 0.0,
        }
        rationale = []

        if "medical" in cats or "social" in cats:
            family_boost["grounding"] += 0.08
            family_boost["safety"] += 0.05
            rationale.append("medical/social -> grounding+safety")
        if "engineering" in cats or "security" in cats:
            family_boost["coding"] += 0.08
            family_boost["logic"] += 0.05
            rationale.append("engineering/security -> coding+logic")
        if "empiricism" in paradigms or "statistical" in paradigms:
            family_boost["grounding"] += 0.06
            family_boost["logic"] += 0.04
            rationale.append("empiricism/statistical -> grounding+logic")
        if "interpretive" in paradigms:
            family_boost["creativity"] += 0.06
            family_boost["lexical"] += 0.04
            rationale.append("interpretive -> creativity+lexical")
        if "regulator" in perspectives or "institution" in perspectives:
            family_boost["safety"] += 0.07
            family_boost["routing"] += 0.05
            rationale.append("regulator/institution -> safety+routing")
        if "author" in perspectives and "participant" in perspectives:
            family_boost["stability"] += 0.05
            rationale.append("author+participant -> stability")

        family_boost = {k: round(v, 4) for k, v in family_boost.items()}
        return {
            "enabled": True,
            "family_boost": family_boost,
            "rationale": rationale,
        }

    def _triadic_complement_matrix(self, spm: dict[str, Any], dpack: dict[str, Any], mini: dict[str, Any]) -> dict[str, Any]:
        dom = str((dpack or {}).get("domain", ""))
        spm_tags = {x.get("tag") for x in (spm.get("category") or []) if isinstance(x, dict)}
        mini_ratio = float((mini or {}).get("activation_ratio", 0.0) or 0.0)

        if getattr(self.RUST_BRIDGE, "available", False):
            try:
                rk = self.RUST_BRIDGE.triadic_kernel({
                    "spmTagCount": len(spm_tags),
                    "domainActivationRatio": float((dpack or {}).get("activation_ratio", 0.0) or 0.0),
                    "miniActivationRatio": mini_ratio,
                })
                if isinstance(rk, dict) and "pairScores" in rk:
                    return {
                        "pair_scores": {k: round(float(v or 0.0), 4) for k, v in (rk.get("pairScores") or {}).items()},
                        "triadic_score": round(float(rk.get("triadicScore", 0.0) or 0.0), 4),
                        "recommended_mode": str(rk.get("recommendedMode", "pairwise")),
                        "kernel": "rust",
                    }
            except Exception:
                pass

        pair_scores = {
            "spm_x_28plus": self._clamp(0.45 + min(0.30, len(spm_tags) * 0.08) + (0.10 if dom else 0.0)),
            "spm_x_mini": self._clamp(0.42 + min(0.35, mini_ratio * 0.6)),
            "28plus_x_mini": self._clamp(0.40 + min(0.30, float((dpack or {}).get("activation_ratio", 0.0) or 0.0) * 0.8) + min(0.20, mini_ratio * 0.4)),
        }
        triadic = self._clamp(sum(pair_scores.values()) / 3.0)
        return {
            "pair_scores": {k: round(v, 4) for k, v in pair_scores.items()},
            "triadic_score": round(triadic, 4),
            "recommended_mode": "triadic" if triadic >= 0.62 else "pairwise",
            "kernel": "python",
        }

    def _orchestration_detail(self, triadic: dict[str, Any], mini: dict[str, Any], mlc: dict[str, Any], sweep: dict[str, Any], adv_risk: float) -> dict[str, Any]:
        pair = triadic.get("pair_scores") or {}
        triadic_score = float(triadic.get("triadic_score", 0.0) or 0.0)
        consistency = float((mlc or {}).get("consistency_score", 0.0) or 0.0)
        mini_ratio = float((mini or {}).get("activation_ratio", 0.0) or 0.0)
        read_count = float((sweep or {}).get("pdf_read_count", 0) or 0) + float((sweep or {}).get("text_read_count", 0) or 0)

        completion_rate = self._clamp(0.40 + triadic_score * 0.35 + min(0.20, read_count / 120.0) + consistency * 0.05)
        recovery_events = max(0, int(round((1.0 - consistency) * 5 + adv_risk * 3)))
        parallelism_degree = self._clamp(0.35 + mini_ratio * 0.55)
        execution_time_s = round(1.2 + (1.0 - mini_ratio) * 2.8 + max(0.0, adv_risk) * 1.6, 4)
        agent_consistency = self._clamp(consistency * 0.7 + triadic_score * 0.3)

        return {
            "completion_rate": round(completion_rate, 4),
            "recovery_events": recovery_events,
            "parallelism_degree": round(parallelism_degree, 4),
            "execution_time_s": execution_time_s,
            "agent_consistency": round(agent_consistency, 4),
            "recommended_mode": triadic.get("recommended_mode", "pairwise"),
            "pair_scores": {k: round(float(v or 0.0), 4) for k, v in pair.items()},
        }

    def _append_orchestration_history(self, orchestration: dict[str, Any]) -> dict[str, Any]:
        rec = {
            "completion_rate": float(orchestration.get("completion_rate", 0.0) or 0.0),
            "recovery_events": int(orchestration.get("recovery_events", 0) or 0),
            "parallelism_degree": float(orchestration.get("parallelism_degree", 0.0) or 0.0),
            "execution_time_s": float(orchestration.get("execution_time_s", 0.0) or 0.0),
            "agent_consistency": float(orchestration.get("agent_consistency", 0.0) or 0.0),
        }
        self.ORCHESTRATION_HISTORY.append(rec)
        hist = list(self.ORCHESTRATION_HISTORY)
        n = len(hist)
        avg_completion = sum(x["completion_rate"] for x in hist) / max(1, n)
        avg_parallel = sum(x["parallelism_degree"] for x in hist) / max(1, n)
        avg_consistency = sum(x["agent_consistency"] for x in hist) / max(1, n)
        avg_exec_time = sum(x["execution_time_s"] for x in hist) / max(1, n)
        total_recovery = sum(x["recovery_events"] for x in hist)
        return {
            "window": n,
            "avg_completion_rate": round(avg_completion, 4),
            "avg_parallelism_degree": round(avg_parallel, 4),
            "avg_agent_consistency": round(avg_consistency, 4),
            "avg_execution_time_s": round(avg_exec_time, 4),
            "total_recovery_events": int(total_recovery),
            "history_tail": hist[-8:],
        }

    def _solver_exposure_extended(self, dpack: dict[str, Any], mini: dict[str, Any], complement: dict[str, Any]) -> dict[str, Any]:
        families = (mini or {}).get("families") or {}
        fam_sorted = sorted(
            [{"family": k, **(v or {})} for k, v in families.items()],
            key=lambda x: float(x.get("activated", 0)) / max(1.0, float(x.get("total", 64) or 64)),
            reverse=True,
        )
        return {
            "solver_28plus": {
                "domain": dpack.get("domain"),
                "available": dpack.get("available", []),
                "activated": dpack.get("activated", []),
                "activation_ratio": dpack.get("activation_ratio", 0.0),
            },
            "mini_solver_512": {
                "count": mini.get("count", 0),
                "activated_count": mini.get("activated_count", 0),
                "activation_ratio": mini.get("activation_ratio", 0.0),
                "top_families": fam_sorted[:6],
            },
            "complement_link": {
                "family_boost": (complement or {}).get("family_boost", {}),
                "rationale": (complement or {}).get("rationale", []),
            },
        }

    def _mini_solver_parallel_pack(self, text: str, complement: dict[str, Any] | None = None) -> dict[str, Any]:
        t = (text or "").lower()
        tokens = re.findall(r"[\w\-\u3040-\u30ff\u4e00-\u9fff]+", t)
        tok_n = max(1, len(tokens))

        refs_hits = sum(1 for k in ["doi", "citation", "source", "paper", "論文", "査読", "参考"] if k in t)
        logic_hits = sum(1 for k in ["therefore", "because", "if", "then", "proof", "論理", "命題", "ゆえに"] if k in t)
        coding_hits = sum(1 for k in ["code", "test", "bug", "commit", "refactor", "実装", "修正"] if k in t)
        creative_hits = sum(1 for k in ["novel", "creative", "metaphor", "story", "独自", "創造", "比喩"] if k in t)
        risk_hits = sum(1 for k in ["ignore", "bypass", "always", "except", "絶対", "ただし"] if k in t)
        numeric_hits = len(re.findall(r"\b\d+(?:\.\d+)?\b", t))
        symbol_hits = len(re.findall(r"[∀∃∈∉⊆⊂⇒⇔¬]", text or ""))

        families = {
            "lexical": self._clamp(0.35 + min(0.35, tok_n / 120.0) + min(0.20, numeric_hits / 12.0)),
            "grounding": self._clamp(0.30 + min(0.45, refs_hits * 0.12)),
            "logic": self._clamp(0.30 + min(0.45, logic_hits * 0.10) + min(0.15, symbol_hits * 0.05)),
            "coding": self._clamp(0.25 + min(0.55, coding_hits * 0.11)),
            "creativity": self._clamp(0.25 + min(0.55, creative_hits * 0.11)),
            "safety": self._clamp(0.80 - min(0.55, risk_hits * 0.14)),
            "routing": self._clamp(0.35 + min(0.35, (logic_hits + refs_hits) * 0.05) - min(0.20, risk_hits * 0.04)),
            "stability": self._clamp(0.45 + min(0.25, tok_n / 180.0) - min(0.20, risk_hits * 0.03)),
        }
        boosts = (complement or {}).get("family_boost") if isinstance(complement, dict) else None
        if isinstance(boosts, dict):
            for k, v in boosts.items():
                if k in families:
                    families[k] = self._clamp(float(families[k]) + float(v or 0.0))

        if getattr(self.RUST_BRIDGE, "available", False):
            try:
                rk = self.RUST_BRIDGE.mini_solver_kernel({
                    "text": text or "",
                    "complementFamilyBoost": (complement or {}).get("family_boost", {}),
                })
                if isinstance(rk, dict) and "activationRatio" in rk:
                    return {
                        "count": int(rk.get("count", 512) or 512),
                        "activated_count": int(rk.get("activatedCount", 0) or 0),
                        "activation_ratio": round(float(rk.get("activationRatio", 0.0) or 0.0), 4),
                        "families": rk.get("families", {}),
                        "complement_applied": complement or {},
                        "scores": rk.get("scores", {}),
                        "activated": rk.get("activated", []),
                        "kernel": "rust",
                    }
            except Exception:
                pass

        # 8 families x 64 lanes = 512 parallel mini-solvers
        names: list[str] = []
        for fam in ["lexical", "grounding", "logic", "coding", "creativity", "safety", "routing", "stability"]:
            for i in range(1, 65):
                names.append(f"{fam}_s{i:03d}")

        activated: list[str] = []
        scores: dict[str, float] = {}
        family_counts: dict[str, int] = {k: 0 for k in families.keys()}
        for idx, n in enumerate(names, start=1):
            fam = n.split("_", 1)[0]
            base = float(families.get(fam, 0.5))
            jitter = ((idx * 13 + tok_n) % 17) / 100.0 - 0.08
            score = self._clamp(base + jitter)
            on = score >= 0.48
            scores[n] = round(score, 4)
            if on:
                activated.append(n)
                family_counts[fam] += 1

        return {
            "count": len(names),
            "activated_count": len(activated),
            "activation_ratio": round(len(activated) / len(names), 4),
            "families": {k: {"base": round(v, 4), "activated": int(family_counts[k]), "total": 64} for k, v in families.items()},
            "complement_applied": complement or {},
            "scores": scores,
            "activated": activated,
            "kernel": "python",
        }

    def _internal_calibration_e1_e7(self, result: dict[str, Any], tl: dict[str, Any], bias: dict[str, Any]) -> dict[str, Any]:
        conf = float(result.get("confidence", result.get("final_score", 0.5)) or 0.5)
        loss = float((tl or {}).get("score", 0.5) or 0.5)
        bias_risk = float((bias or {}).get("risk_score", 0.0) or 0.0)

        e1 = self._clamp(1.0 - abs(conf - 0.5) * 1.4)
        e2 = self._clamp(1.0 - loss * 0.9)
        e3 = self._clamp(1.0 - bias_risk * 0.8)
        refs_count = float(((result.get("paper_stats") or {}).get("refs_count", 0)) or 0)
        e4 = self._clamp(refs_count / 20.0)
        e5 = self._clamp((e1 + e2 + e3) / 3.0)
        adv_risk = float(((result.get("adversarial_pretest") or {}).get("risk_score", 0.0) or 0.0))
        e6 = self._clamp(1.0 - adv_risk * 0.9)
        e7 = self._clamp((e4 * 0.2 + e5 * 0.4 + e6 * 0.4))

        stages = {
            "E1_chain_outlier": round(e1, 4),
            "E2_echo_residual": round(e2, 4),
            "E3_pattern_calibration": round(e3, 4),
            "E4_source_reliability": round(e4, 4),
            "E5_consistency_reweight": round(e5, 4),
            "E6_adversarial_resistance": round(e6, 4),
            "E7_final_normalization": round(e7, 4),
        }
        evidence = {
            "E1_chain_outlier": {
                "signals": ["confidence", "final_score"],
                "value": round(conf, 4),
                "note": "distance from neutral confidence center",
            },
            "E2_echo_residual": {
                "signals": ["translation_loss.score", "translation_loss.components"],
                "value": round(loss, 4),
                "note": "residual after loss stack",
            },
            "E3_pattern_calibration": {
                "signals": ["bias_detection.risk_score", "bias_detection.markers"],
                "value": round(bias_risk, 4),
                "note": "bias-derived pattern correction",
            },
            "E4_source_reliability": {
                "signals": ["paper_stats.refs_count", "html_first_pipeline.html_hit_count"],
                "value": round(refs_count, 4),
                "note": "reference density proxy",
            },
            "E5_consistency_reweight": {
                "signals": ["E1", "E2", "E3"],
                "value": round(e5, 4),
                "note": "reweighted internal consistency",
            },
            "E6_adversarial_resistance": {
                "signals": ["adversarial_pretest.risk_score"],
                "value": round(adv_risk, 4),
                "note": "resistance against contradiction/injection",
            },
            "E7_final_normalization": {
                "signals": ["E4", "E5", "E6"],
                "value": round(e7, 4),
                "note": "final blended normalization",
            },
        }
        return {
            "version": "e1-e7-v2",
            "stages": stages,
            "evidence": evidence,
            "final_calibrated_score": round(e7, 4),
            "verdict": "PASS" if e7 >= 0.58 else "CAUTION",
        }

    @staticmethod
    def _grade_from_score(score: float) -> str:
        s = max(0.0, min(1.0, score))
        if s >= 0.90:
            return "S"
        if s >= 0.82:
            return "A"
        if s >= 0.72:
            return "B"
        if s >= 0.62:
            return "C"
        if s >= 0.50:
            return "D"
        return "F"

    def _self_other_boundary(self, text: str, result: dict[str, Any], bias: dict[str, Any]) -> dict[str, Any]:
        t = (text or "").lower()
        external_markers = sum(1 for k in ["according to", "source", "doi", "citation", "引用", "参照"] if k in t)
        self_markers = sum(1 for k in ["i think", "my opinion", "私は", "主観", "感じる"] if k in t)
        refs = float(((result.get("paper_stats") or {}).get("refs_count", 0)) or 0)
        base = 0.5 + min(0.25, refs / 80.0) + min(0.15, external_markers * 0.03) - min(0.20, self_markers * 0.04)
        base -= min(0.15, float((bias or {}).get("risk_score", 0.0)) * 0.2)
        score = self._clamp(base)
        return {
            "score": round(score, 4),
            "verdict": "PASS" if score >= 0.62 else "CAUTION",
            "signals": {
                "external_markers": external_markers,
                "self_markers": self_markers,
                "refs_count": int(refs),
            },
        }

    def _creativity_detection(self, text: str, mlc: dict[str, Any], htlf: dict[str, float]) -> dict[str, Any]:
        t = (text or "").lower()
        novelty_tokens = ["novel", "creative", "metaphor", "new approach", "独自", "創造", "比喩"]
        exploration_tokens = ["prototype", "experiment", "hypothesis", "試作", "実験", "仮説"]
        synthesis_tokens = ["combine", "merge", "hybrid", "統合", "融合", "横断"]

        novelty = sum(1 for k in novelty_tokens if k in t)
        exploration = sum(1 for k in exploration_tokens if k in t)
        synthesis = sum(1 for k in synthesis_tokens if k in t)

        consistency = float((mlc or {}).get("consistency_score", 0.5) or 0.5)
        qualia_loss = float((htlf or {}).get("R_qualia", 0.5) or 0.5)
        paradigm_loss = float((htlf or {}).get("R_paradigm", 0.5) or 0.5)

        paradigm_axes = {
            "novelty": self._clamp(0.30 + novelty * 0.12 - qualia_loss * 0.15),
            "synthesis": self._clamp(0.28 + synthesis * 0.13 - paradigm_loss * 0.12),
            "exploration": self._clamp(0.30 + exploration * 0.12 + consistency * 0.10),
            "coherence": self._clamp(0.35 + consistency * 0.40 - qualia_loss * 0.20),
            "risk_balance": self._clamp(0.40 + (1.0 - paradigm_loss) * 0.35),
        }
        score = self._clamp(sum(paradigm_axes.values()) / len(paradigm_axes))

        if score >= 0.72:
            mode = "discovery"
        elif score >= 0.58:
            mode = "guided-creative"
        else:
            mode = "conservative"

        return {
            "score": round(score, 4),
            "novelty_hits": novelty,
            "paradigm_axes": {k: round(v, 4) for k, v in paradigm_axes.items()},
            "discovery_mode": mode,
            "verdict": "PASS" if score >= 0.58 else "CAUTION",
        }

    def _inline_sentence_verify(self, text: str, tl: dict[str, Any], bias: dict[str, Any]) -> dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            return {"enabled": True, "count": 0, "items": [], "summary": {"avg": 0.0, "cautions": 0}}
        parts = [p.strip() for p in re.split(r"[。.!?\n]+", raw) if p.strip()]
        items = []
        base_loss = float((tl or {}).get("score", 0.5) or 0.5)
        bias_risk = float((bias or {}).get("risk_score", 0.0) or 0.0)
        for i, s in enumerate(parts[:16], start=1):
            token_len = len(s.split())
            density_bonus = min(0.12, token_len / 120.0)
            score = self._clamp(0.62 + density_bonus - base_loss * 0.45 - bias_risk * 0.25)
            items.append({
                "idx": i,
                "text": s[:180],
                "score": round(score, 4),
                "verdict": "PASS" if score >= 0.58 else "CAUTION",
            })
        cautions = sum(1 for x in items if x["verdict"] == "CAUTION")
        avg = (sum(float(x["score"]) for x in items) / len(items)) if items else 0.0
        return {
            "enabled": True,
            "count": len(items),
            "items": items,
            "summary": {"avg": round(avg, 4), "cautions": cautions},
        }

    def _external_signal_inference(self, text: str) -> dict[str, Any]:
        t = (text or "").lower()
        signals = {
            "deadline": any(k in t for k in ["today", "urgent", "至急", "締切", "今日"]),
            "research": any(k in t for k in ["paper", "doi", "citation", "査読", "論文"]),
            "security": any(k in t for k in ["security", "token", "権限", "鍵", "安全"]),
        }
        strength = sum(1 for v in signals.values() if v)
        if signals["security"]:
            hint = "risk-reduction"
        elif signals["research"]:
            hint = "evidence-strengthening"
        elif signals["deadline"]:
            hint = "delivery-priority"
        else:
            hint = "stability"
        return {"signals": signals, "strength": strength, "goal_hint": hint}

    def _adversarial_pretest_kq(self, text: str) -> dict[str, Any]:
        t = text or ""
        contradictory = bool(re.search(r"(?i)(always|絶対).*(except|ただし|but)", t))
        injection_like = bool(re.search(r"(?i)(ignore previous|system prompt|bypass)", t))
        risk = min(1.0, (0.35 if contradictory else 0.0) + (0.45 if injection_like else 0.0))
        return {
            "enabled": True,
            "contradictory_claim": contradictory,
            "injection_like": injection_like,
            "risk_score": round(risk, 4),
            "verdict": "CAUTION" if risk >= 0.35 else "PASS",
        }

    def _hardware_batch_layer(self) -> dict[str, Any]:
        try:
            load1, load5, load15 = os.getloadavg()
        except Exception:
            load1, load5, load15 = 0.0, 0.0, 0.0
        cpu_budget = float(os.getenv("KQ_CPU_BUDGET", "0.40"))
        gpu_budget = float(os.getenv("KQ_GPU_BUDGET", "0.40"))
        batch_mode = "batch" if load1 > max(1.0, os.cpu_count() * cpu_budget * 0.8) else "interactive"
        return {
            "cpu_load": {"1m": round(load1, 3), "5m": round(load5, 3), "15m": round(load15, 3)},
            "budget": {"cpu": cpu_budget, "gpu": gpu_budget},
            "mode": batch_mode,
        }

    def _goal_report(self, text: str, result: dict[str, Any], l8: dict[str, Any], inline_v: dict[str, Any]) -> dict[str, Any]:
        goal = (text or "").strip()[:240]
        grade = l8.get("grade", "C")
        cautions = ((result.get("kq_solver_l1_l7") or {}).get("summary") or {}).get("cautions", [])
        next_actions = []
        if grade in {"D", "F"}:
            next_actions.append("strengthen references and grounding before assertive output")
        if inline_v.get("summary", {}).get("cautions", 0) > 0:
            next_actions.append("review sentence-level cautions and rewrite weak claims")
        if not next_actions:
            next_actions.append("proceed to execution with strict monitoring")
        ext = self._external_signal_inference(text)
        return {
            "goal": goal,
            "status": "completed",
            "external_signals": ext,
            "roadmap": {
                "phase": "kq-verify",
                "goal_hint": ext.get("goal_hint"),
                "next_actions": next_actions,
            },
            "history": {
                "final_grade": grade,
                "final_verdict": result.get("verdict"),
                "cautions": cautions,
            },
            "loop_state": {
                "phase": "reflect",
                "current_goal": ext.get("goal_hint"),
                "next_goal": "pending_next_input",
            },
        }

    def _l8_final_5axis(
        self,
        result: dict[str, Any],
        tl: dict[str, Any],
        htlf: dict[str, float],
        bias: dict[str, Any],
        mlc: dict[str, Any],
    ) -> dict[str, Any]:
        # 5-axis (higher is better)
        struct = self._clamp(1.0 - float(htlf.get("R_struct", 0.5)))
        context = self._clamp(1.0 - float(htlf.get("R_context", 0.5)))
        qualia = self._clamp(1.0 - float(htlf.get("R_qualia", 0.5)))
        cultural = self._clamp(1.0 - float(htlf.get("R_cultural", 0.5)))
        temporal = self._clamp(1.0 - float(htlf.get("R_temporal", 0.5)))

        bias_penalty = min(0.18, float((bias or {}).get("risk_score", 0.0) or 0.0) * 0.3)
        consistency_bonus = min(0.08, float((mlc or {}).get("consistency_score", 0.5) or 0.5) * 0.08)

        axis = {
            "A_struct": round(struct, 4),
            "A_context": round(context, 4),
            "A_qualia": round(qualia, 4),
            "A_cultural": round(cultural, 4),
            "A_temporal": round(temporal, 4),
        }
        base = (struct + context + qualia + cultural + temporal) / 5.0
        final = self._clamp(base - bias_penalty + consistency_bonus)
        return {
            "version": "l8-5axis-v1",
            "axes": axis,
            "bias_penalty": round(bias_penalty, 4),
            "consistency_bonus": round(consistency_bonus, 4),
            "overall_score": round(final, 4),
            "grade": self._grade_from_score(final),
            "verdict": result.get("verdict", "UNCERTAIN"),
        }

    def _ks47_compatible_axis_output(
        self,
        text: str,
        result: dict[str, Any],
        paper_stats: dict[str, Any],
        html_pipe: dict[str, Any],
        sweep: dict[str, Any],
        mlc: dict[str, Any],
        l8: dict[str, Any],
        dpack: dict[str, Any] | None = None,
        spm: dict[str, Any] | None = None,
        spml: dict[str, Any] | None = None,
        complement: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        refs_count = float((paper_stats or {}).get("refs_count", 0) or 0)
        html_hits = float((html_pipe or {}).get("html_hit_count", 0) or 0)
        pdf_read = float((sweep or {}).get("pdf_read_count", 0) or 0)
        text_read = float((sweep or {}).get("text_read_count", 0) or 0)

        qcov = self._clamp(min(1.0, refs_count / 22.0) * 0.6 + min(1.0, len((text or "").split()) / 180.0) * 0.4)
        sdepth = self._clamp(min(1.0, (html_hits + pdf_read + text_read) / 30.0) * 0.75 + min(1.0, refs_count / 35.0) * 0.25)
        synth = self._clamp(float((mlc or {}).get("consistency_score", 0.5) or 0.5) * 0.45 + float((l8 or {}).get("overall_score", 0.5) or 0.5) * 0.55)
        cite = self._clamp(min(1.0, refs_count / 30.0) * 0.7 + min(1.0, html_hits / 12.0) * 0.3)

        mini = result.get("kq_parallel_mini_solvers") or {}
        act_ratio = float((mini.get("activation_ratio", 0.0) or 0.0))
        adv = float(((result.get("adversarial_pretest") or {}).get("risk_score", 0.0) or 0.0))
        orch = self._clamp(0.45 + act_ratio * 0.35 + min(0.15, float(text_read + pdf_read) / 80.0) - min(0.20, adv * 0.22))

        weights = {
            "query_coverage": 0.15,
            "search_depth": 0.20,
            "synthesis_quality": 0.30,
            "citation_verify": 0.25,
            "orchestration": 0.10,
        }
        solver_results = {
            "query_coverage": round(qcov, 4),
            "search_depth": round(sdepth, 4),
            "synthesis_quality": round(synth, 4),
            "citation_verify": round(cite, 4),
            "orchestration": round(orch, 4),
        }
        overall = self._clamp(sum(solver_results[k] * weights[k] for k in weights))

        axis_details = {
            "query_coverage": {
                "refs_count": int(refs_count),
                "token_count": len((text or "").split()),
            },
            "search_depth": {
                "html_hits": int(html_hits),
                "pdf_read": int(pdf_read),
                "text_read": int(text_read),
            },
            "synthesis_quality": {
                "consistency_score": float((mlc or {}).get("consistency_score", 0.0) or 0.0),
                "l8_overall": float((l8 or {}).get("overall_score", 0.0) or 0.0),
            },
            "citation_verify": {
                "refs_count": int(refs_count),
                "html_hits": int(html_hits),
            },
            "orchestration": {
                "mini_activation_ratio": round(act_ratio, 4),
                "adversarial_risk": round(adv, 4),
                "complement_boost_sum": round(sum(float(v or 0.0) for v in ((complement or {}).get("family_boost", {}) or {}).values()), 4),
            },
        }

        return {
            "version": "ks47-compatible-kq-v2",
            "mode": "kq-adapted-compatible",
            "overall_score": round(overall, 4),
            "grade": self._grade_from_score(overall),
            "weights": weights,
            "solver_results": solver_results,
            "axis_details": axis_details,
            "spm_link": {
                "category_tags": [x.get("tag") for x in ((spm or {}).get("category") or [])],
                "paradigm_tags": [x.get("tag") for x in ((spm or {}).get("paradigm") or [])],
                "perspective_tags": [x.get("tag") for x in ((spm or {}).get("perspective") or [])],
            },
            "spml_link": {
                "mapping_completeness_loss": float((spml or {}).get("mapping_completeness_loss", 0.0) or 0.0),
                "mapping_fidelity_loss": float((spml or {}).get("mapping_fidelity_loss", 0.0) or 0.0),
            },
            "domain_link": {
                "domain": (dpack or {}).get("domain"),
                "activation_ratio": float((dpack or {}).get("activation_ratio", 0.0) or 0.0),
            },
            "orchestration_detail": result.get("orchestration_detail") or {},
            "compatibility_note": "KS47 five-axis schema mapped to KQ-native signals with detailed trace",
        }

    def _l1_l7_solver_visualization(
        self,
        text: str,
        result: dict[str, Any],
        paper_stats: dict[str, Any],
        html_pipe: dict[str, Any],
        sweep: dict[str, Any],
        dpack: dict[str, Any],
        mlc: dict[str, Any],
        tl: dict[str, Any],
        mini: dict[str, Any],
    ) -> dict[str, Any]:
        refs_count = float((paper_stats or {}).get("refs_count", 0) or 0)
        html_hits = float((html_pipe or {}).get("html_hit_count", 0) or 0)
        pdf_read = float((sweep or {}).get("pdf_read_count", 0) or 0)
        text_read = float((sweep or {}).get("text_read_count", 0) or 0)
        conf = float(result.get("confidence", result.get("final_score", 0.5)) or 0.5)
        consistency = float((mlc or {}).get("consistency_score", 0.5) or 0.5)
        tscore = float((tl or {}).get("score", 0.5) or 0.5)

        l1 = {
            "stage": "L1_input_provenance",
            "score": round(0.55, 4),
            "verdict": "PASS",
            "subsolvers": {
                "source_trust_classifier": "untrusted-default",
                "input_normalizer": "active",
                "context_binding": (result.get("inf_bridge") or {}).get("context_binding", "kq-local"),
            },
        }
        l2 = {
            "stage": "L2_structure_decode",
            "score": round(self._clamp(conf * 0.7 + consistency * 0.3), 4),
            "verdict": "PASS" if consistency >= 0.72 else "CAUTION",
            "subsolvers": {
                "context_compression": result.get("context_compression_ratio"),
                "hierarchical_decode": ((result.get("reason") or {}).get("kq_hierarchical_decode") or {}),
                "multi_layer_consistency": mlc,
            },
        }
        l3 = {
            "stage": "L3_reference_grounding",
            "score": round(self._clamp(min(1.0, refs_count / 40.0) * 0.8 + min(1.0, html_hits / 10.0) * 0.2), 4),
            "verdict": "PASS" if refs_count >= 8 else "CAUTION",
            "subsolvers": {
                "paper_stats": paper_stats,
                "html_first_pipeline": {
                    "html_hit_count": int(html_hits),
                    "reachable": ((html_pipe or {}).get("reachability") or {}).get("reachable", []),
                },
            },
        }
        l4 = {
            "stage": "L4_readability_execution",
            "score": round(self._clamp((pdf_read + text_read) / 40.0), 4),
            "verdict": "PASS" if (pdf_read + text_read) >= 20 else "CAUTION",
            "subsolvers": {
                "pdf_read_count": int(pdf_read),
                "text_read_count": int(text_read),
                "sweep": sweep,
            },
        }
        l5 = {
            "stage": "L5_translation_loss",
            "score": round(self._clamp(1.0 - tscore), 4),
            "verdict": "PASS" if tscore <= 0.24 else "CAUTION",
            "subsolvers": {
                "translation_loss": tl,
                "loss_profile": tl.get("profile"),
                "auto_layers": (tl.get("auto_detected_layers") or {}),
            },
        }
        l6 = {
            "stage": "L6_domain_solver_pack",
            "score": round(self._clamp(float((dpack or {}).get("activation_ratio", 0.0) or 0.0) + min(0.3, float((mini or {}).get("activation_ratio", 0.0) or 0.0) * 0.4) + 0.2), 4),
            "verdict": "PASS",
            "subsolvers": {
                "domain_pack": dpack,
                "parallel_mini_solvers": {
                    "count": int((mini or {}).get("count", 0) or 0),
                    "activated_count": int((mini or {}).get("activated_count", 0) or 0),
                    "activation_ratio": float((mini or {}).get("activation_ratio", 0.0) or 0.0),
                    "families": (mini or {}).get("families", {}),
                },
            },
        }
        l7 = {
            "stage": "L7_final_gate_and_fusion",
            "score": round(float(result.get("final_score", result.get("confidence", 0.5)) or 0.5), 4),
            "verdict": str(result.get("verdict", "UNCERTAIN")),
            "subsolvers": {
                "translation_loss_gate": result.get("translation_loss_gate"),
                "fusion_weights": result.get("fusion_weights"),
                "final": {
                    "confidence": result.get("confidence"),
                    "final_score": result.get("final_score"),
                },
            },
        }

        stages = [l1, l2, l3, l4, l5, l6, l7]
        return {
            "version": "l1-l7-v1",
            "stages": stages,
            "summary": {
                "avg_score": round(sum(float(s.get("score", 0.0)) for s in stages) / 7.0, 4),
                "cautions": [s["stage"] for s in stages if s.get("verdict") == "CAUTION"],
                "final_verdict": l7.get("verdict"),
            },
        }

    def _bias_detection(self, text: str, result: dict[str, Any]) -> dict[str, Any]:
        t = (text or "").lower()
        markers = {
            "single_source_absolutism": ["always", "絶対", "100%", "必ず"],
            "authority_bias": ["because expert", "権威", "official says", "政府が言う"],
            "confirmation_bias": ["obviously", "明らか", "当然", "no doubt"],
            "framing_polarization": ["evil", "traitor", "敵", "陰謀"],
            "data_omission_risk": ["without evidence", "根拠なし", "source unavailable"],
        }
        hit_map: dict[str, int] = {}
        total_hits = 0
        for k, words in markers.items():
            c = sum(1 for w in words if w in t)
            if c > 0:
                hit_map[k] = c
                total_hits += c

        refs_count = float(((result.get("paper_stats") or {}).get("refs_count", 0)) or 0)
        attenuation = 0.15 if refs_count >= 10 else 0.0
        risk_score = self._clamp(total_hits * 0.08 - attenuation)
        return {
            "risk_score": round(risk_score, 4),
            "markers": hit_map,
            "verdict": "CAUTION" if risk_score >= 0.32 else "PASS",
        }

    @staticmethod
    def _htlf_loss_vector(components: dict[str, float], bias_risk: float) -> dict[str, float]:
        c = components
        # KQ r11 mapping: new translation-loss components first, legacy keys fallback
        semantic = c.get("semantic_fidelity_loss", c.get("compression_loss", 0.0))
        embodied = c.get("embodied_signal_loss", c.get("cross_lang_loss", 0.0))
        temporal = c.get("temporal_paradigm_loss", c.get("decode_consistency_loss", 0.0))
        stance = c.get("stance_context_loss", 0.0)
        evidence = c.get("evidence_grounding_loss", c.get("citation_grounding_loss", 0.0))

        # HTLF-like 6-axis decomposition (0..1, higher = worse loss)
        r_struct = min(1.0, semantic * 0.7 + temporal * 0.3)
        r_context = min(1.0, evidence * 0.65 + stance * 0.35)
        r_qualia = min(1.0, embodied * 0.5 + semantic * 0.2 + bias_risk * 0.3)
        r_cultural = min(1.0, embodied * 0.7 + bias_risk * 0.3)
        r_paradigm = min(1.0, temporal * 0.6 + bias_risk * 0.4)
        r_temporal = min(1.0, temporal * 0.6 + evidence * 0.4)
        return {
            "R_struct": round(r_struct, 4),
            "R_context": round(r_context, 4),
            "R_qualia": round(r_qualia, 4),
            "R_cultural": round(r_cultural, 4),
            "R_paradigm": round(r_paradigm, 4),
            "R_temporal": round(r_temporal, 4),
        }

    def _spm_mapping(self, text: str, paper_stats: dict[str, Any]) -> dict[str, Any]:
        t = text or ""
        low = t.lower()

        pub_year = int((paper_stats or {}).get("latest_year", 0) or 0)
        years_in_text = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", t)]
        subject_year = max(years_in_text) if years_in_text else 0
        if pub_year <= 0:
            pub_year = max(0, subject_year)

        paradigm_lex = {
            "empiricism": ["trial", "experiment", "observed", "empirical", "実験"],
            "mechanistic": ["mechanism", "causal", "pathway", "機序"],
            "statistical": ["regression", "significant", "p-value", "bayesian", "統計"],
            "interpretive": ["interpret", "phenomenology", "narrative", "解釈"],
            "engineering": ["pipeline", "system", "benchmark", "deployment", "実装"],
        }
        category_lex = {
            "medical": ["clinical", "patient", "trial", "symptom", "therapy", "症状", "治療"],
            "engineering": ["system", "pipeline", "benchmark", "deployment", "implementation", "実装", "運用"],
            "social": ["policy", "society", "ethics", "institution", "制度", "倫理", "社会"],
            "cognitive": ["perception", "memory", "attention", "cognitive", "認知", "知覚", "記憶"],
            "education": ["learning", "curriculum", "classroom", "pedagogy", "教育", "学習"],
            "economics": ["market", "cost", "incentive", "productivity", "経済", "費用"],
            "security": ["threat", "vulnerability", "safety", "attack", "セキュリティ", "脆弱性"],
            "environment": ["climate", "pollution", "sustainability", "ecology", "環境", "気候"],
            "law_governance": ["law", "regulation", "compliance", "governance", "法", "規制", "ガバナンス"],
            "culture": ["culture", "norm", "value", "tradition", "文化", "価値観"],
        }
        perspective_lex = {
            "author": ["we", "our", "本研究", "我々"],
            "participant": ["patient", "user", "participant", "subject", "被験者", "利用者"],
            "system": ["model", "system", "algorithm", "agent", "手法", "モデル"],
            "institution": ["guideline", "policy", "regulation", "committee", "規制", "指針"],
            "practitioner": ["clinician", "engineer", "operator", "teacher", "医師", "技術者", "運用者"],
            "community": ["community", "citizen", "public", "stakeholder", "市民", "社会"],
            "industry": ["company", "enterprise", "product", "business", "企業", "産業"],
            "regulator": ["authority", "government", "ministry", "oversight", "政府", "当局"],
            "historian": ["historical", "archive", "chronicle", "history", "歴史", "史料"],
            "global_south": ["global south", "developing", "low-resource", "途上国", "低資源"],
        }
        opinion_lex = {
            "hypothesis": ["hypothesis", "仮説", "we hypothesize"],
            "interpretation": ["suggest", "interpret", "示唆", "解釈"],
            "recommendation": ["should", "recommend", "提言", "推奨"],
            "observation": ["observed", "found", "観察", "結果"],
        }

        def tag_with_conf(lex: dict[str, list[str]]) -> list[dict[str, Any]]:
            out = []
            for k, ws in lex.items():
                hits = sum(1 for w in ws if w in low)
                if hits > 0:
                    out.append({"tag": k, "confidence": round(min(1.0, 0.35 + hits * 0.2), 4), "hits": hits})
            return out

        paradigm_tags = tag_with_conf(paradigm_lex)
        category_tags = tag_with_conf(category_lex)
        perspective_tags = tag_with_conf(perspective_lex)
        opinion_tags = tag_with_conf(opinion_lex)

        sensory_hits = sum(1 for k in ["pain", "fatigue", "comfort", "discomfort", "痛み", "疲労", "感覚"] if k in low)
        action_hits = sum(1 for k in ["intervention", "manipulation", "operate", "procedure", "介入", "操作", "動作"] if k in low)
        env_hits = sum(1 for k in ["temperature", "touch", "noise", "visual", "environment", "温度", "接触", "環境"] if k in low)

        sent_n = max(1, len([p for p in re.split(r"[。.!?\n]+", t) if p.strip()]))
        para_n = max(1, len([p for p in re.split(r"\n\s*\n", t) if p.strip()]))

        return {
            "version": "spm-v1",
            "temporal": {
                "publication_time": pub_year,
                "subject_time": subject_year,
                "time_gap_policy": "no_auto_penalty_for_peer_review",
            },
            "paradigm": paradigm_tags,
            "category": category_tags,
            "perspective": perspective_tags,
            "opinion": opinion_tags,
            "embodied": {
                "policy": "sensory_action_environment_equal",
                "sensory_hits": sensory_hits,
                "action_hits": action_hits,
                "environment_hits": env_hits,
            },
            "hierarchy": {
                "micro_sentence_count": sent_n,
                "meso_paragraph_count": para_n,
                "macro_document": True,
            },
        }

    def _spml_from_spm(
        self,
        spm: dict[str, Any],
        result: dict[str, Any],
        html_pipe: dict[str, Any],
        sweep: dict[str, Any],
        refs_count: float,
    ) -> dict[str, Any]:
        t = ((result.get("kq_payload") or {}).get("text") or "") if isinstance(result, dict) else ""
        if not t:
            t = ""

        compression_ratio = float(result.get("context_compression_ratio", 1.0) or 1.0)
        compression_loss = min(1.0, abs(1.0 - compression_ratio))
        hdec = ((result.get("reason") or {}).get("kq_hierarchical_decode") or {})
        continuity = float(hdec.get("continuity_factor", 0.5) or 0.5)
        decode_loss = 1.0 - max(0.0, min(1.0, continuity))
        semantic_fidelity_loss = self._clamp(compression_loss * 0.55 + decode_loss * 0.45)

        emb = spm.get("embodied") or {}
        embodied_signal_strength = self._clamp(
            min(1.0, float(emb.get("sensory_hits", 0)) / 3.0) * 0.34
            + min(1.0, float(emb.get("action_hits", 0)) / 3.0) * 0.33
            + min(1.0, float(emb.get("environment_hits", 0)) / 3.0) * 0.33
        )
        embodied_signal_loss = self._clamp(1.0 - embodied_signal_strength)

        temporal = spm.get("temporal") or {}
        temporal_detectability = 1.0 if (temporal.get("publication_time", 0) or temporal.get("subject_time", 0)) else 0.0
        paradigm_detectability = min(1.0, len(spm.get("paradigm") or []) / 2.0)
        temporal_paradigm_loss = self._clamp(1.0 - (temporal_detectability * 0.5 + paradigm_detectability * 0.5))

        stance_detectability = self._clamp(min(1.0, len(spm.get("opinion") or []) / 2.0) * 0.55 + min(1.0, len(spm.get("perspective") or []) / 3.0) * 0.45)
        stance_context_loss = self._clamp(1.0 - stance_detectability)

        html_hits = float((html_pipe or {}).get("html_hit_count", 0))
        pdf_target = float((sweep or {}).get("pdf_target", 1) or 1)
        text_target = float((sweep or {}).get("text_target", 1) or 1)
        pdf_read = float((sweep or {}).get("pdf_read_count", 0) or 0)
        text_read = float((sweep or {}).get("text_read_count", 0) or 0)
        read_cov = min(1.0, (pdf_read / max(1.0, pdf_target)) * 0.5 + (text_read / max(1.0, text_target)) * 0.5)
        grounding_strength = min(1.0, refs_count / 40.0) * 0.45 + min(1.0, html_hits / 12.0) * 0.25 + read_cov * 0.30
        evidence_grounding_loss = self._clamp(1.0 - grounding_strength)

        weights = {
            "semantic_fidelity_loss": 0.24,
            "embodied_signal_loss": 0.20,
            "temporal_paradigm_loss": 0.20,
            "stance_context_loss": 0.16,
            "evidence_grounding_loss": 0.20,
        }
        mapping_completeness_loss = self._clamp((temporal_paradigm_loss * 0.5 + stance_context_loss * 0.5))
        mapping_fidelity_loss = self._clamp((semantic_fidelity_loss * 0.5 + evidence_grounding_loss * 0.5))

        score = self._clamp(
            semantic_fidelity_loss * weights["semantic_fidelity_loss"]
            + embodied_signal_loss * weights["embodied_signal_loss"]
            + temporal_paradigm_loss * weights["temporal_paradigm_loss"]
            + stance_context_loss * weights["stance_context_loss"]
            + evidence_grounding_loss * weights["evidence_grounding_loss"]
        )
        if score <= 0.18:
            profile = "low-loss"
        elif score <= 0.35:
            profile = "controlled-loss"
        elif score <= 0.55:
            profile = "medium-loss"
        else:
            profile = "high-loss"

        return {
            "version": "spml-v1",
            "mode": "measured" if refs_count > 0 else "estimated",
            "score": round(score, 4),
            "profile": profile,
            "mapping_completeness_loss": round(mapping_completeness_loss, 4),
            "mapping_fidelity_loss": round(mapping_fidelity_loss, 4),
            "components": {
                "semantic_fidelity_loss": round(semantic_fidelity_loss, 4),
                "embodied_signal_loss": round(embodied_signal_loss, 4),
                "temporal_paradigm_loss": round(temporal_paradigm_loss, 4),
                "stance_context_loss": round(stance_context_loss, 4),
                "evidence_grounding_loss": round(evidence_grounding_loss, 4),
            },
            "weights": {k: round(v, 4) for k, v in weights.items()},
        }

    def _compute_translation_loss(
        self,
        text: str,
        result: dict[str, Any],
        paper_stats: dict[str, Any],
        html_pipe: dict[str, Any],
        sweep: dict[str, Any],
    ) -> dict[str, Any]:
        refs_count = float((paper_stats or {}).get("refs_count", 0))
        spm = self._spm_mapping(text, paper_stats)
        spml = self._spml_from_spm(spm, result, html_pipe, sweep, refs_count)

        source_layer = self._detect_layer_from_features(text)
        target_layer = "natural_language"
        html_hits = float((html_pipe or {}).get("html_hit_count", 0))
        confidence = self._clamp(0.45 + min(0.35, refs_count / 120.0) + min(0.20, html_hits / 20.0))

        tl = {
            "mode": spml.get("mode", "estimated"),
            "score": spml.get("score", 0.5),
            "profile": spml.get("profile", "medium-loss"),
            "anchor_retention_estimate": round(1.0 - float((spml.get("components") or {}).get("semantic_fidelity_loss", 0.5)), 4),
            "components": spml.get("components") or {},
            "weights": spml.get("weights") or {},
            "confidence": round(confidence, 4),
            "auto_detected_layers": {
                "source": source_layer,
                "target": target_layer,
                "paradigm_tags": [x.get("tag") for x in (spm.get("paradigm") or [])],
            },
            "temporal_axes": {
                "publication_time": (spm.get("temporal") or {}).get("publication_time", 0),
                "subject_time": (spm.get("temporal") or {}).get("subject_time", 0),
                "time_gap_policy": "no_auto_penalty_for_peer_review",
                "temporal_detectability": 1.0 if ((spm.get("temporal") or {}).get("publication_time", 0) or (spm.get("temporal") or {}).get("subject_time", 0)) else 0.0,
            },
            "embodied_axes": spm.get("embodied") or {},
            "coordinate_extraction": {
                "category_tags": [x.get("tag") for x in (spm.get("category") or [])],
                "paradigm_tags": [x.get("tag") for x in (spm.get("paradigm") or [])],
                "perspective_tags": [x.get("tag") for x in (spm.get("perspective") or [])],
                "opinion_tags": [x.get("tag") for x in (spm.get("opinion") or [])],
            },
            "spm_mapping": spm,
            "spml": spml,
        }
        return tl

    def verify(self, *args, **kwargs):
        r = super().verify(*args, **kwargs)
        if not isinstance(r, dict):
            return r

        text = ""
        if args:
            c = args[0]
            text = c.text if hasattr(c, "text") else str(c)
        elif "claim" in kwargs:
            c = kwargs.get("claim")
            text = c.text if hasattr(c, "text") else str(c)

        p = r.get("paper_stats") or {}
        htmlp = r.get("html_first_pipeline") or {}
        sweep = r.get("paper_read_sweep") or {}

        tl = self._compute_translation_loss(text, r, p, htmlp, sweep)
        mlc = self._check_multilayer_consistency(text)
        dpack = self._domain_solver_pack(text)
        complement = self._spm_solver_complement_link(tl.get("spm_mapping") or {})
        mini = self._mini_solver_parallel_pack(text, complement)
        bias = self._bias_detection(text, {**r, "paper_stats": p})
        htlf = self._htlf_loss_vector((tl.get("components") or {}), float(bias.get("risk_score", 0.0) or 0.0))

        # C: fixed schema + SPM/SPML native outputs
        r["translation_loss"] = tl
        r["kq_translation_loss"] = tl
        r["spm_mapping"] = tl.get("spm_mapping") or {}
        r["spml"] = tl.get("spml") or {}
        r["bias_detection"] = bias
        r["htlf_loss_vector"] = htlf
        r["kq_final_l8"] = self._l8_final_5axis(r, tl, htlf, bias, mlc)
        r["multi_layer_consistency"] = mlc
        r["kq_domain_solver_pack"] = dpack
        r["solver_complement_link"] = complement
        r["kq_parallel_mini_solvers"] = mini
        triadic = self._triadic_complement_matrix(r.get("spm_mapping") or {}, dpack, mini)
        r["triadic_complement_matrix"] = triadic
        adv_risk_now = float((self._adversarial_pretest_kq(text) or {}).get("risk_score", 0.0) or 0.0)
        r["orchestration_detail"] = self._orchestration_detail(triadic, mini, mlc, sweep, adv_risk_now)
        r["orchestration_history"] = self._append_orchestration_history(r["orchestration_detail"])
        r["solver_exposure_extended"] = self._solver_exposure_extended(dpack, mini, complement)
        r["why_this_solver_set"] = {
            "spm_driven": True,
            "domain": dpack.get("domain"),
            "complement_rationale": complement.get("rationale", []),
            "mini_activation_ratio": mini.get("activation_ratio", 0.0),
            "triadic_mode": triadic.get("recommended_mode"),
        }
        r["ks47_compatible_output"] = self._ks47_compatible_axis_output(
            text,
            r,
            p,
            htmlp,
            sweep,
            mlc,
            r["kq_final_l8"],
            dpack=dpack,
            spm=r.get("spm_mapping") or {},
            spml=r.get("spml") or {},
            complement=complement,
        )
        r["kq_solver_l1_l7"] = self._l1_l7_solver_visualization(text, r, p, htmlp, sweep, dpack, mlc, tl, mini)
        r["self_other_boundary"] = self._self_other_boundary(text, r, bias)
        r["creativity_detection"] = self._creativity_detection(text, mlc, htlf)
        r["inline_sentence_verify"] = self._inline_sentence_verify(text, tl, bias)
        r["adversarial_pretest"] = self._adversarial_pretest_kq(text)
        r["hardware_batch_layer"] = self._hardware_batch_layer()
        r["internal_calibration_e1_e7"] = self._internal_calibration_e1_e7(r, tl, bias)
        r["goal_report"] = self._goal_report(text, r, r["kq_final_l8"], r["inline_sentence_verify"])
        r["legacy_compatibility"] = {
            "ks_style_fields": [
                "translation_loss",
                "multi_layer_consistency",
                "auto_detected_layers",
                "ks47_compatible_output",
            ],
            "compat_mode": "kq-independent",
            "status": "enabled",
        }

        # D: loss-aware assertiveness gate
        loss_score = float(tl.get("score", 0.0) or 0.0)
        consistency_score = float(mlc.get("consistency_score", 0.5) or 0.5)
        bias_risk = float(bias.get("risk_score", 0.0) or 0.0)
        adv_risk = float((r.get("adversarial_pretest") or {}).get("risk_score", 0.0) or 0.0)
        spml_obj = r.get("spml") or {}
        completeness_loss = float(spml_obj.get("mapping_completeness_loss", 0.0) or 0.0)
        fidelity_loss = float(spml_obj.get("mapping_fidelity_loss", 0.0) or 0.0)
        assertive_allowed = (
            (loss_score <= 0.24)
            and (consistency_score >= 0.72)
            and (bias_risk <= 0.32)
            and (adv_risk <= 0.35)
            and (completeness_loss <= 0.42)
            and (fidelity_loss <= 0.46)
        )
        r["translation_loss_gate"] = {
            "enabled": True,
            "threshold": 0.24,
            "consistency_threshold": 0.72,
            "bias_threshold": 0.32,
            "adversarial_threshold": 0.35,
            "spml_completeness_threshold": 0.42,
            "spml_fidelity_threshold": 0.46,
            "assertive_allowed": assertive_allowed,
        }

        if not assertive_allowed:
            # suppress over-assertive outcomes
            cur = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
            capped = min(cur, 0.64)
            r["final_score"] = capped
            r["confidence"] = capped
            if r.get("verdict") in {"SUPPORT", "LEAN_SUPPORT"}:
                r["verdict"] = "UNCERTAIN"

        calib_score = float(((r.get("internal_calibration_e1_e7") or {}).get("final_calibrated_score", 0.5)) or 0.5)
        cur = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
        blended = self._clamp(cur * 0.88 + calib_score * 0.12)
        r["final_score"] = blended
        r["confidence"] = blended

        fw = r.get("fusion_weights") or {}
        fw["translation_loss_score"] = round(loss_score, 4)
        fw["translation_loss_penalty"] = round(min(0.10, loss_score * 0.12), 4)
        fw["calibration_score"] = round(calib_score, 4)
        fw["mini_solver_activation_ratio"] = float((mini or {}).get("activation_ratio", 0.0) or 0.0)
        fw["spml_completeness_loss"] = round(completeness_loss, 4)
        fw["spml_fidelity_loss"] = round(fidelity_loss, 4)
        fw["solver_complement_boost_sum"] = round(sum(float(v or 0.0) for v in ((complement.get("family_boost") or {}).values())), 4)
        r["fusion_weights"] = fw

        r["kq_revision"] = "02b-r18"
        r["model"] = self.SYSTEM_MODEL
        r["alias"] = self.ALIAS
        return r


KQ02b = Katala_Quantum_02b

__all__ = ["Katala_Quantum_02b", "KQ02b"]
