"""
Katala_Samurai_inf_000001

Enigma接続用の薄い統合レイヤ。
- KS最新版(現行: KS42c)を内部で利用
- Enigma側は本クラス名を固定エンドポイントとして参照可能
- しろくま接続ノードには依存しない
- 出力はinf-Coding adapterへ転送可能
- 連番ポリシー: 次回更新モデルは 000002 を採番
"""
from __future__ import annotations

from typing import Any

from .inf_coding_adapter import emit_bridge_output

_KS_BACKEND_ERROR: str | None = None
try:
    from .ks42c import KS42c as _KS42cBase
except Exception as e:  # optional heavy deps (e.g. z3) may be missing
    _KS42cBase = object  # type: ignore[assignment]
    _KS_BACKEND_ERROR = str(e)


class Katala_Samurai_inf_000001(_KS42cBase):
    """Enigma <-> Katala KS bridge (versioned)."""

    SYSTEM_NAME: str = "Katala_Samurai_inf"
    SYSTEM_MODEL: str = "Katala_Samurai_inf_000001"
    ENIGMA_BRIDGE: str = "enabled"
    ALIAS: str = "KSi1"

    # ① 多層ソルバー連鎖（軽量版）
    SOLVER_CHAIN_WEIGHTS: dict[str, float] = {
        "intent": 0.22,
        "constraint": 0.26,
        "execution_risk": 0.22,
        "consistency": 0.15,
        "integration": 0.15,
    }

    # ② モジュール相互依存（軽量版）
    MODULE_DEP_WEIGHTS: dict[str, float] = {
        "inf-coding": 0.18,
        "assist": 0.14,
        "router": 0.12,
        "adapter": 0.12,
        "ks42c": 0.12,
        "solver": 0.12,
        "l1": 0.10,
        "s28": 0.10,
    }

    def bridge_status(self) -> dict:
        return {
            "system": self.SYSTEM_NAME,
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "enigma_bridge": self.ENIGMA_BRIDGE,
            "ks_backend": getattr(self, "VERSION", "KS42c"),
            "degraded": _KS_BACKEND_ERROR is not None,
            "backend_error": _KS_BACKEND_ERROR,
            "multi_stage_reasoning": True,
            "module_dependency_integration": True,
        }

    @staticmethod
    def _norm(score: float) -> float:
        return max(0.0, min(1.0, score))

    def _run_solver_chain(self, text: str) -> dict[str, Any]:
        t = text.lower()
        scores = {
            "intent": 0.45 + (0.25 if any(k in t for k in ["implement", "実装", "改善", "最適化"]) else 0.0),
            "constraint": 0.4 + (0.3 if any(k in t for k in ["must", "必ず", "禁止", "rule", "order"]) else 0.0),
            "execution_risk": 0.55 - (0.18 if any(k in t for k in ["delete", "drop", "rm", "force"]) else 0.0),
            "consistency": 0.45 + (0.2 if any(k in t for k in ["same", "統一", "整合", "consistent"]) else 0.0),
            "integration": 0.4 + (0.25 if any(k in t for k in ["bridge", "adapter", "connect", "接続"]) else 0.0),
        }
        scores = {k: self._norm(v) for k, v in scores.items()}
        weighted = sum(scores[k] * self.SOLVER_CHAIN_WEIGHTS[k] for k in self.SOLVER_CHAIN_WEIGHTS)
        passed = sum(1 for v in scores.values() if v >= 0.6)
        return {
            "scores": scores,
            "weighted_score": round(self._norm(weighted), 3),
            "solvers_passed": f"{passed}/{len(scores)}",
        }

    def _module_dependency_score(self, text: str) -> dict[str, Any]:
        t = text.lower()
        hits: dict[str, float] = {}
        for k, w in self.MODULE_DEP_WEIGHTS.items():
            if k in t:
                hits[k] = w

        base = sum(hits.values())
        # cross-module bonus (相互依存を明示的に評価)
        bonus = 0.0
        if "inf-coding" in hits and "assist" in hits:
            bonus += 0.08
        if "router" in hits and "adapter" in hits:
            bonus += 0.08
        if ("ks42c" in hits or "solver" in hits) and ("l1" in hits or "s28" in hits):
            bonus += 0.08

        score = self._norm(0.35 + base + bonus)
        return {
            "hits": sorted(hits.keys()),
            "score": round(score, 3),
            "bonus": round(bonus, 3),
        }

    def _enhanced_fallback_verify(self, claim: Any) -> dict[str, Any]:
        text = claim.text if hasattr(claim, "text") else str(claim)
        t = text.lower()

        base = 0.5
        notes: list[str] = []
        if "stateless" in t:
            base += 0.08
            notes.append("stateless policy detected")
        if "order" in t and "assist" in t:
            base += 0.08
            notes.append("order/assist control path detected")
        if "rust" in t:
            base += 0.05
            notes.append("rust integration intent detected")

        chain = self._run_solver_chain(text)
        dep = self._module_dependency_score(text)

        final = self._norm(base * 0.45 + chain["weighted_score"] * 0.35 + dep["score"] * 0.20)
        verdict = "SUPPORT" if final >= 0.82 else ("LEAN_SUPPORT" if final >= 0.68 else "UNCERTAIN")

        return {
            "verdict": verdict,
            "confidence": round(final, 3),
            "final_score": round(final, 3),
            "solvers_passed": chain["solvers_passed"],
            "mode": "fallback-no-ks42c",
            "notes": notes,
            "ksi1_chain": chain,
            "module_dependency": dep,
        }

    def _augment_full_result(self, claim: Any, result: dict[str, Any]) -> dict[str, Any]:
        text = claim.text if hasattr(claim, "text") else str(claim)
        chain = self._run_solver_chain(text)
        dep = self._module_dependency_score(text)

        ks_score = float(result.get("final_score", result.get("confidence", 0.5)) or 0.5)
        fused = self._norm(ks_score * 0.78 + chain["weighted_score"] * 0.14 + dep["score"] * 0.08)
        result["ksi1_chain"] = chain
        result["module_dependency"] = dep
        result["ksi1_fused_score"] = round(fused, 3)

        # KS本体を尊重しつつ、情報として補助スコアを露出
        result.setdefault("confidence", round(fused, 3))
        return result

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if _KS_BACKEND_ERROR is None and hasattr(super(), "verify"):
            result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
            if isinstance(result, dict):
                result = self._augment_full_result(claim, result)
        else:
            result = self._enhanced_fallback_verify(claim)

        if isinstance(result, dict):
            emit_bridge_output(self.SYSTEM_MODEL, {
                "alias": self.ALIAS,
                "bridge_status": self.bridge_status(),
                "verdict": result.get("verdict"),
                "final_score": result.get("final_score"),
                "confidence": result.get("confidence"),
                "solvers_passed": result.get("solvers_passed"),
                "mode": result.get("mode", "ks42c"),
                "ksi1_fused_score": result.get("ksi1_fused_score"),
                "module_hits": (result.get("module_dependency") or {}).get("hits", []),
            })
        return result


# Alias
KSi1 = Katala_Samurai_inf_000001


__all__ = ["Katala_Samurai_inf_000001", "KSi1"]
