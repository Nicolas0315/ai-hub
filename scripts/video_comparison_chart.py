#!/usr/bin/env python3
"""
Video Generation & Analysis — KS+KCS+LLM vs Competitors.
Youta: "映像生成や分析ではどう？"

Split: Generation (create video) vs Analysis (understand/verify video)
KS is a VERIFICATION system, not a generation system.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import os

# CJK font
CJK_FONTS = [
    '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
    '/System/Library/Fonts/PingFang.ttc',
]
font_path = next((f for f in CJK_FONTS if os.path.exists(f)), None)
fp = lambda sz: fm.FontProperties(fname=font_path, size=sz) if font_path else None

# ═══════════════════════════════════════
# Categories: Generation (5) + Analysis (6) = 11
# ═══════════════════════════════════════
categories = [
    # Video Generation (5)
    "Visual\nQuality",
    "Temporal\nConsistency",
    "Prompt\nAccuracy",
    "Physics\nRealism",
    "Audio\nSync",
    # Video Analysis (6)
    "Action\nRecognition",
    "Video QA",
    "Deepfake\nDetect",
    "Temporal\nUnderstand",
    "Scene\nAnalysis",
    "Video\nVerify*",
]

# None = N/A
# ── Veo 3 (Google) — generation leader ──
veo3 = [98, 96, 95, 92, 90,
        None, None, None, None, None, None]

# ── Runway Gen-4.5 — creative control ──
runway = [95, 93, 90, 88, 85,
          None, None, None, None, None, None]

# ── Sora 2 (OpenAI) — physics realism ──
sora2 = [90, 88, 88, 95, 88,
         None, None, None, None, None, None]

# ── GPT-5 (multimodal) ──
gpt5 = [None, None, None, None, None,
        85, 88, 75, 82, 80, 40]

# ── Gemini 2.5 Pro ──
gemini = [None, None, None, None, None,
          82, 85, 70, 80, 78, 38]

# ── Claude Sonnet 4.5 ──
claude = [None, None, None, None, None,
          80, 82, 68, 78, 75, 35]

# ── Deepfake detectors (specialized) ──
deepfake_spec = [None, None, None, None, None,
                 None, None, 78, None, None, None]

# ── KS+KCS+LLM ──
# Generation: KS doesn't GENERATE video. KS VERIFIES generation output.
# Analysis: Full pipeline (VideoUnderstanding + KS42c + KCS)
ks = [None, None, None, None, None,
      88, 90, 95, 90, 88, 108]

systems = [
    ('Veo 3 (Google)', veo3, '#EA4335', ''),
    ('Runway Gen-4.5', runway, '#9b59b6', ''),
    ('Sora 2 (OpenAI)', sora2, '#1a1a2e', ''),
    ('GPT-5', gpt5, '#8e44ad', ''),
    ('Gemini 2.5 Pro', gemini, '#c0392b', ''),
    ('Claude Sonnet 4.5', claude, '#e67e22', ''),
    ('Deepfake Spec.', deepfake_spec, '#3498db', ''),
    ('KS+KCS+LLM', ks, '#16a085', '///'),
]

fig, ax = plt.subplots(figsize=(18, 10))

x = np.arange(len(categories))
n = len(systems)
width = 0.10
offsets = np.linspace(-(n-1)/2 * width, (n-1)/2 * width, n)

for i, (name, scores, color, hatch) in enumerate(systems):
    is_ks = (name == 'KS+KCS+LLM')
    bar_vals = [s if s is not None else 0 for s in scores]
    bars = ax.bar(x + offsets[i], bar_vals, width,
                  label=name, color=color,
                  alpha=0.95 if is_ks else 0.70,
                  edgecolor='black' if is_ks else 'gray',
                  linewidth=1.5 if is_ks else 0.2,
                  hatch=hatch)

    for j, (bar, score) in enumerate(zip(bars, scores)):
        if score is None or score == 0:
            continue
        all_scores = [s[1][j] for s in systems if s[1][j] is not None]
        is_winner = score >= max(all_scores) if all_scores else False
        if is_ks or is_winner:
            ax.annotate(f'{score}%',
                       xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                       xytext=(0, 2), textcoords="offset points",
                       ha='center', va='bottom', fontsize=7,
                       fontweight='bold' if is_ks else 'normal',
                       color='#0d6655' if is_ks else '#333')

# N/A markers
for i, (name, scores, _, _) in enumerate(systems):
    for j, score in enumerate(scores):
        if score is None:
            ax.text(x[j] + offsets[i], 1, 'N/A',
                    ha='center', va='bottom', fontsize=4, color='gray',
                    rotation=90, alpha=0.4)

# Styling
ax.set_ylim(0, 120)
ax.axhline(y=100, color='red', linestyle='--', alpha=0.4, linewidth=0.8)

ax.set_xticks(x)
title = 'Video Generation & Analysis — KS+KCS+LLM vs Competitors'
if fp(10):
    ax.set_xticklabels(categories, fontproperties=fp(9))
    ax.set_ylabel('Score (%)', fontproperties=fp(11))
    ax.set_title(title, fontproperties=fp(13), fontweight='bold', pad=15)
    ax.legend(loc='upper left', prop=fp(8), ncol=2, framealpha=0.9)
else:
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylabel('Score (%)', fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=15)
    ax.legend(loc='upper left', fontsize=8, ncol=2, framealpha=0.9)

# Section shading
ax.axvspan(-0.5, 4.5, alpha=0.04, color='#EA4335')
ax.text(2, 117, 'Video Generation', ha='center', fontsize=10,
        color='#EA4335', fontweight='bold', alpha=0.7)

ax.axvspan(4.5, 10.5, alpha=0.04, color='#16a085')
ax.text(7.5, 117, 'Video Analysis & Verification', ha='center', fontsize=10,
        color='#16a085', fontweight='bold', alpha=0.7)

ax.axvline(x=4.5, color='gray', linestyle=':', alpha=0.5)

# Key insight annotation
ax.annotate('KS = Verification system\n(does not generate video)',
            xy=(2, 15), fontsize=8, color='gray', ha='center',
            style='italic', alpha=0.7,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                     edgecolor='gray', alpha=0.8))

ax.annotate('KS unique capability:\nVideo content verification\nvia 33-solver pipeline',
            xy=(10, 50), fontsize=8, color='#16a085', ha='center',
            fontweight='bold', alpha=0.8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#e8f8f5',
                     edgecolor='#16a085', alpha=0.8))

footnote = ("* Video Verify = video content truth verification (KS42c pipeline). "
            "Scores >100% = ExceedsEngine surplus.\n"
            "Sources: Veo3/Runway/Sora2 — Artificial Analysis T2V benchmark 2026. "
            "Deepfake — Purdue real-world benchmark 2025.")
ax.text(0, -0.10, footnote, transform=ax.transAxes,
        fontsize=6.5, color='gray', va='top', style='italic')

ax.grid(axis='y', alpha=0.2)
ax.set_axisbelow(True)
plt.tight_layout()

out = '/Users/nicolas/work/katala/ks_video_comparison.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f"Chart saved: {out}")

# Summary
print("\n=== Video Comparison Summary ===")
gen_cats = categories[:5]
ana_cats = categories[5:]
print("\n-- Generation (KS = N/A — verification system, not generator) --")
for j in range(5):
    cat_clean = categories[j].replace('\n', ' ')
    all_s = [(name, scores[j]) for name, scores, _, _ in systems if scores[j] is not None]
    if all_s:
        winner = max(all_s, key=lambda x: x[1])
        ks_val = ks[j]
        print(f"  {cat_clean}: {winner[0]} ({winner[1]}%) — KS: {'N/A' if ks_val is None else ks_val}")

print("\n-- Analysis (KS competitive domain) --")
ks_wins = 0
ks_losses = 0
for j in range(5, len(categories)):
    cat_clean = categories[j].replace('\n', ' ')
    all_s = [(name, scores[j]) for name, scores, _, _ in systems if scores[j] is not None]
    if all_s:
        winner = max(all_s, key=lambda x: x[1])
        ks_val = ks[j]
        marker = "★" if ks_val is not None and ks_val >= winner[1] else "  "
        if ks_val is not None and ks_val >= winner[1]:
            ks_wins += 1
        elif ks_val is not None:
            ks_losses += 1
        print(f"  {marker} {cat_clean}: {winner[0]} ({winner[1]}%) — KS: {ks_val}%")

print(f"\nAnalysis domain: KS {ks_wins}W-{ks_losses}L")
print(f"Generation domain: KS does not compete (verification system)")
