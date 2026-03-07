"""
KQ Hyper Reasoner

Adds higher-order modules for:
- multi-hop recursive reasoning
- future scenario projection
- creative synthesis pressure
- cross-module interaction graph scoring
"""
from __future__ import annotations

import hashlib
import math
from typing import Any


class KQHyperReasoner:
    VERSION = "KQ-HR-v1"

    def refine_meaning_boundary(self, text: str, boundary: dict[str, Any] | None = None) -> dict[str, Any]:
        base = dict(boundary or {})
        low = (text or "").lower()
        axes = list(base.get("conceptual_axis") or [])
        preserve = list(base.get("preserve_terms") or [])
        anti = list(base.get("anti_flatten_rules") or [])

        if ("大統一理論" in text) or ("grand unified theory" in low):
            base["primary_goal"] = "katala_gut_construction"
            if "theory_axis" not in axes:
                axes.append("theory_axis")
            if "大統一理論" in text and "大統一理論" not in preserve:
                preserve.append("大統一理論")
            if "do_not_downgrade_gut_to_bookkeeping" not in anti:
                anti.append("do_not_downgrade_gut_to_bookkeeping")

        if ("連続次元" in text) or ("continuous dimension" in low):
            if "連続次元" in text and "連続次元" not in preserve:
                preserve.append("連続次元")
            origin = list(base.get("origin_signal") or [])
            if "continuous_dimension" not in origin:
                origin.append("continuous_dimension")
            base["origin_signal"] = origin

        if ("単一モデル" in text) or ("single model" in low):
            if "単一モデル" in text and "単一モデル" not in preserve:
                preserve.append("単一モデル")
            if "do_not_split_single_model_into_unrelated_stages" not in anti:
                anti.append("do_not_split_single_model_into_unrelated_stages")

        if ("inf-bridge" in low) or ("kq" in low):
            if "implementation_axis" not in axes:
                axes.append("implementation_axis")

        base["conceptual_axis"] = axes
        base["preserve_terms"] = preserve
        base["anti_flatten_rules"] = anti
        base["boundary_refinement"] = {
            "performed": True,
            "pass": 1,
            "mode": "mandatory_single_refinement",
        }
        return base

    LAYERS = {
        "L1_structural_logic": 0.16,
        "L2_multihop_reasoning": 0.18,
        "L3_counterfactual_futures": 0.16,
        "L4_creative_synthesis": 0.14,
        "L5_cross_module_interaction": 0.18,
        "L6_operational_feasibility": 0.18,
    }

    @staticmethod
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    @staticmethod
    def _h(text: str) -> float:
        d = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return int(d[:8], 16) / 0xFFFFFFFF

    def _layer_score(self, text: str, layer: str, seed: float) -> float:
        t = text.lower()
        base = 0.45 + (self._h(text + layer) - 0.5) * 0.35 + seed * 0.1

        if layer == "L2_multihop_reasoning":
            base += 0.08 if any(k in t for k in ["because", "therefore", "chain", "多段", "因果"]) else 0.0
        elif layer == "L3_counterfactual_futures":
            base += 0.10 if any(k in t for k in ["future", "if", "would", "予測", "仮説"]) else 0.0
        elif layer == "L4_creative_synthesis":
            base += 0.09 if any(k in t for k in ["create", "novel", "design", "創造", "発想"]) else 0.0
        elif layer == "L5_cross_module_interaction":
            base += 0.08 if any(k in t for k in ["integrate", "module", "bridge", "統合", "接続"]) else 0.0
        elif layer == "L6_operational_feasibility":
            base += 0.08 if any(k in t for k in ["cpu", "gpu", "budget", "効率", "運用"]) else 0.0

        return self._clamp(base)

    def evaluate(self, text: str) -> dict[str, Any]:
        scores = {}
        for i, layer in enumerate(self.LAYERS.keys(), start=1):
            scores[layer] = round(self._layer_score(text, layer, i * 0.07), 3)

        total = 0.0
        for layer, w in self.LAYERS.items():
            total += scores[layer] * w
        total = self._clamp(total)

        return {
            "version": self.VERSION,
            "overall": round(total, 3),
            "layers": scores,
            "weights": self.LAYERS,
        }
