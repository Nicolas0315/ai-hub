"""
KS33c — Katala Samurai 33c: PDF Direct Verification

KS33b + PDF Reader (Mode A: pdfplumber, Mode B: OCR fallback).
verify() now accepts str (text claim), Path (PDF file), or Claim object.

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os
from pathlib import Path
from typing import Union, Dict, Any, Optional

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks33b import KS33b, Claim
    from .pdf_reader import extract_claims, verify_pdf
    from .stage_store import StageStore
except ImportError:
    from ks33b import KS33b, Claim
    from pdf_reader import extract_claims, verify_pdf
    from stage_store import StageStore


class KS33c(KS33b):
    """KS33b + PDF Direct Verification.
    
    New capabilities:
      - verify() accepts file path → auto-extracts claims from PDF
      - verify_pdf() batch-verifies all claims in a PDF
      - Supports digital PDFs (Mode A) and scanned PDFs with OCR (Mode B)
    """
    
    VERSION = "KS33c"
    
    def __init__(self, use_ocr: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.use_ocr = use_ocr
    
    def verify(
        self,
        claim: Union[str, Path, Claim],
        store: Optional[StageStore] = None,
        skip_s28: bool = True,
        pdf_mode: str = "sentences",
        max_claims: int = 20,
        **kwargs,
    ) -> Union[Dict[str, Any], list]:
        """Verify a claim or all claims from a PDF.
        
        Args:
            claim: Text string, Path to PDF, or Claim object.
            pdf_mode: "sentences" or "paragraphs" (only for PDF input).
            max_claims: Max claims to extract from PDF.
        
        Returns:
            Single result dict for text/Claim input.
            List of result dicts for PDF input.
        """
        # Detect PDF input
        if isinstance(claim, (str, Path)):
            path = Path(claim)
            if path.suffix.lower() == ".pdf" and path.exists():
                return self._verify_pdf(
                    str(path), mode=pdf_mode, max_claims=max_claims,
                    store=store, skip_s28=skip_s28, **kwargs,
                )
        
        # Normal claim verification (delegate to KS33b)
        return super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
    
    def _verify_pdf(
        self, pdf_path: str, mode: str = "sentences",
        max_claims: int = 20, **verify_kwargs,
    ) -> Dict[str, Any]:
        """Verify all claims extracted from a PDF."""
        return verify_pdf(
            pdf_path, verifier=self, mode=mode,
            use_ocr=self.use_ocr, max_claims=max_claims,
            **verify_kwargs,
        )
    
    def extract_only(
        self, pdf_path: str, mode: str = "sentences", max_claims: int = 100,
    ) -> Dict[str, Any]:
        """Extract claims from PDF without verification (preview)."""
        return extract_claims(
            pdf_path, mode=mode, use_ocr=self.use_ocr, max_claims=max_claims,
        )
