from __future__ import annotations

from io import BytesIO
from typing import Any
import os
import shutil
import subprocess
import tempfile


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


def _extract_with_pymupdf(raw: bytes) -> tuple[str, str]:
    try:
        import fitz  # type: ignore

        doc = fitz.open(stream=raw, filetype="pdf")
        texts: list[str] = []
        for page in doc:
            t = page.get_text("text") or ""
            if t.strip():
                texts.append(t)
        out = "\n".join(texts).strip()
        return out, "pymupdf"
    except Exception:
        return "", "pymupdf"


def _extract_with_pdftotext(raw: bytes) -> tuple[str, str]:
    if shutil.which("pdftotext") is None:
        return "", "pdftotext"
    tmp_pdf = None
    tmp_txt = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(raw)
            tmp_pdf = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as t:
            tmp_txt = t.name
        subprocess.run(["pdftotext", "-layout", tmp_pdf, tmp_txt], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if tmp_txt and os.path.exists(tmp_txt):
            with open(tmp_txt, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read().strip(), "pdftotext"
        return "", "pdftotext"
    except Exception:
        return "", "pdftotext"
    finally:
        for p in [tmp_pdf, tmp_txt]:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


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

    for fn in (_extract_with_pymupdf, _extract_with_pdftotext, _extract_with_pdfplumber, _extract_with_pypdf):
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
