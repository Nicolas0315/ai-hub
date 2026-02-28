"""
PDF Reader — Extract claims from PDF documents for KS verification.

Two modes:
  A) Text extraction (pdfplumber) — fast, works for most digital PDFs
  B) OCR fallback (pytesseract) — for scanned/image PDFs

Design: Youta Hilono, 2026-02-28
"""

import re
from pathlib import Path
from typing import List, Dict, Any


def extract_text_pdfplumber(pdf_path: str) -> str:
    """Mode A: Extract text using pdfplumber (fast, digital PDFs)."""
    import pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
            for table in page.extract_tables():
                for row in table:
                    if row:
                        pages.append(" | ".join(str(c) if c else "" for c in row))
    return "\n\n".join(pages)


def extract_text_ocr(pdf_path: str) -> str:
    """Mode B: OCR for scanned/image PDFs. Requires tesseract."""
    try:
        import pytesseract
        import pdfplumber
    except ImportError as e:
        return f"[OCR unavailable: {e}]"
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and len(text.strip()) > 20:
                pages.append(text)
                continue
            try:
                img = page.to_image(resolution=300)
                ocr_text = pytesseract.image_to_string(img.original, lang="eng+jpn")
                if ocr_text.strip():
                    pages.append(ocr_text)
            except Exception as e:
                pages.append(f"[OCR failed: {e}]")
    return "\n\n".join(pages)


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r'\s+', ' ', text).strip()
    parts = re.split(r'(?<=[.!?。！？])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 10]


def _split_paragraphs(text: str) -> List[str]:
    parts = re.split(r'\n\s*\n', text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def extract_claims(
    pdf_path: str,
    mode: str = "sentences",
    use_ocr: bool = False,
    max_claims: int = 100,
    min_length: int = 15,
) -> Dict[str, Any]:
    """Extract claim candidates from a PDF.
    
    Args:
        pdf_path: Path to PDF file.
        mode: "sentences" or "paragraphs".
        use_ocr: Force OCR mode (Mode B).
        max_claims: Cap on returned claims.
        min_length: Minimum char length per claim.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF: {pdf_path}")

    # Mode A first
    text = extract_text_pdfplumber(str(path))
    extraction_mode = "pdfplumber"

    # Auto-fallback to OCR if text extraction got almost nothing
    if len(text.strip()) < 50:
        try:
            ocr_text = extract_text_ocr(str(path))
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                extraction_mode = "ocr_auto" if not use_ocr else "ocr"
        except Exception:
            pass
    elif use_ocr:
        # Forced OCR
        ocr_text = extract_text_ocr(str(path))
        if ocr_text.strip():
            text = ocr_text
            extraction_mode = "ocr"

    # Split
    if mode == "sentences":
        claims = _split_sentences(text)
    elif mode == "paragraphs":
        claims = _split_paragraphs(text)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    claims = [c for c in claims if len(c) >= min_length][:max_claims]

    import pdfplumber
    with pdfplumber.open(str(path)) as pdf:
        metadata = {"pages": len(pdf.pages), "pdf_metadata": pdf.metadata or {}}

    return {
        "claims": claims,
        "claim_count": len(claims),
        "raw_text_length": len(text),
        "extraction_mode": extraction_mode,
        "metadata": metadata,
        "source": path.name,
    }


def verify_pdf(
    pdf_path: str,
    verifier=None,
    mode: str = "sentences",
    use_ocr: bool = False,
    max_claims: int = 20,
    **verify_kwargs,
) -> Dict[str, Any]:
    """Extract + verify all claims from a PDF.
    
    If verifier is None, creates KS33c instance.
    """
    extraction = extract_claims(pdf_path, mode=mode, use_ocr=use_ocr, max_claims=max_claims)

    if verifier is None:
        try:
            from .ks33c import KS33c
        except ImportError:
            from ks33c import KS33c
        verifier = KS33c()

    results = []
    for i, claim_text in enumerate(extraction["claims"]):
        try:
            result = verifier.verify(claim_text, **verify_kwargs)
            results.append({
                "index": i, "claim": claim_text[:200],
                "verdict": result.get("verdict", "ERROR"),
                "confidence": result.get("confidence", 0),
            })
        except Exception as e:
            results.append({
                "index": i, "claim": claim_text[:200],
                "verdict": "ERROR", "confidence": 0, "error": str(e)[:100],
            })

    verdicts = [r["verdict"] for r in results]
    avg_conf = sum(r["confidence"] for r in results) / max(len(results), 1)

    return {
        "source": extraction["source"],
        "extraction_mode": extraction["extraction_mode"],
        "pages": extraction["metadata"]["pages"],
        "claims_extracted": extraction["claim_count"],
        "claims_verified": len(results),
        "results": results,
        "summary": {
            "average_confidence": round(avg_conf, 4),
            "verdict_distribution": {v: verdicts.count(v) for v in set(verdicts)},
        },
    }
