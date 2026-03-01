#!/usr/bin/env python3
"""
KS System Architecture Flowchart — Full pipeline overview.
Youta: "現在のシステムのフローチャートも見せて"
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import os

CJK_FONTS = [
    '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
]
font_path = next((f for f in CJK_FONTS if os.path.exists(f)), None)
fp = lambda sz: fm.FontProperties(fname=font_path, size=sz) if font_path else None


def box(ax, x, y, w, h, text, fc='#ecf0f1', ec='#2c3e50',
        fs=9, bold=False, tc='#2c3e50'):
    p = mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                 facecolor=fc, edgecolor=ec,
                                 linewidth=1.5, alpha=0.95)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fs, fontweight='bold' if bold else 'normal',
            color=tc, fontproperties=fp(fs), linespacing=1.4)


def arrow(ax, x1, y1, x2, y2, c='#7f8c8d', lw=1.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=c, lw=lw))


fig, ax = plt.subplots(figsize=(30, 24))
ax.set_xlim(0, 30)
ax.set_ylim(0, 24)
ax.set_aspect('equal')
ax.axis('off')
fig.patch.set_facecolor('white')

# ── TITLE ──
ax.text(15, 23.3, "Katala System Architecture", ha='center', fontsize=20,
        fontweight='bold', color='#2c3e50', fontproperties=fp(20))
ax.text(15, 22.8, "186 modules | 82K+ lines | 33 solvers | 22+ KS classes | 43 Rust functions",
        ha='center', fontsize=10, color='#7f8c8d', fontproperties=fp(10))

# ══════════════════════════════════════════════════════
# LAYER 0: INPUTS (top)
# ══════════════════════════════════════════════════════
Y = 21.0
inputs = [
    (0.5, "📝 Text\nClaims, Articles", '#d5f5e3', '#27ae60'),
    (5.0, "🖼️ Image\nPhotos, OCR", '#d6eaf8', '#2980b9'),
    (9.5, "🎵 Audio\nMusic, Speech", '#fdebd0', '#e67e22'),
    (14.0, "🎬 Video\nClips, Streams", '#fadbd8', '#e74c3c'),
    (18.5, "💻 Code\nSource, Design", '#e8daef', '#8e44ad'),
    (23.0, "🎹 Music\nMIDI, Score", '#fef9e7', '#f39c12'),
]
for x, txt, fc, ec in inputs:
    box(ax, x, Y, 4.0, 0.9, txt, fc, ec, 8)

# ── ⓪ MULTIMODAL INPUT LAYER ──
Y_mm = 19.3
box(ax, 0.5, Y_mm, 26.5, 1.1,
    "⓪ MultimodalInputLayer\n"
    "TextProcessor  |  ImageProcessor (CLIP ViT-B-32)  |  AudioProcessor (Whisper)  |  VideoProcessor",
    '#eaf2f8', '#2c3e50', 10, True)

for x, *_ in inputs:
    arrow(ax, x + 2.0, Y, x + 2.0, Y_mm + 1.1)

# ── JUDGMENT LAYER ──
Y_j = 17.5
box(ax, 0.5, Y_j, 26.5, 1.1,
    "ModalityJudge — 判断層\n"
    "Validity Check  |  Cross-Modal Contradiction Detection  |  Solver Weight Hints\n"
    "↕ Bidirectional with Input Layer AND _parse()",
    '#fef9e7', '#f39c12', 9, True)

arrow(ax, 13.75, Y_mm, 13.75, Y_j + 1.1, '#f39c12', 2)

# ── CROSS-MODAL SOLVER ENGINE ──
Y_cm = 15.7
box(ax, 0.5, Y_cm, 26.5, 1.1,
    "CrossModalSolverEngine (6 components)\n"
    "ModalSolverBridge  |  ContradictionAmplifier  |  ParallelModalityPath\n"
    "AdaptiveWeightEngine  |  ConsistencyVerifier  |  SafetyAlignmentWeave",
    '#f5eef8', '#8e44ad', 9, True)

arrow(ax, 13.75, Y_j, 13.75, Y_cm + 1.1, '#8e44ad', 2)

# ── _parse() + HTLF ──
Y_p = 13.7
box(ax, 0.5, Y_p, 12.5, 1.2,
    "_parse() — Proposition Extraction\n"
    "parse_bridge.py: 35 features (Rust backend)\n"
    "ks29 / ks30 / ks30c propositional logic",
    '#d5f5e3', '#27ae60', 9)

box(ax, 14.0, Y_p, 13.0, 1.2,
    "HTLF Pipeline — 5-axis Translation Loss\n"
    "R_struct  |  R_context  |  R_qualia  |  R_cultural  |  R_temporal\n"
    "parser → matcher → scorer → classifier (12 profiles)",
    '#d6eaf8', '#2980b9', 9)

arrow(ax, 6.75, Y_cm, 6.75, Y_p + 1.2)
arrow(ax, 20.5, Y_cm, 20.5, Y_p + 1.2)

# ── SOLVER POOL ──
Y_s = 11.3
box(ax, 0.3, Y_s, 6.5, 1.7,
    "Structural Solvers\n(S01-S28)\n"
    "SAT / Modal / Probabilistic\n"
    "Temporal / Deontic / Topo\n"
    "Analogical / Game Theory",
    '#eaf2f8', '#2980b9', 8)

box(ax, 7.3, Y_s, 6.5, 1.7,
    "Semantic Truth\n(S29-S33)\n"
    "Known-false (12 patterns)\n"
    "Self-contradiction detect\n"
    "Weasel / Data / Known-true",
    '#fdebd0', '#e67e22', 8)

box(ax, 14.3, Y_s, 6.0, 1.7,
    "Perception Engines\n"
    "Image (CLIP) | Audio (Whisper)\n"
    "Video (optical flow, deepfake)\n"
    "Music (5-axis MIR)\n"
    "OCR (HandwritingKCS)",
    '#fadbd8', '#e74c3c', 8)

box(ax, 20.8, Y_s, 6.5, 1.7,
    "Meta / Boost\n"
    "ExceedsEngine (110%, 4 comp)\n"
    "AxisMaxBoost v2.0 (10 comp)\n"
    "SolverQuality / Orthogonality\n"
    "SolverRouter (adaptive)",
    '#e8daef', '#8e44ad', 8)

arrow(ax, 3.5, Y_p, 3.5, Y_s + 1.7)
arrow(ax, 6.75, Y_p, 10.5, Y_s + 1.7)
arrow(ax, 17.0, Y_p, 17.3, Y_s + 1.7)
arrow(ax, 20.5, Y_p, 24.0, Y_s + 1.7)

# ── KS MRO CHAIN ──
Y_mro = 9.4
box(ax, 0.3, Y_mro, 27.0, 1.2,
    "KS MRO Chain (22+ classes)\n"
    "KS42c → KS42b (Self-Reflective 4-layer) → KS42a (Evolutionary) → KS41b (Goal Planning) → KS41a → KS40b (HTLF) →\n"
    "KS40a → KS39b (Self-Other Boundary) → ... → KS31e (Ensemble) → KS30d (33-solver weighted) → KS29 (Propositional)",
    '#f0f0f0', '#2c3e50', 9, True)

for x in [3.5, 10.5, 17.3, 24.0]:
    arrow(ax, x, Y_s, x, Y_mro + 1.2)

# ── KCS + AGENT + GENERATION ──
Y_mid = 7.4

box(ax, 0.3, Y_mid, 8.5, 1.3,
    "KCS — Code Verification\n"
    "KCS-1b: 5-axis design→code fidelity\n"
    "KCS-2a: Reverse intent inference\n"
    "156 modules scanned (A5 B99 C46 D6)",
    '#e8daef', '#8e44ad', 8)

box(ax, 9.3, Y_mid, 8.5, 1.3,
    "Agent System\n"
    "KS Agent (PEV Loop) | HTN Planner\n"
    "SubgoalResolver | GoalEmergence\n"
    "EpisodicMemory | Checkpoint",
    '#d5f5e3', '#27ae60', 8)

box(ax, 18.3, Y_mid, 9.0, 1.3,
    "Generation Engines\n"
    "AudioToVideo (8 moods × 12 genres)\n"
    "LoFi Synth (Pure Python FM)\n"
    "CodeGen | Multilingual | LongCtx | MathProof",
    '#fef9e7', '#f39c12', 8)

arrow(ax, 4.5, Y_mro, 4.5, Y_mid + 1.3)
arrow(ax, 13.5, Y_mro, 13.5, Y_mid + 1.3)
arrow(ax, 22.5, Y_mro, 22.8, Y_mid + 1.3)

# KCS ↔ Agent feedback
ax.annotate('', xy=(4.5, Y_mid + 0.65), xytext=(9.3, Y_mid + 0.65),
            arrowprops=dict(arrowstyle='<->', color='#8e44ad', lw=2,
                           connectionstyle='arc3,rad=0.3'))
ax.text(6.9, Y_mid + 0.2, 'feedback\nloop', fontsize=7, ha='center',
        color='#8e44ad', style='italic', fontproperties=fp(7))

# ── RUST LAYER ──
Y_r = 5.5
box(ax, 0.3, Y_r, 13.5, 1.2,
    "🦀 Rust Acceleration\n"
    "rust_accel (PyO3): 43 functions  |  parse_bridge backend\n"
    "KS Engine (Rust binary): 27 native solvers, tiny_http  |  ~5μs/claim",
    '#fce4ec', '#c0392b', 9, True)

box(ax, 14.3, Y_r, 13.0, 1.2,
    "Infrastructure\n"
    "SemanticCache (n-gram)  |  Checkpoint  |  ComputeRouter (MPS/CPU)\n"
    "ExpertReasoning  |  CrossDomainTransfer  |  AnticipatoryEngine  |  TemporalContext",
    '#eaf2f8', '#2980b9', 8)

arrow(ax, 4.5, Y_mid, 7.0, Y_r + 1.2, '#c0392b')
arrow(ax, 13.5, Y_mid, 20.8, Y_r + 1.2)

# ── KS LIVE ──
Y_live = 3.7
box(ax, 3.0, Y_live, 22.0, 1.1,
    "🔴 KS Live — Always-on Verification Endpoint\n"
    "POST /verify → L1 lightweight → full KS42c pipeline  |  Per-channel ON/OFF  |  OpenClaw integration",
    '#fce4ec', '#e74c3c', 10, True)

arrow(ax, 7.0, Y_r, 10.0, Y_live + 1.1, '#e74c3c', 2)
arrow(ax, 20.8, Y_r, 20.0, Y_live + 1.1, '#e74c3c', 2)

# ── OUTPUTS ──
Y_o = 1.8
outputs = [
    (0.5, 5.0, "✅ Verification\nVERIFIED / UNVERIFIED\nconfidence + evidence", '#d5f5e3', '#27ae60'),
    (6.0, 5.0, "📊 Translation Loss\nHTLF 5-axis score\n12 loss profiles", '#d6eaf8', '#2980b9'),
    (11.5, 5.0, "🎵 Audio Output\nLoFi / Music\nWAV / MP3 / MIDI", '#fdebd0', '#e67e22'),
    (17.0, 5.0, "🎬 Video Spec\nScene descriptions\nAV sync verified", '#fadbd8', '#e74c3c'),
    (22.5, 5.0, "💻 Code Fixes\nKCS-guided\ndesign→code", '#e8daef', '#8e44ad'),
]
for x, w, txt, fc, ec in outputs:
    box(ax, x, Y_o, w, 1.0, txt, fc, ec, 8, True)

xs_out = [3.0, 8.5, 14.0, 19.5, 25.0]
for x in xs_out:
    arrow(ax, x, Y_live, x, Y_o + 1.0)

# ── STATS BOX ──
box(ax, 20.0, 20.0, 7.3, 2.3,
    "System Stats (2026-03-02)\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "18-axis AGI:   101.1% (18W-0L)\n"
    "OCR 8-cat:     100.5% (8W-0L)\n"
    "Music 5-ax:      94.4%\n"
    "Video Analysis:   8W-0L\n"
    "Full 16-cat:    16W-0L vs 8 competitors",
    '#f0f0f0', '#2c3e50', 8, tc='#2c3e50')

# ── FOOTER ──
ax.text(15, 0.5, "Designed by Youta Hilono  |  Implemented by Shirokuma 🐻‍❄️  |  Katala Framework 2026",
        ha='center', fontsize=9, color='#95a5a6', style='italic',
        fontproperties=fp(9))

plt.tight_layout()
out = '/Users/nicolas/work/katala/ks_system_flowchart.png'
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f"Flowchart saved: {out}")
