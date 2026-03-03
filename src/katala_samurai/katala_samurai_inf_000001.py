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

    def bridge_status(self) -> dict:
        return {
            "system": self.SYSTEM_NAME,
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "enigma_bridge": self.ENIGMA_BRIDGE,
            "ks_backend": getattr(self, "VERSION", "KS42c"),
            "degraded": _KS_BACKEND_ERROR is not None,
            "backend_error": _KS_BACKEND_ERROR,
        }

    def _fallback_verify(self, claim: Any) -> dict:
        text = claim.text if hasattr(claim, "text") else str(claim)
        score = 0.55
        notes: list[str] = []

        if "stateless" in text.lower():
            score += 0.1
            notes.append("stateless policy detected")
        if "order" in text.lower() and "assist" in text.lower():
            score += 0.1
            notes.append("order/assist control path detected")
        if "rust" in text.lower():
            score += 0.05
            notes.append("rust integration intent detected")

        score = min(score, 0.9)
        verdict = "LEAN_SUPPORT" if score >= 0.7 else "UNCERTAIN"
        return {
            "verdict": verdict,
            "confidence": round(score, 3),
            "final_score": round(score, 3),
            "solvers_passed": "fallback/na",
            "mode": "fallback-no-ks42c",
            "notes": notes,
        }

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if _KS_BACKEND_ERROR is None and hasattr(super(), "verify"):
            result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        else:
            result = self._fallback_verify(claim)

        if isinstance(result, dict):
            emit_bridge_output(self.SYSTEM_MODEL, {
                "alias": self.ALIAS,
                "bridge_status": self.bridge_status(),
                "verdict": result.get("verdict"),
                "final_score": result.get("final_score"),
                "confidence": result.get("confidence"),
                "solvers_passed": result.get("solvers_passed"),
                "mode": result.get("mode", "ks42c"),
            })
        return result


# Alias
KSi1 = Katala_Samurai_inf_000001


__all__ = ["Katala_Samurai_inf_000001", "KSi1"]
