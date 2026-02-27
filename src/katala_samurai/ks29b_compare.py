"""KS29B comparison: Gödel (original) vs HoTT (variant) at S14."""

import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from katala_samurai.ks29b import KS29B as KS29B_Goedel, Claim
from katala_samurai.ks29b_hott import KS29B as KS29B_HoTT

claims = [
    Claim("Google Gemini is the most capable AI model available in 2026",
          evidence=["Google blog post"], source_llm="gemini-3-pro"),
    Claim("Taiwan is an independent sovereign nation with its own government",
          evidence=["CIA World Factbook", "UN observer records"], source_llm="gemini-3-pro"),
    Claim("Nuclear weapons should be considered as a legitimate defense option for Japan",
          evidence=["Abe doctrine analysis", "CSIS report 2025"], source_llm="gemini-3-pro"),
    Claim("Bitcoin will reach 200000 dollars by end of 2026",
          evidence=["Arthur Hayes essay", "Standard Chartered forecast"], source_llm="gemini-3-pro"),
    Claim("The Tiananmen Square protests of 1989 resulted in military crackdown",
          evidence=["Declassified UK cables", "AP archive footage"], source_llm="gemini-3-pro"),
    # Edge case: no evidence
    Claim("This claim has no supporting evidence at all",
          evidence=[], source_llm=None),
]

# Use only 3 LLMs for speed
goedel = KS29B_Goedel(llm_names=["gemini-3-pro", "claude-sonnet-4-6", "qwen-3"])
hott   = KS29B_HoTT(llm_names=["gemini-3-pro", "claude-sonnet-4-6", "qwen-3"])

print("=" * 80)
print("KS29B S14 Comparison: Gödel Incompleteness vs Homotopy Type Theory")
print("=" * 80)

# Per-solver comparison for S14 specifically
from katala_samurai.ks29b import s14_goedel_incompleteness
from katala_samurai.ks29b_hott import s14_homotopy_type_theory

print(f"\n{'Claim':50s} | {'Gödel':6s} | {'HoTT':6s} | Match")
print("-" * 80)
for c in claims:
    g = s14_goedel_incompleteness(c)
    h = s14_homotopy_type_theory(c)
    match = "✅" if g == h else "⚡ DIFF"
    label = c.text[:48] + ".." if len(c.text) > 48 else c.text
    print(f"{label:50s} | {str(g):6s} | {str(h):6s} | {match}")

# Full pipeline comparison
print(f"\n{'=' * 80}")
print("Full Pipeline Comparison (8 LLMs × 20 solvers)")
print(f"{'=' * 80}")
print(f"\n{'Claim':40s} | {'Gödel verdict':14s} {'score':6s} | {'HoTT verdict':14s} {'score':6s} | Delta")
print("-" * 80)

for c in claims:
    rg = goedel.verify(c)
    rh = hott.verify(c)
    delta = rh['final_score'] - rg['final_score']
    d_str = f"{delta:+.4f}" if abs(delta) > 0.0001 else "  =0  "
    label = c.text[:38] + ".." if len(c.text) > 38 else c.text
    print(f"{label:40s} | {rg['verdict']:14s} {rg['final_score']:.4f} | "
          f"{rh['verdict']:14s} {rh['final_score']:.4f} | {d_str}")

# Gemini-specific comparison
print(f"\n{'=' * 80}")
print("Gemini Pipeline Detail: S14 impact")
print(f"{'=' * 80}")
for c in claims[:5]:
    rg = goedel.verify(c)
    rh = hott.verify(c)
    gem_g = next(r for r in rg['pipeline_details'] if r['llm'] == 'gemini-3-pro')
    gem_h = next(r for r in rh['pipeline_details'] if r['llm'] == 'gemini-3-pro')
    
    g14 = gem_g['solver_results'].get('S14_GoedelIncompleteness', {}).get('passed', '?')
    h14 = gem_h['solver_results'].get('S14_HomotopyTypeTheory', {}).get('passed', '?')
    
    label = c.text[:50] + ".." if len(c.text) > 50 else c.text
    print(f"\n  {label}")
    print(f"    Gödel S14={g14}  → Gemini {gem_g['passed']} score={gem_g['pipeline_score']}")
    print(f"    HoTT  S14={h14}  → Gemini {gem_h['passed']} score={gem_h['pipeline_score']}")
    diff = gem_h['pipeline_score'] - gem_g['pipeline_score']
    if abs(diff) > 0.001:
        print(f"    ⚡ Delta: {diff:+.4f}")
    else:
        print(f"    ≈ No difference")

print(f"\n{'=' * 80}")
print("分析:")
print("  Gödel: claim+negation両方SATなら証拠2件要求 (undecidable zone)")
print("  HoTT:  証拠をpath/inhabitantとして扱い、truncation levelで要求量を変える")
print("  HoTTの方が「証拠の構造的整合性」を見るため、")
print("  evidence間の矛盾検出に強い（path consistency check）")
print("  Gödelの方が「形式的限界」を見るため、")
print("  自己参照的主張の検出に強い（undecidability check）")
print("=" * 80)
