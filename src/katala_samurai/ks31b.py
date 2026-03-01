"""
KS31b — Katala Samurai 31b: Weighted Consensus Voting.

Extended KS31a with confidence-weighted voting: each solver's vote
is scaled by its historical accuracy and domain relevance.

Lineage: KS31a (majority) → KS31b (weighted) → KS31c (disagreement)
         → KS31d (calibration) → KS31e (full quality)

Superseded by KS31e. Backward-compatible wrapper.

Design: Youta Hilono, 2026-02-28
"""

from __future__ import annotations

from .ks31e import KS31e
from .ks31e import *  # noqa: F401,F403


class KS31b(KS31e):
    """Backward-compatible alias for KS31e.

    KS31b added weighted voting. Consolidated into KS31e.

    Usage:
        from katala_samurai.ks31b import KS31b
        ks = KS31b()
        result = ks.verify(claim)
    """

    VERSION = "KS31b→KS31e"

    def __init__(self, **kwargs):
        """Initialize KS31b (delegates to KS31e).

        Args:
            **kwargs: Passed to KS31e.__init__().
        """
        super().__init__(**kwargs)


__all__ = ["KS31b"]
