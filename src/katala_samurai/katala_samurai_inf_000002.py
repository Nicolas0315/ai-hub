"""
Katala_Samurai_inf_000002 (KSi2)
[KSi]シリーズを使用

KSi1直系後継: デバッグ/比較/フォールバック向けの古典通常経路モデル。
"""
from __future__ import annotations

from .katala_samurai_inf_000001 import Katala_Samurai_inf_000001


class Katala_Samurai_inf_000002(Katala_Samurai_inf_000001):
    SYSTEM_MODEL: str = "Katala_Samurai_inf_000002"
    ALIAS: str = "KSi2"
    SERIES: str = "[KSi]シリーズを使用"

    def bridge_status(self) -> dict:
        s = super().bridge_status()
        s.update({
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "series": self.SERIES,
            "classical_normal_path": True,
            "debug_fallback": True,
        })
        return s


KSi2 = Katala_Samurai_inf_000002

__all__ = ["Katala_Samurai_inf_000002", "KSi2"]
