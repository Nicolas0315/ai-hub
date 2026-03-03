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

from .ks42c import KS42c
from .inf_coding_adapter import emit_bridge_output


class Katala_Samurai_inf_000001(KS42c):
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
        }

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        if isinstance(result, dict):
            emit_bridge_output(self.SYSTEM_MODEL, {
                "alias": self.ALIAS,
                "bridge_status": self.bridge_status(),
                "verdict": result.get("verdict"),
                "final_score": result.get("final_score"),
                "confidence": result.get("confidence"),
                "solvers_passed": result.get("solvers_passed"),
            })
        return result


# Alias
KSi1 = Katala_Samurai_inf_000001


__all__ = ["Katala_Samurai_inf_000001", "KSi1"]
