from __future__ import annotations
"""
KS35b — Katala Samurai 35b: Session Toxicity Guard

KS35a + ToxicityDetector — automatic contamination detection + purge.

Scans after every N verifications (default: every 5) for:
  - E1 confidence drift (manipulation)
  - E2 pattern poisoning (bias injection)
  - E3 chain corruption (echo chamber / instability)
  - Content contamination (prompt injection / grinding)

Auto-purges affected mechanisms when toxicity detected.

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks35a import KS35a, Claim
    from .stage_store import StageStore
    from .toxicity_detector import ToxicityDetector
except ImportError:
    from ks35a import KS35a, Claim
    from stage_store import StageStore
    from toxicity_detector import ToxicityDetector


class KS35b(KS35a):
    """KS35a + Session Toxicity Guard."""
    
    VERSION = "KS35b"
    
    def __init__(self, scan_interval: int = 5, auto_purge: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.toxicity = ToxicityDetector(auto_purge=auto_purge)
        self.scan_interval = scan_interval
        self._verify_count = 0
        self._verified_texts = []
        self._last_scan = None
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        # Track claim text for content contamination check
        claim_text = claim.text if hasattr(claim, 'text') else str(claim) if isinstance(claim, str) else ""
        if claim_text and not claim_text.endswith(".pdf"):
            self._verified_texts.append(claim_text)
        
        # Run KS35a verification
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        self._verify_count += 1
        
        # Periodic toxicity scan
        if self._verify_count % self.scan_interval == 0:
            scan_result = self._run_toxicity_scan()
            result["toxicity_scan"] = scan_result
            self._last_scan = scan_result
            
            if scan_result.get("toxic"):
                result["toxicity_alert"] = {
                    "contamination_detected": True,
                    "mechanisms_affected": scan_result["mechanisms_affected"],
                    "auto_purged": scan_result.get("purge_executed", False),
                    "max_severity": scan_result["max_severity"],
                }
        
        result["version"] = self.VERSION
        return result
    
    def _run_toxicity_scan(self) -> Dict:
        """Run toxicity scan on current session state."""
        # Extract E1/E2/E3 data from ephemeral session
        calibration = {}
        patterns = []
        insights = []
        
        if hasattr(self, 'session') and self.session:
            session = self.session
            if hasattr(session, '_e1_weights'):
                calibration = dict(getattr(session, '_e1_weights', {}))
            if hasattr(session, '_e2_patterns'):
                patterns = list(getattr(session, '_e2_patterns', []))
            if hasattr(session, '_e3_insights'):
                insights = list(getattr(session, '_e3_insights', []))
        
        return self.toxicity.scan(
            ephemeral_session=getattr(self, 'session', None),
            calibration_data=calibration,
            domain_patterns=patterns,
            chain_insights=insights,
            verified_texts=self._verified_texts[-50:],  # Last 50 claims
        )
    
    def force_scan(self) -> Dict:
        """Manually trigger toxicity scan."""
        scan = self._run_toxicity_scan()
        self._last_scan = scan
        return scan
    
    def toxicity_status(self) -> Dict:
        """Get current toxicity monitoring status."""
        return {
            "version": self.VERSION,
            "verifications": self._verify_count,
            "scan_interval": self.scan_interval,
            "last_scan": self._last_scan,
            "claims_tracked": len(self._verified_texts),
            "auto_purge": self.toxicity.auto_purge,
            "history": self.toxicity.get_history(),
        }


# Need this for type hints
from typing import Dict
