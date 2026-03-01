#!/usr/bin/env python3
"""Phase 3: Summary Translation Loss Analyzer.

Applies KCS1a's 5-axis model to text summarization:
  Source (search results / articles) → Summary (agent output)

Measures how much meaning is lost when condensing information.

5-Axis Summary Translation Model (reinterpreted from KCS1a):
  R_struct:   Does the summary preserve the logical structure of the source?
  R_context:  Are background assumptions / caveats preserved?
  R_qualia:   Does the summary "feel" accurate? (specificity, hedging)
  R_cultural: Does the summary follow output conventions? (citations, format)
  R_temporal: Will this summary remain accurate over time?

Design: Nicolas Ogoshi / Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
Date: 2026-03-01
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, asdict, field
from typing import Any


# ── Constants ──
GRADE_THRESHOLDS = [(0.90, "S"), (0.80, "A"), (0.65, "B"), (0.50, "C"), (0.35, "D"), (0.00, "F")]
AXIS_WEIGHTS = {"r_struct": 0.30, "r_context": 0.25, "r_qualia": 0.20, "r_cultural": 0.10, "r_temporal": 0.15}


@dataclass(slots=True)
class SummaryVerdict:
    """Translation loss verdict for a summary."""
    r_struct: float
    r_context: float
    r_qualia: float
    r_cultural: float
    r_temporal: float
    total_fidelity: float
    translation_loss: float
    grade: str
    # Diagnostics
    structural_issues: list[str] = field(default_factory=list)
    context_gaps: list[str] = field(default_factory=list)
    qualia_warnings: list[str] = field(default_factory=list)
    cultural_notes: list[str] = field(default_factory=list)
    temporal_risks: list[str] = field(default_factory=list)
    # Meta
    source_len: int = 0
    summary_len: int = 0
    compression_ratio: float = 0.0


# ════════════════════════════════════════════
# R_struct: Logical Structure Preservation
# ════════════════════════════════════════════

def _extract_key_claims(text: str) -> list[str]:
    """Extract sentence-level claims from text (multilingual)."""
    # Split on sentence boundaries (English + Japanese)
    sentences = re.split(r'(?<=[.!?。！？])\s*', text.strip())
    # Filter out very short sentences (likely headers/labels)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


# ── Morphological analysis for cross-lingual matching ──
try:
    import fugashi as _fugashi
    _SL_TAGGER: _fugashi.Tagger | None = _fugashi.Tagger()
except (ImportError, RuntimeError):
    _SL_TAGGER = None


def _tokenize_ja(text: str) -> list[str]:
    """Tokenize Japanese text into content words using morphological analysis."""
    if _SL_TAGGER is None:
        # Fallback: character n-gram + kanji/katakana extraction
        kanji = re.findall(r'[一-龯]{2,}', text)
        kata = re.findall(r'[ァ-ヴー]{3,}', text)
        return kanji + kata

    words = _SL_TAGGER(text)
    content_pos = {'名詞', '動詞', '形容詞'}
    stop_surfaces = {'する', 'ある', 'いる', 'なる', 'れる', 'られる', 'こと', 'もの', 'ため', 'よう'}
    result = []
    for w in words:
        pos = w.feature.pos1 if hasattr(w.feature, 'pos1') else ''
        if pos in content_pos and w.surface not in stop_surfaces and len(w.surface) >= 2:
            result.append(w.surface)
    return result


def _detect_text_lang(text: str) -> str:
    """Detect if text is primarily Japanese or English."""
    cjk = len(re.findall(r'[\u3000-\u9fff]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    return "ja" if cjk > latin else "en"


def _extract_entities(text: str) -> set[str]:
    """Extract named entities and key terms (multilingual)."""
    # Capitalized words (English proper nouns)
    en_entities = set(re.findall(r'\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)*\b', text))
    # Numbers with context
    numbers = set(re.findall(r'\d+(?:\.\d+)?%?', text))
    # Japanese key terms: use morphological analysis
    ja_content = _tokenize_ja(text)
    ja_entities = set(ja_content)
    # Also grab katakana compounds
    kata = set(re.findall(r'[ァ-ヴー]{3,}(?:・[ァ-ヴー]{2,})*', text))
    return en_entities | numbers | ja_entities | kata


def _compute_r_struct(source: str, summary: str) -> tuple[float, list[str]]:
    """Measure logical structure preservation."""
    issues = []

    source_claims = _extract_key_claims(source)
    summary_claims = _extract_key_claims(summary)
    source_entities = _extract_entities(source)
    summary_entities = _extract_entities(summary)

    if not source_claims:
        return 0.5, ["Could not extract claims from source"]

    # 1. Entity preservation
    if source_entities:
        entity_preserved = len(source_entities & summary_entities) / len(source_entities)
    else:
        entity_preserved = 0.5

    # 2. Claim coverage (cross-lingual aware)
    source_lang = _detect_text_lang(source)
    summary_lang = _detect_text_lang(summary)
    cross_lingual = source_lang != summary_lang

    claims_covered = 0
    summary_lower = summary.lower()

    for claim in source_claims:
        if cross_lingual:
            # Cross-lingual: match entities (numbers, proper nouns, katakana)
            # These survive translation better than content words
            claim_entities = _extract_entities(claim)
            summary_entities_local = _extract_entities(summary)
            if claim_entities:
                overlap = len(claim_entities & summary_entities_local) / len(claim_entities)
                if overlap >= 0.2:  # Lower threshold for cross-lingual
                    claims_covered += 1
            # Also check Japanese tokenized content for semantic overlap
            elif source_lang == "en":
                # English → Japanese: look for katakana transliterations
                en_words = set(re.findall(r'[A-Z][a-z]{2,}', claim))
                if en_words and any(w.lower() in summary_lower for w in en_words):
                    claims_covered += 1
        else:
            # Same language: word overlap
            if source_lang == "ja":
                claim_words = set(_tokenize_ja(claim))
                summary_words = set(_tokenize_ja(summary))
                if claim_words:
                    overlap = len(claim_words & summary_words) / len(claim_words)
                    if overlap >= 0.3:
                        claims_covered += 1
            else:
                claim_words = set(re.findall(r'\w{4,}', claim.lower()))
                if claim_words:
                    overlap = sum(1 for w in claim_words if w in summary_lower) / len(claim_words)
                    if overlap >= 0.4:
                        claims_covered += 1

    claim_coverage = claims_covered / len(source_claims)

    # 3. Ordering preservation (do key entities appear in similar order?)
    source_entity_order = [e for e in re.findall(r'[A-Z][a-z]{2,}|\d+', source) if len(e) > 2]
    summary_entity_order = [e for e in re.findall(r'[A-Z][a-z]{2,}|\d+', summary) if len(e) > 2]

    order_score = 0.7  # Default
    if len(source_entity_order) >= 3 and len(summary_entity_order) >= 2:
        # Check if relative ordering is preserved
        common = [e for e in summary_entity_order if e in source_entity_order]
        if len(common) >= 2:
            inversions = 0
            for i in range(len(common) - 1):
                idx_a = source_entity_order.index(common[i])
                idx_b = source_entity_order.index(common[i + 1])
                if idx_a > idx_b:
                    inversions += 1
            order_score = 1.0 - (inversions / max(1, len(common) - 1)) * 0.5

    if claim_coverage < 0.5:
        issues.append(f"Low claim coverage: {claim_coverage:.0%} of source claims reflected")
    if entity_preserved < 0.3:
        issues.append(f"Many source entities dropped: {entity_preserved:.0%} preserved")

    score = 0.35 * entity_preserved + 0.45 * claim_coverage + 0.20 * order_score
    return round(max(0.0, min(1.0, score)), 4), issues


# ════════════════════════════════════════════
# R_context: Background / Caveat Preservation
# ════════════════════════════════════════════

_CAVEAT_MARKERS = [
    r"however", r"but\b", r"although", r"despite", r"except",
    r"note that", r"caveat", r"limitation", r"assuming",
    r"ただし", r"しかし", r"ただ", r"なお", r"注意",
    r"if\b", r"unless", r"条件", r"場合",
]

_ASSUMPTION_MARKERS = [
    r"because", r"since\b", r"due to", r"based on", r"given that",
    r"なぜなら", r"のため", r"に基づ", r"前提",
]


def _compute_r_context(source: str, summary: str) -> tuple[float, list[str]]:
    """Measure preservation of caveats, assumptions, and background context."""
    gaps = []
    source_lower = source.lower()
    summary_lower = summary.lower()

    # Count caveats in source vs summary
    source_caveats = sum(1 for p in _CAVEAT_MARKERS if re.search(p, source_lower))
    summary_caveats = sum(1 for p in _CAVEAT_MARKERS if re.search(p, summary_lower))

    caveat_ratio = 1.0
    if source_caveats > 0:
        caveat_ratio = min(1.0, summary_caveats / source_caveats)
        if caveat_ratio < 0.5:
            gaps.append(f"Caveats lost: source has {source_caveats}, summary has {summary_caveats}")

    # Count assumptions
    source_assumptions = sum(1 for p in _ASSUMPTION_MARKERS if re.search(p, source_lower))
    summary_assumptions = sum(1 for p in _ASSUMPTION_MARKERS if re.search(p, summary_lower))

    assumption_ratio = 1.0
    if source_assumptions > 0:
        assumption_ratio = min(1.0, summary_assumptions / source_assumptions)
        if assumption_ratio < 0.5:
            gaps.append(f"Assumptions dropped: {source_assumptions} in source, {summary_assumptions} in summary")

    # Conditional statements
    source_conditionals = len(re.findall(r'\bif\b|\bunless\b|場合|条件', source_lower))
    summary_conditionals = len(re.findall(r'\bif\b|\bunless\b|場合|条件', summary_lower))

    conditional_ratio = 1.0
    if source_conditionals > 0:
        conditional_ratio = min(1.0, summary_conditionals / source_conditionals)

    score = 0.40 * caveat_ratio + 0.35 * assumption_ratio + 0.25 * conditional_ratio
    return round(max(0.0, min(1.0, score)), 4), gaps


# ════════════════════════════════════════════
# R_qualia: Specificity & Accuracy Feel
# ════════════════════════════════════════════

def _compute_r_qualia(source: str, summary: str) -> tuple[float, list[str]]:
    """Measure whether the summary feels accurate and specific."""
    warnings = []

    # 1. Number preservation
    source_numbers = set(re.findall(r'\d+(?:\.\d+)?%?', source))
    summary_numbers = set(re.findall(r'\d+(?:\.\d+)?%?', summary))

    if source_numbers:
        num_preserved = len(source_numbers & summary_numbers) / len(source_numbers)
    else:
        num_preserved = 0.8

    if source_numbers and num_preserved < 0.5:
        warnings.append(f"Numbers lost: {len(source_numbers)} in source, {len(source_numbers & summary_numbers)} preserved")

    # 2. Hedging added (summary adds uncertainty not in source)
    hedge_words = ["maybe", "possibly", "might", "perhaps", "seems", "appears",
                   "かもしれない", "らしい", "っぽい", "思われる"]
    source_hedges = sum(1 for h in hedge_words if h in source.lower())
    summary_hedges = sum(1 for h in hedge_words if h in summary.lower())
    added_hedging = max(0, summary_hedges - source_hedges)
    hedge_penalty = min(0.3, added_hedging * 0.1)
    if added_hedging > 0:
        warnings.append(f"Added hedging: {added_hedging} hedge words not in source")

    # 3. Specificity: summary shouldn't be vaguer than source
    source_specifics = len(re.findall(r'\d|%|[A-Z][a-z]+\s[A-Z]|「|"', source))
    summary_specifics = len(re.findall(r'\d|%|[A-Z][a-z]+\s[A-Z]|「|"', summary))
    specificity_ratio = 1.0
    if source_specifics > 0:
        # Adjust for compression
        expected = source_specifics * (len(summary) / max(1, len(source)))
        if expected > 0:
            specificity_ratio = min(1.5, summary_specifics / expected)
        specificity_ratio = min(1.0, specificity_ratio)

    score = 0.40 * num_preserved + 0.30 * (1.0 - hedge_penalty) + 0.30 * specificity_ratio
    return round(max(0.0, min(1.0, score)), 4), warnings


# ════════════════════════════════════════════
# R_cultural: Output Convention Adherence
# ════════════════════════════════════════════

def _compute_r_cultural(summary: str) -> tuple[float, list[str]]:
    """Check summary follows output conventions (citations, formatting)."""
    notes = []
    score = 0.7  # Baseline

    # Has source attribution?
    has_url = bool(re.search(r'https?://', summary))
    has_citation = bool(re.search(r'出典|source|ref|参照|according to|によると', summary.lower()))
    if has_url or has_citation:
        score += 0.15
    else:
        notes.append("No source attribution in summary")

    # Structured output (bullets, headers)?
    has_structure = bool(re.search(r'^[-*•]|\n[-*•]|^#{1,3}\s', summary, re.MULTILINE))
    if has_structure:
        score += 0.1

    # Not too long for a summary
    if len(summary) > 2000:
        notes.append("Summary exceeds 2000 chars — may not be concise enough")
        score -= 0.05

    return round(max(0.0, min(1.0, score)), 4), notes


# ════════════════════════════════════════════
# R_temporal: Summary Shelf Life
# ════════════════════════════════════════════

_TEMPORAL_MARKERS = [
    r"\b(today|yesterday|this week|now|current|latest|recent)\b",
    r"(今日|昨日|今週|現在|最新|最近|直近)",
    r"\b(202[4-9]|203\d)\b",  # Near-future dates
]

_TIMELESS_MARKERS = [
    r"\b(always|generally|typically|historically|fundamental)\b",
    r"(一般的|基本的|歴史的|原則)",
]


def _compute_r_temporal(source: str, summary: str) -> tuple[float, list[str]]:
    """Estimate how quickly this summary will become stale."""
    risks = []

    temporal_refs = sum(len(re.findall(p, summary, re.I)) for p in _TEMPORAL_MARKERS)
    timeless_refs = sum(len(re.findall(p, summary, re.I)) for p in _TIMELESS_MARKERS)

    # High temporal references without dates = will rot fast
    if temporal_refs > 2 and not re.search(r'20\d{2}[-/]\d{1,2}', summary):
        risks.append("Temporal references without specific dates — will become ambiguous")
        score = 0.5
    elif temporal_refs > 0:
        score = 0.7
    else:
        score = 0.9

    if timeless_refs > temporal_refs:
        score = min(1.0, score + 0.1)

    # Check if summary preserves dates from source
    source_dates = set(re.findall(r'20\d{2}[-/]\d{1,2}[-/]?\d{0,2}', source))
    summary_dates = set(re.findall(r'20\d{2}[-/]\d{1,2}[-/]?\d{0,2}', summary))
    if source_dates and not summary_dates:
        risks.append("Source dates not preserved in summary")
        score -= 0.15

    return round(max(0.0, min(1.0, score)), 4), risks


# ════════════════════════════════════════════
# Main Engine
# ════════════════════════════════════════════

class SummaryLossAnalyzer:
    """Analyze translation loss from source text to summary."""

    def analyze(self, source: str, summary: str) -> SummaryVerdict:
        """Run 5-axis analysis on source→summary translation."""
        r_struct, struct_issues = _compute_r_struct(source, summary)
        r_context, context_gaps = _compute_r_context(source, summary)
        r_qualia, qualia_warnings = _compute_r_qualia(source, summary)
        r_cultural, cultural_notes = _compute_r_cultural(summary)
        r_temporal, temporal_risks = _compute_r_temporal(source, summary)

        total = (
            AXIS_WEIGHTS["r_struct"] * r_struct +
            AXIS_WEIGHTS["r_context"] * r_context +
            AXIS_WEIGHTS["r_qualia"] * r_qualia +
            AXIS_WEIGHTS["r_cultural"] * r_cultural +
            AXIS_WEIGHTS["r_temporal"] * r_temporal
        )
        total = round(max(0.0, min(1.0, total)), 4)

        grade = "F"
        for threshold, g in GRADE_THRESHOLDS:
            if total >= threshold:
                grade = g
                break

        source_len = len(source)
        summary_len = len(summary)
        compression = round(summary_len / max(1, source_len), 4)

        return SummaryVerdict(
            r_struct=r_struct,
            r_context=r_context,
            r_qualia=r_qualia,
            r_cultural=r_cultural,
            r_temporal=r_temporal,
            total_fidelity=total,
            translation_loss=round(1.0 - total, 4),
            grade=grade,
            structural_issues=struct_issues,
            context_gaps=context_gaps,
            qualia_warnings=qualia_warnings,
            cultural_notes=cultural_notes,
            temporal_risks=temporal_risks,
            source_len=source_len,
            summary_len=summary_len,
            compression_ratio=compression,
        )

    @staticmethod
    def format(v: SummaryVerdict) -> str:
        """Pretty-print verdict."""
        lines = [
            f"╔══ Summary Loss: Grade {v.grade} ({v.total_fidelity:.1%} fidelity, {v.translation_loss:.1%} loss) ══╗",
            f"║ R_struct:   {v.r_struct:.3f}  (logical structure)",
            f"║ R_context:  {v.r_context:.3f}  (caveats/assumptions)",
            f"║ R_qualia:   {v.r_qualia:.3f}  (specificity/accuracy)",
            f"║ R_cultural: {v.r_cultural:.3f}  (output conventions)",
            f"║ R_temporal: {v.r_temporal:.3f}  (shelf life)",
            f"║ Compression: {v.source_len}→{v.summary_len} chars ({v.compression_ratio:.0%})",
        ]
        all_diag = [
            ("⚠️  Structure", v.structural_issues),
            ("📚 Context", v.context_gaps),
            ("🎯 Qualia", v.qualia_warnings),
            ("🏛️  Convention", v.cultural_notes),
            ("⏳ Temporal", v.temporal_risks),
        ]
        for label, items in all_diag:
            if items:
                lines.append(f"║ {label}:")
                for item in items:
                    lines.append(f"║   • {item}")
        lines.append("╚" + "═" * 60 + "╝")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze translation loss in summaries")
    parser.add_argument("--source", required=True, help="Source text or @filepath")
    parser.add_argument("--summary", required=True, help="Summary text or @filepath")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    def load_text(val: str) -> str:
        if val.startswith("@"):
            with open(val[1:], encoding="utf-8") as f:
                return f.read()
        return val

    source = load_text(args.source)
    summary = load_text(args.summary)

    analyzer = SummaryLossAnalyzer()
    verdict = analyzer.analyze(source, summary)

    if args.json:
        print(json.dumps(asdict(verdict), ensure_ascii=False, indent=2))
    else:
        print(SummaryLossAnalyzer.format(verdict))


if __name__ == "__main__":
    main()
