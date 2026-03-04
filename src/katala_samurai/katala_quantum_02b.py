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
from typing import Any

from .katala_quantum_02a import Katala_Quantum_02a

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
        novelty = sum(1 for k in novelty_tokens if k in t)
        consistency = float((mlc or {}).get("consistency_score", 0.5) or 0.5)
        qualia_loss = float((htlf or {}).get("R_qualia", 0.5) or 0.5)
        score = self._clamp(0.35 + min(0.35, novelty * 0.08) + consistency * 0.25 - qualia_loss * 0.2)
        return {
            "score": round(score, 4),
            "novelty_hits": novelty,
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
            "score": round(self._clamp(float((dpack or {}).get("activation_ratio", 0.0) or 0.0) + 0.3), 4),
            "verdict": "PASS",
            "subsolvers": dpack,
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
        # HTLF-like 6-axis decomposition (0..1, higher = worse loss)
        r_struct = min(1.0, c.get("compression_loss", 0.0) * 0.7 + c.get("decode_consistency_loss", 0.0) * 0.3)
        r_context = min(1.0, c.get("citation_grounding_loss", 0.0) * 0.65 + c.get("readability_loss", 0.0) * 0.35)
        r_qualia = min(1.0, c.get("cross_lang_loss", 0.0) * 0.5 + c.get("compression_loss", 0.0) * 0.2 + bias_risk * 0.3)
        r_cultural = min(1.0, c.get("cross_lang_loss", 0.0) * 0.7 + bias_risk * 0.3)
        r_paradigm = min(1.0, c.get("citation_grounding_loss", 0.0) * 0.6 + bias_risk * 0.4)
        r_temporal = min(1.0, c.get("readability_loss", 0.0) * 0.6 + c.get("decode_consistency_loss", 0.0) * 0.4)
        return {
            "R_struct": round(r_struct, 4),
            "R_context": round(r_context, 4),
            "R_qualia": round(r_qualia, 4),
            "R_cultural": round(r_cultural, 4),
            "R_paradigm": round(r_paradigm, 4),
            "R_temporal": round(r_temporal, 4),
        }

    def _compute_translation_loss(
        self,
        text: str,
        result: dict[str, Any],
        paper_stats: dict[str, Any],
        html_pipe: dict[str, Any],
        sweep: dict[str, Any],
    ) -> dict[str, Any]:
        # A) compression loss (KQ context compression proxy)
        compression_ratio = float(result.get("context_compression_ratio", 1.0) or 1.0)
        compression_loss = min(1.0, abs(1.0 - compression_ratio))

        # B) citation grounding loss (refs + html fulltext hit quality)
        refs_count = float((paper_stats or {}).get("refs_count", 0))
        html_hits = float((html_pipe or {}).get("html_hit_count", 0))
        grounding_strength = min(1.0, refs_count / 40.0) * 0.6 + min(1.0, html_hits / 12.0) * 0.4
        citation_grounding_loss = 1.0 - grounding_strength

        # C) cross-language loss (ported, estimated mode)
        has_cjk = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text or ""))
        has_latin = bool(re.search(r"[A-Za-z]", text or ""))
        if has_cjk and has_latin:
            # SAOT-like reduction from pretranslation baseline
            cross_lang_loss = max(0.0, PRETRANSLATION_ACCURACY_LOSS_PCT / 100.0 * (1.0 - SAOT_ANCHOR_RETENTION_TARGET))
        elif has_cjk or has_latin:
            cross_lang_loss = 0.03
        else:
            cross_lang_loss = 0.08

        # D) decode consistency loss from hierarchical continuity proxy
        hdec = ((result.get("reason") or {}).get("kq_hierarchical_decode") or {})
        continuity = float(hdec.get("continuity_factor", 0.5) or 0.5)
        decode_consistency_loss = 1.0 - max(0.0, min(1.0, continuity))

        # E) readability execution loss from sweep
        pdf_target = float((sweep or {}).get("pdf_target", 1) or 1)
        text_target = float((sweep or {}).get("text_target", 1) or 1)
        pdf_read = float((sweep or {}).get("pdf_read_count", 0) or 0)
        text_read = float((sweep or {}).get("text_read_count", 0) or 0)
        read_cov = min(1.0, (pdf_read / max(1.0, pdf_target)) * 0.5 + (text_read / max(1.0, text_target)) * 0.5)
        readability_loss = 1.0 - read_cov

        # Weighted aggregate (KS-like measured/estimated hybrid)
        score = self._clamp(
            compression_loss * 0.22
            + citation_grounding_loss * 0.30
            + cross_lang_loss * 0.16
            + decode_consistency_loss * 0.18
            + readability_loss * 0.14
        )

        source_layer = self._detect_layer_from_features(text)
        target_layer = "natural_language"

        # confidence: more refs and html hits => higher confidence in measured estimate
        confidence = self._clamp(0.45 + min(0.35, refs_count / 120.0) + min(0.20, html_hits / 20.0))

        if score <= 0.18:
            profile = "low-loss"
        elif score <= 0.35:
            profile = "controlled-loss"
        elif score <= 0.55:
            profile = "medium-loss"
        else:
            profile = "high-loss"

        return {
            "mode": "measured" if refs_count > 0 else "estimated",
            "score": round(score, 4),
            "profile": profile,
            "anchor_retention_estimate": round(1.0 - cross_lang_loss, 4),
            "components": {
                "compression_loss": round(compression_loss, 4),
                "citation_grounding_loss": round(citation_grounding_loss, 4),
                "cross_lang_loss": round(cross_lang_loss, 4),
                "decode_consistency_loss": round(decode_consistency_loss, 4),
                "readability_loss": round(readability_loss, 4),
            },
            "confidence": round(confidence, 4),
            "auto_detected_layers": {
                "source": source_layer,
                "target": target_layer,
            },
        }

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
        bias = self._bias_detection(text, {**r, "paper_stats": p})
        htlf = self._htlf_loss_vector((tl.get("components") or {}), float(bias.get("risk_score", 0.0) or 0.0))

        # C: fixed schema
        r["translation_loss"] = tl
        r["kq_translation_loss"] = tl
        r["bias_detection"] = bias
        r["htlf_loss_vector"] = htlf
        r["kq_final_l8"] = self._l8_final_5axis(r, tl, htlf, bias, mlc)
        r["multi_layer_consistency"] = mlc
        r["kq_domain_solver_pack"] = dpack
        r["kq_solver_l1_l7"] = self._l1_l7_solver_visualization(text, r, p, htmlp, sweep, dpack, mlc, tl)
        r["self_other_boundary"] = self._self_other_boundary(text, r, bias)
        r["creativity_detection"] = self._creativity_detection(text, mlc, htlf)
        r["inline_sentence_verify"] = self._inline_sentence_verify(text, tl, bias)
        r["adversarial_pretest"] = self._adversarial_pretest_kq(text)
        r["hardware_batch_layer"] = self._hardware_batch_layer()
        r["goal_report"] = self._goal_report(text, r, r["kq_final_l8"], r["inline_sentence_verify"])
        r["legacy_compatibility"] = {
            "ks_style_fields": [
                "translation_loss",
                "multi_layer_consistency",
                "auto_detected_layers",
            ],
            "compat_mode": "kq-independent",
            "status": "enabled",
        }

        # D: loss-aware assertiveness gate
        loss_score = float(tl.get("score", 0.0) or 0.0)
        consistency_score = float(mlc.get("consistency_score", 0.5) or 0.5)
        bias_risk = float(bias.get("risk_score", 0.0) or 0.0)
        adv_risk = float((r.get("adversarial_pretest") or {}).get("risk_score", 0.0) or 0.0)
        assertive_allowed = (loss_score <= 0.24) and (consistency_score >= 0.72) and (bias_risk <= 0.32) and (adv_risk <= 0.35)
        r["translation_loss_gate"] = {
            "enabled": True,
            "threshold": 0.24,
            "consistency_threshold": 0.72,
            "bias_threshold": 0.32,
            "adversarial_threshold": 0.35,
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

        fw = r.get("fusion_weights") or {}
        fw["translation_loss_score"] = round(loss_score, 4)
        fw["translation_loss_penalty"] = round(min(0.10, loss_score * 0.12), 4)
        r["fusion_weights"] = fw

        r["kq_revision"] = "02b-r7"
        r["model"] = self.SYSTEM_MODEL
        r["alias"] = self.ALIAS
        return r


KQ02b = Katala_Quantum_02b

__all__ = ["Katala_Quantum_02b", "KQ02b"]
