"""HTLF measurement pipeline package.

Exports are lazily resolved to avoid circular-import pressure when
`pipeline` and `ks_integration` are imported from KS40 modules.
"""

from __future__ import annotations

__all__ = ["LossVector", "HTLFResult", "HTLFScorer", "run_pipeline"]


def __getattr__(name: str):
    if name in {"LossVector", "run_pipeline"}:
        from .pipeline import LossVector, run_pipeline

        return {"LossVector": LossVector, "run_pipeline": run_pipeline}[name]
    if name in {"HTLFResult", "HTLFScorer"}:
        from .ks_integration import HTLFResult, HTLFScorer

        return {"HTLFResult": HTLFResult, "HTLFScorer": HTLFScorer}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
