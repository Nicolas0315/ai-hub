"""
KS31c — Katala Samurai 31c: Disagreement Classification.

Extended KS31b with 4-type disagreement taxonomy:
  1. data_gap: Missing evidence → collect more data
  2. epistemic: Interpretation difference → Bayesian update
  3. framework (Kuhnian): Paradigm clash → cannot resolve by data alone
  4. principled (Quinean): Underdetermination → multiple valid theories

Lineage: KS31a → KS31b → KS31c (disagreement) → KS31d → KS31e

Superseded by KS31e. Backward-compatible wrapper.

Design: Youta Hilono, 2026-02-28
"""

from __future__ import annotations

from .ks31e import KS31e
from .ks31e import *  # noqa: F401,F403


class KS31c(KS31e):
    """Backward-compatible alias for KS31e.

    KS31c introduced disagreement classification (4 types).
    Consolidated into KS31e.

    Usage:
        from katala_samurai.ks31c import KS31c
        ks = KS31c()
        result = ks.verify(claim)
    """

    VERSION = "KS31c→KS31e"

    def __init__(self, **kwargs):
        """Initialize KS31c (delegates to KS31e).

        Args:
            **kwargs: Passed to KS31e.__init__().
        """
        super().__init__(**kwargs)


__all__ = ["KS31c"]
