from __future__ import annotations

from io import BytesIO
from typing import Any


def _extract_with_pdfplumber(raw: bytes) -> tuple[str, str]:
    try:
        import pdfplumber  # type: ignore

        texts: list[str] = []
        with pdfplumber.open(BytesIO(raw)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    texts.append(t)
        out = "\n".join(texts).strip()
        return out, "pdfplumber"
    except Exception:
        return "", "pdfplumber"


def _extract_with_pypdf(raw: bytes) -> tuple[str, str]:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(raw))
        texts: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                texts.append(t)
        out = "\n".join(texts).strip()
        return out, "pypdf"
    except Exception:
        return "", "pypdf"


def extract_pdf_text_kq(raw: bytes) -> dict[str, Any]:
    """KQ-native PDF text extraction.

    Returns summary only (no persistent cache):
    { text, method, confidence, ok }
    """
    if not raw:
        return {"text": "", "method": "none", "confidence": 0.0, "ok": False}

    for fn in (_extract_with_pdfplumber, _extract_with_pypdf):
        text, method = fn(raw)
        if len((text or "").strip()) >= 120:
            conf = 0.84 if method == "pdfplumber" else 0.72
            return {
                "text": text,
                "method": method,
                "confidence": conf,
                "ok": True,
            }

    return {"text": "", "method": "fallback", "confidence": 0.0, "ok": False}
