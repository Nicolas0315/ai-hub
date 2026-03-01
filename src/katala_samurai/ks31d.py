"""
KS31d — Katala Samurai 31d: Cross-Solver Calibration.

Extended KS31c with cross-solver calibration: normalizes solver
outputs to a common scale by tracking per-solver bias and variance
across historical verification runs.

Lineage: KS31a → KS31b → KS31c → KS31d (calibration) → KS31e

Superseded by KS31e. Backward-compatible wrapper.

Design: Youta Hilono, 2026-02-28
"""

from __future__ import annotations

from .ks31e import KS31e
from .ks31e import *  # noqa: F401,F403


class KS31d(KS31e):
    """Backward-compatible alias for KS31e.

    KS31d added cross-solver calibration. Consolidated into KS31e.

    Usage:
        from katala_samurai.ks31d import KS31d
        ks = KS31d()
        result = ks.verify(claim)
    """

    VERSION = "KS31d→KS31e"

    def __init__(self, **kwargs):
        """Initialize KS31d (delegates to KS31e).

        Args:
            **kwargs: Passed to KS31e.__init__().
        """
        super().__init__(**kwargs)


__all__ = ["KS31d"]
