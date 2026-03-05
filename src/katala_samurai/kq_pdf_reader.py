from __future__ import annotations

from io import BytesIO
from typing import Any
import os
import re
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


def _ocr_with_tesseract(raw: bytes) -> tuple[str, dict[str, Any]]:
    """OCR fallback for image-scan PDFs.

    Requires `pdftoppm` and `tesseract` binaries.
    Uses ephemeral temp files only.
    """
    if shutil.which("pdftoppm") is None or shutil.which("tesseract") is None:
        return "", {"ocr_used": False, "reason": "missing_bin"}

    tmp_pdf = None
    tmp_dir = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(raw)
            tmp_pdf = f.name
        tmp_dir = tempfile.mkdtemp(prefix="kq-pdf-ocr-")
        prefix = os.path.join(tmp_dir, "page")

        # rasterize PDF pages
        subprocess.run(["pdftoppm", "-gray", "-r", "220", tmp_pdf, prefix, "-png"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pages = sorted([os.path.join(tmp_dir, x) for x in os.listdir(tmp_dir) if re.match(r"^page-\d+\.png$", x)])
        if not pages:
            return "", {"ocr_used": False, "reason": "no_raster_pages"}

        langs = os.getenv("KQ_OCR_LANGS", "eng+jpn").strip() or "eng"
        out_pages: list[str] = []
        confs: list[float] = []
        for img in pages:
            proc = subprocess.run(
                ["tesseract", img, "stdout", "-l", langs, "--psm", "6", "tsv"],
                capture_output=True,
                text=True,
                check=False,
            )
            tsv = proc.stdout or ""
            # basic TSV reconstruction from recognized words
            words = []
            for ln in tsv.splitlines()[1:]:
                cols = ln.split("\t")
                if len(cols) >= 12:
                    txt = cols[11].strip()
                    if txt:
                        words.append(txt)
                    try:
                        cf = float(cols[10])
                        if cf >= 0:
                            confs.append(cf)
                    except Exception:
                        pass
            out_pages.append(" ".join(words))

        text = "\n".join([p for p in out_pages if p.strip()]).strip()
        mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.45
        return text, {
            "ocr_used": True,
            "engine": "tesseract",
            "pages": len(pages),
            "ocr_confidence": round(max(0.0, min(1.0, mean_conf)), 4),
            "langs": langs,
        }
    except Exception:
        return "", {"ocr_used": False, "reason": "ocr_error"}
    finally:
        try:
            if tmp_pdf and os.path.exists(tmp_pdf):
                os.unlink(tmp_pdf)
        except Exception:
            pass
        try:
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def extract_pdf_text_kq(raw: bytes) -> dict[str, Any]:
    """KQ-native PDF text extraction.

    Returns summary only (no persistent cache):
    { text, method, confidence, ok, ocr_used, ... }
    """
    if not raw:
        return {"text": "", "method": "none", "confidence": 0.0, "ok": False, "ocr_used": False}

    for fn in (_extract_with_pymupdf, _extract_with_pdftotext, _extract_with_pdfplumber, _extract_with_pypdf):
        text, method = fn(raw)
        if len((text or "").strip()) >= 120:
            conf = 0.84 if method == "pdfplumber" else 0.72
            return {
                "text": text,
                "method": method,
                "confidence": conf,
                "ok": True,
                "ocr_used": False,
            }

    # OCR fallback for scan/image PDFs
    ocr_text, ocr_meta = _ocr_with_tesseract(raw)
    if len((ocr_text or "").strip()) >= 80:
        return {
            "text": ocr_text,
            "method": "ocr-fallback",
            "confidence": float(ocr_meta.get("ocr_confidence", 0.45)),
            "ok": True,
            **ocr_meta,
        }

    return {"text": "", "method": "fallback", "confidence": 0.0, "ok": False, **ocr_meta}
