"""
Multimodal Input Engine for KS30
Converts images, diagrams, and equation images into structured text
descriptions that can be fed into the KS30 Claim pipeline.

Design: Youta Hilono
Implementation: Shirokuma

Architecture:
  Image -> Vision LLM -> Structured Description -> Claim(text=description)
  
Primary vision model: Gemini-3-Pro (Tokyo endpoint)
Fallback: local OCR (pytesseract)
"""

import base64
import json
import urllib.request
import urllib.parse
import os
import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MultimodalInput:
    """Represents a multimodal input (image, diagram, equation)."""
    input_type: str  # "image", "diagram", "equation", "table", "chart"
    source_path: str | None = None
    source_url: str | None = None
    source_base64: str | None = None
    mime_type: str = "image/png"
    description: str = ""
    structured_data: dict = field(default_factory=dict)
    confidence: float = 0.0
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.content_hash:
            raw = self.source_base64 or self.source_url or self.source_path or ""
            self.content_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_image_base64(source_path=None, source_url=None, source_base64=None):
    """Load image data as base64 string."""
    if source_base64:
        return source_base64
    if source_path and Path(source_path).exists():
        with open(source_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    if source_url:
        try:
            req = urllib.request.Request(source_url, headers={"User-Agent": "KS30/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return base64.b64encode(resp.read()).decode()
        except Exception:
            return None
    return None


def _detect_input_type(description):
    """Detect the type of visual input from its description."""
    lower = description.lower()
    if any(w in lower for w in ["equation", "formula", "integral", "derivative", "theorem"]):
        return "equation"
    if any(w in lower for w in ["diagram", "venn", "flowchart", "graph", "tree", "network"]):
        return "diagram"
    if any(w in lower for w in ["table", "row", "column", "header"]):
        return "table"
    if any(w in lower for w in ["chart", "bar", "pie", "scatter", "histogram", "plot"]):
        return "chart"
    return "image"


VISION_PROMPT = """Analyze this image for the KS30 verification system.

Provide a structured analysis:
1. DESCRIPTION: What does this image show? Be precise and factual.
2. TYPE: Is this an equation, diagram, table, chart, photograph, or other?
3. CLAIMS: List any factual claims or assertions visible in/implied by the image.
4. FORMAL_CONTENT: If mathematical/logical content is present, write it in formal notation.
5. CONTEXT: What academic domain(s) is this most relevant to?

Format your response as:
DESCRIPTION: ...
TYPE: ...
CLAIMS: [claim1] | [claim2] | ...
FORMAL_CONTENT: ...
CONTEXT: ..."""


def _query_gemini_vision(image_base64, mime_type="image/png", api_key=None, timeout=30):
    """Query Gemini Vision API for image analysis."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [
            {"text": VISION_PROMPT},
            {"inline_data": {"mime_type": mime_type, "data": image_base64}}
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def _parse_vision_response(response_text):
    """Parse structured vision API response."""
    result = {"description": "", "type": "image", "claims": [], "formal_content": "", "context": ""}
    if not response_text:
        return result
    
    current_field = None
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("DESCRIPTION:"):
            result["description"] = line[len("DESCRIPTION:"):].strip()
            current_field = "description"
        elif line.startswith("TYPE:"):
            result["type"] = line[len("TYPE:"):].strip().lower()
        elif line.startswith("CLAIMS:"):
            claims_str = line[len("CLAIMS:"):].strip()
            result["claims"] = [c.strip().strip("[]") for c in claims_str.split("|") if c.strip()]
        elif line.startswith("FORMAL_CONTENT:"):
            result["formal_content"] = line[len("FORMAL_CONTENT:"):].strip()
            current_field = "formal_content"
        elif line.startswith("CONTEXT:"):
            result["context"] = line[len("CONTEXT:"):].strip()
        elif current_field == "description" and line:
            result["description"] += " " + line
        elif current_field == "formal_content" and line:
            result["formal_content"] += " " + line
    return result


def _fallback_ocr(image_base64):
    """Fallback OCR using pytesseract."""
    try:
        import pytesseract
        from PIL import Image
        import io
        img_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip() if text.strip() else None
    except Exception:
        return None


def process_multimodal(source_path=None, source_url=None, source_base64=None,
                       mime_type="image/png", api_key=None):
    """Process a multimodal input and return structured description.
    
    Pipeline: load image -> Gemini Vision -> parse -> MultimodalInput
    Fallback: OCR -> basic text extraction
    """
    img_b64 = _load_image_base64(source_path, source_url, source_base64)
    if not img_b64:
        return MultimodalInput(input_type="error", description="Failed to load image")
    
    content_hash = hashlib.sha256(img_b64.encode()).hexdigest()[:16]
    
    # Try Gemini Vision
    vision_response = _query_gemini_vision(img_b64, mime_type, api_key)
    if vision_response:
        parsed = _parse_vision_response(vision_response)
        input_type = parsed["type"] or _detect_input_type(parsed["description"])
        desc_parts = [parsed["description"]]
        if parsed["formal_content"]:
            desc_parts.append(f"Formal: {parsed['formal_content']}")
        return MultimodalInput(
            input_type=input_type, source_path=source_path, source_url=source_url,
            mime_type=mime_type, description=" | ".join(desc_parts),
            structured_data=parsed, confidence=0.85, content_hash=content_hash)
    
    # Fallback: OCR
    ocr_text = _fallback_ocr(img_b64)
    if ocr_text:
        return MultimodalInput(
            input_type=_detect_input_type(ocr_text), source_path=source_path,
            source_url=source_url, mime_type=mime_type, description=ocr_text,
            structured_data={"description": ocr_text, "type": "ocr_fallback"},
            confidence=0.4, content_hash=content_hash)
    
    return MultimodalInput(input_type="unknown",
        description="Unable to process image (no vision API or OCR available)",
        confidence=0.0, content_hash=content_hash)


def multimodal_to_claim(mm_input, additional_evidence=None):
    """Convert MultimodalInput to KS30 Claim.
    
    Usage:
        mm = process_multimodal(source_url="https://example.com/diagram.png")
        claim = multimodal_to_claim(mm)
        result = LLMPipeline('gpt-5').run(claim)
    """
    from .ks29b import Claim
    
    evidence = []
    if mm_input.structured_data.get("claims"):
        evidence.extend(mm_input.structured_data["claims"])
    if additional_evidence:
        evidence.extend(additional_evidence)
    if mm_input.source_url:
        evidence.append(f"Source: {mm_input.source_url}")
    
    text = mm_input.description
    if not text or text.startswith("Unable") or text.startswith("Failed"):
        text = "Unprocessable multimodal input"
    
    claim = Claim(text=text, evidence=evidence)
    claim._multimodal = mm_input
    return claim
