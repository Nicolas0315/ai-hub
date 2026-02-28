"""
KS35c — Katala Samurai 35c: Visual Output + ArtSearch Fallback

KS35b + two minor upgrades:
  1) Result Visualizer: auto-generate PNG charts instead of text tables
  2) ArtSearch Layer: YouTube/Spotify/SoundCloud/Pixiv search (FALLBACK ONLY)

ArtSearch is sandboxed — results are isolated, never fed back into L1-L7.
Contamination minimized by design.

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks35b import KS35b, Claim
    from .stage_store import StageStore
    from .result_visualizer import render_verdict, render_comparison
    from .art_search import art_search
except ImportError:
    from ks35b import KS35b, Claim
    from stage_store import StageStore
    from result_visualizer import render_verdict, render_comparison
    from art_search import art_search

from typing import Dict, Any, List, Optional, Union
from pathlib import Path


class KS35c(KS35b):
    """KS35b + Visual Output + ArtSearch Fallback."""
    
    VERSION = "KS35c"
    
    def __init__(self, visual_output: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.visual_output = visual_output
        self._results_cache = []
    
    def verify(self, claim, store=None, skip_s28=True, render=None, **kwargs):
        """Verify with optional auto-visualization.
        
        Args:
            render: None (auto), True (force PNG), False (no PNG), or str (output path).
        """
        if store is None:
            store = StageStore()
        
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        # Cache for comparison renders
        if isinstance(result, dict):
            claim_text = claim.text if hasattr(claim, 'text') else str(claim) if isinstance(claim, str) else ""
            result["claim"] = claim_text[:100]
            self._results_cache.append(result)
            if len(self._results_cache) > 20:
                self._results_cache = self._results_cache[-20:]
        
        # Auto-render if enabled
        should_render = render if render is not None else self.visual_output
        if should_render and isinstance(result, dict):
            try:
                output_path = render if isinstance(render, str) else None
                png_path = render_verdict(result, output_path)
                result["visualization"] = png_path
            except Exception as e:
                result["visualization"] = f"render_failed: {str(e)[:100]}"
        
        result["version"] = self.VERSION
        return result
    
    def render_history(self, output_path: Optional[str] = None) -> str:
        """Render comparison chart of all cached verification results."""
        if not self._results_cache:
            return ""
        return render_comparison(self._results_cache, output_path)
    
    def search_art(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """ArtSearch — fallback media search.
        
        SANDBOXED: Results are never fed back into verification pipeline.
        Use for reference/context only.
        """
        result = art_search(query, platforms, max_results)
        result["_sandboxed"] = True
        result["_warning"] = "ArtSearch results are FALLBACK ONLY — not fed into L1-L7 verification"
        return result
