"""
KS29B S14 Comparison: Gödel Incompleteness vs Homotopy Type Theory.

Runs the same claims through both KS29B variants to measure:
  - S14 solver divergence (Gödel undecidability vs HoTT path consistency)
  - Full pipeline score delta across all claims
  - Gemini-specific impact analysis

Key insight:
  Gödel: claim+negation both SAT → requires 2+ evidence (undecidable zone)
  HoTT:  evidence as paths/inhabitants, truncation level varies requirement
  HoTT is stronger at structural evidence consistency (path check).
  Gödel is stronger at self-referential claim detection (undecidability check).

Usage:
  python ks29b_compare.py
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from katala_samurai.ks29b import KS29B as KS29B_Goedel, Claim
from katala_samurai.ks29b_hott import KS29B as KS29B_HoTT

# ── Constants ──
NUM_COMPARISON_LLMS = 3               # Speed vs coverage tradeoff
LLM_NAMES = ["gemini-3-pro", "claude-sonnet-4-6", "qwen-3"]
TABLE_WIDTH = 80
LABEL_TRUNCATION = 48                 # Max chars for claim labels in output
FULL_LABEL_TRUNCATION = 38            # For full pipeline table
DETAIL_LABEL_TRUNCATION = 50          # For Gemini detail table
DELTA_THRESHOLD = 0.0001              # Min delta to display
GEMINI_DETAIL_COUNT = 5               # Claims to show in Gemini detail

# ── Test Claims ──
COMPARISON_CLAIMS = [
    Claim(
        "Google Gemini is the most capable AI model available in 2026",
        evidence=["Google blog post"],
        source_llm="gemini-3-pro",
    ),
    Claim(
        "Taiwan is an independent sovereign nation with its own government",
        evidence=["CIA World Factbook", "UN observer records"],
        source_llm="gemini-3-pro",
    ),
    Claim(
        "Nuclear weapons should be considered as a legitimate defense option for Japan",
        evidence=["Abe doctrine analysis", "CSIS report 2025"],
        source_llm="gemini-3-pro",
    ),
    Claim(
        "Bitcoin will reach 200000 dollars by end of 2026",
        evidence=["Arthur Hayes essay", "Standard Chartered forecast"],
        source_llm="gemini-3-pro",
    ),
    Claim(
        "The Tiananmen Square protests of 1989 resulted in military crackdown",
        evidence=["Declassified UK cables", "AP archive footage"],
        source_llm="gemini-3-pro",
    ),
    Claim(
        "This claim has no supporting evidence at all",
        evidence=[],
        source_llm=None,
    ),
]


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if exceeding max length."""
    return text[:max_len - 2] + ".." if len(text) > max_len else text


def run_s14_comparison() -> None:
    """Compare S14 solver output between Gödel and HoTT variants."""
    from katala_samurai.ks29b import s14_goedel_incompleteness
    from katala_samurai.ks29b_hott import s14_homotopy_type_theory

    print(f"\n{'Claim':50s} | {'Gödel':6s} | {'HoTT':6s} | Match")
    print("-" * TABLE_WIDTH)
    for claim in COMPARISON_CLAIMS:
        g_result = s14_goedel_incompleteness(claim)
        h_result = s14_homotopy_type_theory(claim)
        match = "✅" if g_result == h_result else "⚡ DIFF"
        label = _truncate(claim.text, LABEL_TRUNCATION)
        print(f"{label:50s} | {str(g_result):6s} | {str(h_result):6s} | {match}")


def run_full_pipeline_comparison() -> None:
    """Compare full verify() pipeline results between Gödel and HoTT."""
    goedel = KS29B_Goedel(llm_names=LLM_NAMES)
    hott = KS29B_HoTT(llm_names=LLM_NAMES)

    print(f"\n{'Claim':40s} | {'Gödel verdict':14s} {'score':6s} | "
          f"{'HoTT verdict':14s} {'score':6s} | Delta")
    print("-" * TABLE_WIDTH)

    for claim in COMPARISON_CLAIMS:
        rg = goedel.verify(claim)
        rh = hott.verify(claim)
        delta = rh["final_score"] - rg["final_score"]
        d_str = f"{delta:+.4f}" if abs(delta) > DELTA_THRESHOLD else "  =0  "
        label = _truncate(claim.text, FULL_LABEL_TRUNCATION)
        print(
            f"{label:40s} | {rg['verdict']:14s} {rg['final_score']:.4f} | "
            f"{rh['verdict']:14s} {rh['final_score']:.4f} | {d_str}"
        )


def run_gemini_detail() -> None:
    """Show Gemini-specific S14 impact for first N claims."""
    goedel = KS29B_Goedel(llm_names=LLM_NAMES)
    hott = KS29B_HoTT(llm_names=LLM_NAMES)

    for claim in COMPARISON_CLAIMS[:GEMINI_DETAIL_COUNT]:
        rg = goedel.verify(claim)
        rh = hott.verify(claim)
        gem_g = next(r for r in rg["pipeline_details"] if r["llm"] == "gemini-3-pro")
        gem_h = next(r for r in rh["pipeline_details"] if r["llm"] == "gemini-3-pro")

        g14 = gem_g["solver_results"].get("S14_GoedelIncompleteness", {}).get("passed", "?")
        h14 = gem_h["solver_results"].get("S14_HomotopyTypeTheory", {}).get("passed", "?")

        label = _truncate(claim.text, DETAIL_LABEL_TRUNCATION)
        print(f"\n  {label}")
        print(f"    Gödel S14={g14}  → Gemini {gem_g['passed']} "
              f"score={gem_g['pipeline_score']}")
        print(f"    HoTT  S14={h14}  → Gemini {gem_h['passed']} "
              f"score={gem_h['pipeline_score']}")
        diff = gem_h["pipeline_score"] - gem_g["pipeline_score"]
        if abs(diff) > DELTA_THRESHOLD:
            print(f"    ⚡ Delta: {diff:+.4f}")
        else:
            print(f"    ≈ No difference")


def main() -> None:
    """Run all comparison sections."""
    print("=" * TABLE_WIDTH)
    print("KS29B S14 Comparison: Gödel Incompleteness vs Homotopy Type Theory")
    print("=" * TABLE_WIDTH)

    run_s14_comparison()

    print(f"\n{'=' * TABLE_WIDTH}")
    print(f"Full Pipeline Comparison ({NUM_COMPARISON_LLMS} LLMs × 20 solvers)")
    print(f"{'=' * TABLE_WIDTH}")

    run_full_pipeline_comparison()

    print(f"\n{'=' * TABLE_WIDTH}")
    print("Gemini Pipeline Detail: S14 impact")
    print(f"{'=' * TABLE_WIDTH}")

    run_gemini_detail()

    print(f"\n{'=' * TABLE_WIDTH}")
    print("Analysis:")
    print("  Gödel: claim+negation both SAT → requires 2+ evidence (undecidable zone)")
    print("  HoTT:  evidence as paths/inhabitants, truncation level varies requirement")
    print("  HoTT is stronger at structural evidence consistency (path check)")
    print("  Gödel is stronger at self-referential claim detection (undecidability check)")
    print("=" * TABLE_WIDTH)


if __name__ == "__main__":
    main()
