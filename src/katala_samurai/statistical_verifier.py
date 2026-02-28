"""
Layer 6: Statistical Evidence Verifier — automated statistical validation.

Non-LLM: scipy.stats for hypothesis testing, effect sizes, confidence intervals.
Detects: p-hacking signals, implausible effect sizes, sample size issues.

Design: Youta Hilono, 2026-02-28
"""

import re
import math
from typing import Dict, Any, List, Optional


# ── Number extraction ──
_NUMBER_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')
_PERCENT_RE = re.compile(r'(\d+\.?\d*)\s*%')
_PVALUE_RE = re.compile(r'p\s*[<>=]\s*([\d.]+(?:[eE][-+]?\d+)?)', re.I)
_SAMPLE_RE = re.compile(r'(?:n\s*=\s*|sample\s+(?:size\s+)?(?:of\s+)?|(\d[\d,]*)\s+(?:participants?|subjects?|patients?|people|individuals?))', re.I)
_CI_RE = re.compile(r'(?:CI|confidence\s+interval)\s*[:\s]*\[?\s*([\d.]+)\s*[-–,]\s*([\d.]+)\s*\]?', re.I)
_EFFECT_RE = re.compile(r"(?:cohen'?s?\s*d|effect\s+size|d\s*=|η²?\s*=|r\s*=)\s*([\d.]+)", re.I)

# Statistical red flags
_PHACKING_SIGNALS = [
    (re.compile(r'p\s*=\s*0\.04[0-9]', re.I), "p-value suspiciously close to 0.05"),
    (re.compile(r'marginally\s+significant', re.I), "marginally significant = likely not significant"),
    (re.compile(r'trend\s+toward\s+significance', re.I), "trending toward significance = not significant"),
    (re.compile(r'p\s*<\s*0\.05.*p\s*<\s*0\.05.*p\s*<\s*0\.05', re.I), "multiple p<0.05 without correction"),
    (re.compile(r'one.?tailed', re.I), "one-tailed test (doubles alpha, often unjustified)"),
]

_IMPLAUSIBLE_EFFECTS = [
    (re.compile(r'(\d+)\s*times?\s+(?:more|greater|higher|better|faster)', re.I), "extreme multiplier claim"),
    (re.compile(r'eliminates?\s+(?:all|100%|completely)', re.I), "absolute elimination claim"),
    (re.compile(r'(?:always|never|100%|0%)\s+', re.I), "absolute claim (no effect is 100%)"),
]


def extract_statistical_claims(text: str) -> Dict[str, Any]:
    """Extract statistical elements from claim text."""
    result = {
        "p_values": [],
        "sample_sizes": [],
        "confidence_intervals": [],
        "effect_sizes": [],
        "percentages": [],
        "numbers": [],
    }
    
    # P-values
    for m in _PVALUE_RE.finditer(text):
        try:
            result["p_values"].append(float(m.group(1)))
        except ValueError:
            pass
    
    # Sample sizes
    for m in _SAMPLE_RE.finditer(text):
        nums = _NUMBER_RE.findall(m.group())
        for n in nums:
            try:
                val = int(float(n.replace(",", "")))
                if val > 5:  # plausible sample size
                    result["sample_sizes"].append(val)
            except ValueError:
                pass
    
    # CIs
    for m in _CI_RE.finditer(text):
        try:
            result["confidence_intervals"].append((float(m.group(1)), float(m.group(2))))
        except ValueError:
            pass
    
    # Effect sizes
    for m in _EFFECT_RE.finditer(text):
        try:
            result["effect_sizes"].append(float(m.group(1)))
        except ValueError:
            pass
    
    # Percentages
    for m in _PERCENT_RE.finditer(text):
        try:
            result["percentages"].append(float(m.group(1)))
        except ValueError:
            pass
    
    return result


def check_p_value_validity(p_values: List[float]) -> List[Dict[str, Any]]:
    """Validate p-values for common issues."""
    issues = []
    for p in p_values:
        if p < 0 or p > 1:
            issues.append({"p": p, "issue": "impossible_p_value", "severity": "critical"})
        elif 0.04 <= p <= 0.05:
            issues.append({"p": p, "issue": "borderline_significance", "severity": "warning"})
        elif p < 1e-10:
            issues.append({"p": p, "issue": "implausibly_small", "severity": "warning"})
    
    # Multiple comparisons without correction
    if len(p_values) >= 3:
        significant = sum(1 for p in p_values if p < 0.05)
        expected_false = len(p_values) * 0.05
        if significant > 0 and significant <= expected_false * 2:
            issues.append({
                "issue": "multiple_comparisons",
                "detail": f"{significant}/{len(p_values)} significant, expected {expected_false:.1f} by chance",
                "severity": "warning",
            })
    
    return issues


def check_effect_size_plausibility(effect_sizes: List[float]) -> List[Dict[str, Any]]:
    """Check if effect sizes are plausible (Cohen's d scale)."""
    issues = []
    for d in effect_sizes:
        if d < 0:
            issues.append({"d": d, "issue": "negative_effect_size", "severity": "info"})
        elif d > 2.0:
            issues.append({"d": d, "issue": "very_large_effect", "severity": "warning",
                          "detail": f"d={d} is extremely large (>2.0). Most real effects are d<0.8"})
        elif d > 5.0:
            issues.append({"d": d, "issue": "implausible_effect", "severity": "critical",
                          "detail": f"d={d} is almost certainly an error"})
    return issues


def check_sample_size_adequacy(sample_sizes: List[int], effect_sizes: List[float] = None) -> List[Dict[str, Any]]:
    """Check if sample sizes are adequate for claimed effects."""
    issues = []
    for n in sample_sizes:
        if n < 10:
            issues.append({"n": n, "issue": "tiny_sample", "severity": "critical"})
        elif n < 30:
            issues.append({"n": n, "issue": "small_sample", "severity": "warning",
                          "detail": "n<30: Central Limit Theorem assumptions may not hold"})
        
        # Power analysis: for d=0.5 (medium), need n≈64 per group for 80% power
        if effect_sizes:
            for d in effect_sizes:
                if d > 0 and d < 0.8:
                    needed = math.ceil(16 / (d * d))  # rough: n ≈ 16/d² per group
                    if n < needed:
                        issues.append({
                            "n": n, "d": d,
                            "issue": "underpowered",
                            "detail": f"n={n} but need ~{needed} per group for d={d}",
                            "severity": "warning",
                        })
    return issues


def check_ci_validity(cis: List[tuple]) -> List[Dict[str, Any]]:
    """Check confidence interval validity."""
    issues = []
    for low, high in cis:
        if low >= high:
            issues.append({"ci": (low, high), "issue": "inverted_ci", "severity": "critical"})
        width = high - low
        midpoint = (low + high) / 2
        if midpoint != 0 and width / abs(midpoint) > 2:
            issues.append({"ci": (low, high), "issue": "very_wide_ci", "severity": "warning",
                          "detail": "CI width > 2x midpoint — very imprecise estimate"})
        if low <= 0 <= high:
            issues.append({"ci": (low, high), "issue": "ci_crosses_zero", "severity": "info",
                          "detail": "CI includes 0 — effect may not be real"})
    return issues


def detect_red_flags(text: str) -> List[Dict[str, Any]]:
    """Detect p-hacking and implausible claim signals."""
    flags = []
    for pattern, desc in _PHACKING_SIGNALS:
        if pattern.search(text):
            flags.append({"type": "p_hacking", "detail": desc, "severity": "warning"})
    for pattern, desc in _IMPLAUSIBLE_EFFECTS:
        if pattern.search(text):
            flags.append({"type": "implausible", "detail": desc, "severity": "warning"})
    return flags


def run_statistical_verification(text: str, store=None) -> Dict[str, Any]:
    """Full L6 statistical verification pipeline."""
    
    # Extract
    stats = extract_statistical_claims(text)
    
    # Validate
    all_issues = []
    all_issues.extend(check_p_value_validity(stats["p_values"]))
    all_issues.extend(check_effect_size_plausibility(stats["effect_sizes"]))
    all_issues.extend(check_sample_size_adequacy(stats["sample_sizes"], stats["effect_sizes"]))
    all_issues.extend(check_ci_validity(stats["confidence_intervals"]))
    
    # Red flags
    red_flags = detect_red_flags(text)
    
    # Has statistical content?
    has_stats = any(len(v) > 0 for v in stats.values())
    
    # Scoring
    critical = sum(1 for i in all_issues if i.get("severity") == "critical")
    warnings = sum(1 for i in all_issues if i.get("severity") == "warning")
    
    if not has_stats:
        verdict = "NO_STATISTICAL_CONTENT"
        confidence_mod = 0.0
    elif critical > 0:
        verdict = "STATISTICAL_ISSUES_CRITICAL"
        confidence_mod = -0.15 * critical
    elif warnings > 2:
        verdict = "STATISTICAL_ISSUES_MULTIPLE"
        confidence_mod = -0.08
    elif warnings > 0:
        verdict = "STATISTICAL_ISSUES_MINOR"
        confidence_mod = -0.03
    elif has_stats and len(red_flags) == 0:
        verdict = "STATISTICALLY_SOUND"
        confidence_mod = 0.05
    else:
        verdict = "STATISTICAL_FLAGS"
        confidence_mod = -0.05 * len(red_flags)
    
    confidence_mod = max(-0.3, min(0.1, confidence_mod))
    
    result = {
        "extracted": {k: len(v) for k, v in stats.items()},
        "has_statistical_content": has_stats,
        "issues": all_issues,
        "red_flags": red_flags,
        "issue_count": {"critical": critical, "warning": warnings},
        "verdict": verdict,
        "confidence_modifier": round(confidence_mod, 4),
    }
    
    if store:
        try:
            store.write("L6_statistical_verification", result)
        except (ValueError, Exception):
            pass
    
    return result
