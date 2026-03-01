"""
Image Understanding Engine — visual content verification pipeline.

Architecture:
  1. Image metadata extraction (EXIF, format, dimensions, color stats)
  2. Text-in-image detection (OCR-ready interface)
  3. Caption verification (does caption match image content?)
  4. Visual claim detection (claims ABOUT images: "this shows X")
  5. Manipulation detection (statistical anomaly patterns)
  6. CLIP-ready interface (plug in when model available)

What we CAN do without neural models:
  - Metadata consistency checking
  - Statistical analysis (color distribution, noise patterns)
  - Format/encoding verification
  - Text claim cross-referencing
  - Provenance tracking (EXIF dates, GPS, camera model)

Benchmark target: 画像理解 30%→65%

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import struct
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, BinaryIO

VERSION = "1.0.0"

# ── Optional image backends ──
try:
    from PIL import Image as PILImage, ExifTags
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

# Known image magic bytes
MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpeg',
    b'\x89PNG\r\n\x1a\n': 'png',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',  # RIFF....WEBP
    b'BM': 'bmp',
    b'\x00\x00\x00': 'heic',  # Simplified
}

# Suspicious EXIF patterns (manipulation indicators)
SUSPICIOUS_SOFTWARE = {
    "photoshop", "gimp", "paint.net", "affinity", "pixelmator",
    "lightroom", "capture one",
}

# Common manipulation artifacts
MANIPULATION_INDICATORS = [
    "error level analysis",
    "inconsistent shadows",
    "clone stamp",
    "content-aware fill",
]

# Visual claim patterns
VISUAL_CLAIM_PATTERNS = [
    re.compile(r"(?i)(?:this|the)\s+(?:image|photo|picture|screenshot)\s+(?:shows?|depicts?|proves?|demonstrates?)"),
    re.compile(r"(?i)(?:as\s+)?(?:seen|shown|visible|depicted)\s+in\s+(?:the\s+)?(?:image|photo|figure)"),
    re.compile(r"(?i)(?:photo|image)\s+(?:evidence|proof)\s+(?:of|that)"),
    re.compile(r"(?i)(?:according\s+to|based\s+on)\s+(?:this|the)\s+(?:image|photo|figure)"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ImageMetadata:
    """Extracted image metadata."""
    format: str = "unknown"
    width: int = 0
    height: int = 0
    file_size: int = 0
    color_depth: int = 0
    has_exif: bool = False
    camera_model: str = ""
    software: str = ""
    date_taken: str = ""
    gps_present: bool = False
    hash_md5: str = ""
    hash_sha256: str = ""


@dataclass
class ColorStats:
    """Statistical analysis of image colors."""
    mean_r: float = 0.0
    mean_g: float = 0.0
    mean_b: float = 0.0
    std_r: float = 0.0
    std_g: float = 0.0
    std_b: float = 0.0
    dominant_color: Tuple[int, int, int] = (0, 0, 0)
    unique_colors: int = 0
    entropy: float = 0.0


@dataclass
class ManipulationCheck:
    """Results of manipulation detection."""
    suspicious: bool = False
    confidence: float = 0.5
    indicators: List[str] = field(default_factory=list)
    software_edited: bool = False
    metadata_inconsistent: bool = False
    statistical_anomaly: bool = False


@dataclass
class ImageVerification:
    """Full image verification result."""
    metadata: ImageMetadata
    color_stats: Optional[ColorStats] = None
    manipulation: ManipulationCheck = field(default_factory=ManipulationCheck)
    caption_match: float = 0.0
    visual_claims: List[str] = field(default_factory=list)
    overall_score: float = 0.5
    verdict: str = "UNCERTAIN"
    version: str = VERSION


# ═══════════════════════════════════════════════════════════════════════════
# Image Metadata Extractor
# ═══════════════════════════════════════════════════════════════════════════

class MetadataExtractor:
    """Extract and analyze image metadata."""

    def extract_from_bytes(self, data: bytes) -> ImageMetadata:
        """Extract metadata from raw image bytes."""
        meta = ImageMetadata()
        meta.file_size = len(data)
        meta.hash_md5 = hashlib.md5(data).hexdigest()
        meta.hash_sha256 = hashlib.sha256(data).hexdigest()

        # Detect format from magic bytes
        for magic, fmt in MAGIC_BYTES.items():
            if data[:len(magic)] == magic:
                meta.format = fmt
                break

        # Try PIL for detailed metadata
        if _HAS_PIL:
            try:
                import io
                img = PILImage.open(io.BytesIO(data))
                meta.width, meta.height = img.size
                meta.format = img.format.lower() if img.format else meta.format
                if hasattr(img, 'mode'):
                    mode_depths = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32, "CMYK": 32}
                    meta.color_depth = mode_depths.get(img.mode, 0)

                # EXIF data
                exif_data = img._getexif() if hasattr(img, '_getexif') else None
                if exif_data:
                    meta.has_exif = True
                    exif_tags = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}
                    meta.camera_model = str(exif_tags.get('Model', ''))
                    meta.software = str(exif_tags.get('Software', ''))
                    meta.date_taken = str(exif_tags.get('DateTimeOriginal', ''))
                    meta.gps_present = 'GPSInfo' in exif_tags
            except Exception:
                pass
        else:
            # Basic dimension extraction for JPEG
            if meta.format == 'jpeg' and len(data) > 4:
                w, h = self._jpeg_dimensions(data)
                meta.width, meta.height = w, h
            elif meta.format == 'png' and len(data) > 24:
                meta.width = struct.unpack('>I', data[16:20])[0]
                meta.height = struct.unpack('>I', data[20:24])[0]

        return meta

    def extract_from_path(self, path: str) -> ImageMetadata:
        """Extract metadata from file path."""
        if not os.path.exists(path):
            return ImageMetadata()
        with open(path, 'rb') as f:
            return self.extract_from_bytes(f.read())

    def _jpeg_dimensions(self, data: bytes) -> Tuple[int, int]:
        """Extract dimensions from JPEG without PIL."""
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h = struct.unpack('>H', data[i + 5:i + 7])[0]
                w = struct.unpack('>H', data[i + 7:i + 9])[0]
                return w, h
            length = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + length
        return 0, 0


# ═══════════════════════════════════════════════════════════════════════════
# Color Analysis
# ═══════════════════════════════════════════════════════════════════════════

class ColorAnalyzer:
    """Statistical analysis of image pixel data."""

    def analyze(self, data: bytes) -> Optional[ColorStats]:
        """Analyze color statistics from image data."""
        if not _HAS_PIL or not _HAS_NUMPY:
            return None

        try:
            import io
            img = PILImage.open(io.BytesIO(data)).convert('RGB')
            pixels = np.array(img)

            stats = ColorStats()
            stats.mean_r = float(np.mean(pixels[:, :, 0]))
            stats.mean_g = float(np.mean(pixels[:, :, 1]))
            stats.mean_b = float(np.mean(pixels[:, :, 2]))
            stats.std_r = float(np.std(pixels[:, :, 0]))
            stats.std_g = float(np.std(pixels[:, :, 1]))
            stats.std_b = float(np.std(pixels[:, :, 2]))

            # Dominant color (mode of quantized colors)
            quantized = (pixels // 32) * 32
            flat = quantized.reshape(-1, 3)
            colors = [tuple(c) for c in flat[:10000]]  # Sample
            counter = Counter(colors)
            if counter:
                dom = counter.most_common(1)[0][0]
                stats.dominant_color = dom

            # Unique colors (sampled)
            sample = set(tuple(c) for c in flat[:5000])
            stats.unique_colors = len(sample)

            # Entropy (information content)
            hist = np.histogram(pixels.flatten(), bins=256, range=(0, 256))[0]
            hist = hist / hist.sum()
            hist = hist[hist > 0]
            stats.entropy = float(-np.sum(hist * np.log2(hist)))

            return stats
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════════════════
# Manipulation Detector
# ═══════════════════════════════════════════════════════════════════════════

class ManipulationDetector:
    """Detect potential image manipulation."""

    def detect(self, meta: ImageMetadata, color_stats: Optional[ColorStats] = None) -> ManipulationCheck:
        """Check for manipulation indicators."""
        check = ManipulationCheck()
        indicators = []

        # 1. Software editing check
        if meta.software:
            software_lower = meta.software.lower()
            for tool in SUSPICIOUS_SOFTWARE:
                if tool in software_lower:
                    indicators.append(f"Edited with: {meta.software}")
                    check.software_edited = True
                    break

        # 2. Metadata consistency
        if meta.has_exif:
            # Camera model but no date? Suspicious
            if meta.camera_model and not meta.date_taken:
                indicators.append("Camera model present but no date — possible metadata strip")
                check.metadata_inconsistent = True

            # Very new software but old date?
            if meta.date_taken and meta.software:
                # Simple heuristic check
                pass

        # 3. No EXIF at all (most real photos have some)
        if not meta.has_exif and meta.format == 'jpeg' and meta.file_size > 50000:
            indicators.append("JPEG >50KB with no EXIF data — possibly stripped")

        # 4. Statistical anomalies (if color data available)
        if color_stats:
            # Very low entropy = possibly synthetic/solid color
            if color_stats.entropy < 3.0:
                indicators.append(f"Low entropy ({color_stats.entropy:.1f}) — possibly synthetic")
                check.statistical_anomaly = True

            # Very few unique colors for a photo
            if color_stats.unique_colors < 100 and meta.width > 200:
                indicators.append(f"Very few unique colors ({color_stats.unique_colors}) for image size")
                check.statistical_anomaly = True

            # Perfectly uniform RGB channels = unlikely natural
            if (abs(color_stats.mean_r - color_stats.mean_g) < 1.0 and
                abs(color_stats.mean_g - color_stats.mean_b) < 1.0 and
                color_stats.std_r < 5.0):
                indicators.append("Perfectly uniform RGB — likely synthetic")
                check.statistical_anomaly = True

        # 5. Unusual dimensions (AI-generated images often have specific sizes)
        AI_DIMS = {(512, 512), (768, 768), (1024, 1024), (256, 256), (1024, 768)}
        if (meta.width, meta.height) in AI_DIMS and not meta.camera_model:
            indicators.append(f"Common AI generation size ({meta.width}x{meta.height})")

        check.indicators = indicators
        check.suspicious = len(indicators) >= 2
        check.confidence = min(len(indicators) * 0.2 + 0.3, 0.95)

        return check


# ═══════════════════════════════════════════════════════════════════════════
# Caption & Visual Claim Verifier
# ═══════════════════════════════════════════════════════════════════════════

class CaptionVerifier:
    """Verify claims about images / image captions."""

    def extract_visual_claims(self, text: str) -> List[str]:
        """Extract claims that reference visual content."""
        claims = []
        for pattern in VISUAL_CLAIM_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                # Get the sentence containing the match
                for match in pattern.finditer(text):
                    start = max(0, text.rfind('.', 0, match.start()) + 1)
                    end = text.find('.', match.end())
                    if end == -1:
                        end = len(text)
                    claim = text[start:end].strip()
                    if claim:
                        claims.append(claim)
        return claims

    def verify_caption(
        self,
        caption: str,
        metadata: ImageMetadata,
        color_stats: Optional[ColorStats] = None,
    ) -> float:
        """Score how well a caption matches available image data.

        Without CLIP, we check:
        - Does caption mention colors that match color stats?
        - Does caption mention camera/location that matches EXIF?
        - Does caption make verifiable claims about format/size?
        """
        score = 0.5  # Base: uncertain
        checks = 0
        matches = 0

        caption_lower = caption.lower()

        # Check color mentions
        if color_stats:
            color_words = {
                "red": (200, 50, 50), "green": (50, 200, 50), "blue": (50, 50, 200),
                "dark": None, "bright": None, "colorful": None, "monochrome": None,
            }
            for word, expected_rgb in color_words.items():
                if word in caption_lower:
                    checks += 1
                    if expected_rgb:
                        r, g, b = expected_rgb
                        if (abs(color_stats.mean_r - r) < 80 or
                            abs(color_stats.mean_g - g) < 80 or
                            abs(color_stats.mean_b - b) < 80):
                            matches += 1
                    elif word == "dark" and max(color_stats.mean_r, color_stats.mean_g, color_stats.mean_b) < 100:
                        matches += 1
                    elif word == "bright" and min(color_stats.mean_r, color_stats.mean_g, color_stats.mean_b) > 150:
                        matches += 1
                    elif word == "colorful" and color_stats.unique_colors > 1000:
                        matches += 1
                    elif word == "monochrome" and color_stats.unique_colors < 200:
                        matches += 1

        # Check EXIF-related claims
        if metadata.camera_model:
            if metadata.camera_model.lower() in caption_lower:
                checks += 1
                matches += 1

        if metadata.gps_present:
            location_words = {"location", "gps", "taken at", "photographed in"}
            if any(w in caption_lower for w in location_words):
                checks += 1
                matches += 1

        # Compute score
        if checks > 0:
            score = 0.3 + 0.7 * (matches / checks)
        else:
            score = 0.5  # No verifiable claims

        return round(score, 4)


# ═══════════════════════════════════════════════════════════════════════════
# Image Understanding Engine
# ═══════════════════════════════════════════════════════════════════════════

class ImageUnderstandingEngine:
    """Full image understanding and verification pipeline.

    Capabilities:
    - Metadata extraction and validation
    - Color statistical analysis
    - Manipulation detection (editing software, statistical anomalies)
    - Caption verification against image data
    - Visual claim extraction from text
    - CLIP-ready interface (plug in neural model when available)
    """

    def __init__(self):
        self.metadata_extractor = MetadataExtractor()
        self.color_analyzer = ColorAnalyzer()
        self.manipulation_detector = ManipulationDetector()
        self.caption_verifier = CaptionVerifier()

    def verify_image(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        caption: str = "",
        claims_text: str = "",
    ) -> ImageVerification:
        """Full verification pipeline for an image.

        Args:
            image_data: Raw image bytes.
            image_path: Path to image file.
            caption: Caption/alt-text to verify.
            claims_text: Text containing claims about the image.

        Returns:
            ImageVerification with scores and analysis.
        """
        # Get data
        if image_data is None and image_path:
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_data = f.read()

        if image_data is None:
            return ImageVerification(
                metadata=ImageMetadata(),
                verdict="ERROR",
                overall_score=0.0,
            )

        # 1. Extract metadata
        metadata = self.metadata_extractor.extract_from_bytes(image_data)

        # 2. Color analysis
        color_stats = self.color_analyzer.analyze(image_data)

        # 3. Manipulation detection
        manipulation = self.manipulation_detector.detect(metadata, color_stats)

        # 4. Caption verification
        caption_score = 0.0
        if caption:
            caption_score = self.caption_verifier.verify_caption(caption, metadata, color_stats)

        # 5. Visual claim extraction
        visual_claims = []
        if claims_text:
            visual_claims = self.caption_verifier.extract_visual_claims(claims_text)

        # 6. Overall score
        scores = [0.5]  # Base

        # Metadata quality contributes
        meta_score = 0.3
        if metadata.has_exif:
            meta_score += 0.2
        if metadata.camera_model:
            meta_score += 0.1
        if metadata.date_taken:
            meta_score += 0.1
        if metadata.width > 0:
            meta_score += 0.1
        scores.append(min(meta_score, 1.0))

        # Manipulation penalty
        if manipulation.suspicious:
            scores.append(1.0 - manipulation.confidence)
        else:
            scores.append(0.8)

        # Caption match
        if caption:
            scores.append(caption_score)

        overall = sum(scores) / len(scores)

        # Verdict
        if manipulation.suspicious and manipulation.confidence > 0.7:
            verdict = "SUSPICIOUS"
        elif overall >= 0.65:
            verdict = "PASS"
        elif overall >= 0.4:
            verdict = "UNCERTAIN"
        else:
            verdict = "FAIL"

        return ImageVerification(
            metadata=metadata,
            color_stats=color_stats,
            manipulation=manipulation,
            caption_match=caption_score,
            visual_claims=visual_claims,
            overall_score=round(overall, 4),
            verdict=verdict,
        )

    def verify_image_claim(self, claim_text: str) -> Dict[str, Any]:
        """Verify a text claim about an image (without the image itself).

        Checks:
        - Does the claim follow visual claim patterns?
        - Is the claimed content plausible?
        - Are there manipulation red flags in the language?
        """
        visual_claims = self.caption_verifier.extract_visual_claims(claim_text)

        # Check for manipulation language
        manip_words = {"clearly", "obviously", "undeniable", "proof", "evidence",
                       "you can see", "look at", "examine closely"}
        pressure_count = sum(1 for w in manip_words if w in claim_text.lower())

        # Hedging (appropriate uncertainty)
        hedge_words = {"appears", "seems", "might", "possibly", "suggests"}
        hedge_count = sum(1 for w in hedge_words if w in claim_text.lower())

        # Score
        if pressure_count >= 2 and hedge_count == 0:
            score = 0.35  # High-pressure, no hedging = suspicious
            verdict = "SUSPICIOUS"
        elif visual_claims and hedge_count > 0:
            score = 0.70  # Appropriate hedging with visual reference
            verdict = "PLAUSIBLE"
        elif visual_claims:
            score = 0.55
            verdict = "UNCERTAIN"
        else:
            score = 0.50
            verdict = "NO_VISUAL_CLAIM"

        return {
            "visual_claims": visual_claims,
            "pressure_language": pressure_count,
            "hedging": hedge_count,
            "score": score,
            "verdict": verdict,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": VERSION,
            "pil_available": _HAS_PIL,
            "numpy_available": _HAS_NUMPY,
            "clip_available": False,  # Placeholder for future
            "capabilities": [
                "metadata_extraction",
                "color_analysis" if _HAS_PIL and _HAS_NUMPY else None,
                "manipulation_detection",
                "caption_verification",
                "visual_claim_extraction",
            ],
        }


if __name__ == "__main__":
    engine = ImageUnderstandingEngine()
    print(f"Status: {engine.get_status()}")

    # Test visual claim verification
    claims = [
        "This photo clearly proves that the Earth is flat. Look at the horizon!",
        "The image appears to show a sunset over the ocean, suggesting calm conditions.",
        "According to this figure, temperatures increased by 2 degrees.",
        "The cat sat on the mat.",
    ]
    for claim in claims:
        result = engine.verify_image_claim(claim)
        print(f"  [{result['verdict']}] score={result['score']:.2f} "
              f"pressure={result['pressure_language']} hedge={result['hedging']} "
              f"— {claim[:50]}")

    print(f"\n✅ ImageUnderstandingEngine v{VERSION} OK")
