"""
Katala_Samurai_inf_000001

Enigma接続用の薄い統合レイヤ。
- KS最新版(現行: KS42c)を内部で利用
- Enigma側は本クラス名を固定エンドポイントとして参照可能
- しろくま接続ノードには依存しない
"""
from __future__ import annotations

from .ks42c import KS42c


class Katala_Samurai_inf_000001(KS42c):
    """Enigma <-> Katala KS bridge (versioned)."""

    SYSTEM_NAME: str = "Katala_Samurai_inf"
    SYSTEM_MODEL: str = "Katala_Samurai_inf_000001"
    ENIGMA_BRIDGE: str = "enabled"

    def bridge_status(self) -> dict:
        return {
            "system": self.SYSTEM_NAME,
            "model": self.SYSTEM_MODEL,
            "enigma_bridge": self.ENIGMA_BRIDGE,
            "ks_backend": getattr(self, "VERSION", "KS42c"),
        }


__all__ = ["Katala_Samurai_inf_000001"]
