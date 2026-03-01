"""
KS31a — Katala Samurai 31a: Initial Multi-Solver Consensus.

First iteration of the consensus engine. Introduced basic majority
voting across all solver outputs to produce a single verdict.

Lineage: KS31a → KS31b (weighted) → KS31c (disagreement classification)
         → KS31d (cross-solver calibration) → KS31e (full quality integration)

Superseded by KS31e. This module provides a backward-compatible
wrapper class that delegates to KS31e while preserving the original
interface contract.

Design: Youta Hilono, 2026-02-28
"""

from __future__ import annotations

from .ks31e import KS31e
from .ks31e import *  # noqa: F401,F403


class KS31a(KS31e):
    """Backward-compatible alias for KS31e.

    KS31a introduced basic majority voting. All functionality
    has been consolidated into KS31e. This class exists solely
    for import compatibility with older code that references KS31a.

    Usage:
        from katala_samurai.ks31a import KS31a
        ks = KS31a()
        result = ks.verify(claim)
    """

    VERSION = "KS31a→KS31e"

    def __init__(self, **kwargs):
        """Initialize KS31a (delegates to KS31e).

        Args:
            **kwargs: Passed to KS31e.__init__().
        """
        super().__init__(**kwargs)


__all__ = ["KS31a"]
