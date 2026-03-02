#!/usr/bin/env python3
"""Generate two flowchart images for Youta:
1) Memory Hierarchy Flow (L0→L1→L2→L3 + quarantine + homeostasis layers)
2) Shirokuma System Flow (OpenClaw ↔ KS/KCS/Katala, Coding mode branch)

Uses matplotlib only (no graphviz dependency).
"""
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Hiragino Maru Gothic Pro', 'sans-serif']
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════
# COLOR PALETTE
# ══════════════════════════════════════════════
C_BG = "#0d1117"
C_BOX = "#161b22"
C_BORDER = "#30363d"
C_TEXT = "#e6edf3"
C_ACCENT = "#58a6ff"
C_GREEN = "#3fb950"
C_RED = "#f85149"
C_ORANGE = "#d29922"
C_PURPLE = "#bc8cff"
C_CYAN = "#39d353"
C_PINK = "#f778ba"

def draw_box(ax, x, y, w, h, label, color=C_ACCENT, fontsize=9, sublabel=None):
    """Draw a rounded box with label."""
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                         boxstyle="round,pad=0.15",
                         facecolor=color + "22", edgecolor=color,
                         linewidth=1.5, zorder=2)
    ax.add_patch(box)
    if sublabel:
        ax.text(x, y + 0.15, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color=C_TEXT, zorder=3)
        ax.text(x, y - 0.2, sublabel, ha="center", va="center",
                fontsize=fontsize - 2, color=color, zorder=3)
    else:
        ax.text(x, y, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color=C_TEXT, zorder=3)

def draw_arrow(ax, x1, y1, x2, y2, color=C_BORDER, label=None, style="->"):
    """Draw an arrow between two points."""
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=1.2),
                zorder=1)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.05, my + 0.12, label, ha="center", va="center",
                fontsize=7, color=color, zorder=3,
                bbox=dict(boxstyle="round,pad=0.1", facecolor=C_BG, edgecolor="none"))

def draw_diamond(ax, x, y, w, h, label, color=C_ORANGE, fontsize=8):
    """Draw a diamond (decision) shape."""
    verts = [(x, y + h/2), (x + w/2, y), (x, y - h/2), (x - w/2, y), (x, y + h/2)]
    from matplotlib.patches import Polygon
    diamond = Polygon(verts, closed=True, facecolor=color + "22",
                      edgecolor=color, linewidth=1.5, zorder=2)
    ax.add_patch(diamond)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=C_TEXT, zorder=3)


# ══════════════════════════════════════════════
# CHART 1: Memory Hierarchy Flow
# ══════════════════════════════════════════════
def generate_memory_flowchart():
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.set_xlim(-1, 13)
    ax.set_ylim(-1, 9)
    ax.axis("off")

    # Title
    ax.text(6, 8.5, "しろくま記憶階層フロー (Memory Hierarchy)", ha="center",
            fontsize=16, fontweight="bold", color=C_ACCENT,
            fontfamily="sans-serif")
    ax.text(6, 8.1, "Tay化防止 — USBメモリ型 → 恒常性制御系", ha="center",
            fontsize=10, color=C_ORANGE)

    # Memory levels (left column)
    draw_box(ax, 2, 7, 3, 0.8, "L0: Ephemeral", C_ACCENT, sublabel="セッション内・揮発性")
    draw_box(ax, 2, 5.5, 3, 0.8, "L1: Daily", C_GREEN, sublabel="memory/YYYY-MM-DD.md")
    draw_box(ax, 2, 4, 3, 0.8, "L2: Long-term", C_PURPLE, sublabel="MEMORY.md")
    draw_box(ax, 2, 2.5, 3, 0.8, "L3: Core", C_PINK, sublabel="SOUL.md / IDENTITY.md")

    # Promotion gates (center column)
    draw_diamond(ax, 6, 6.25, 2.2, 0.7, "Quick Bias\nCheck", C_ORANGE, fontsize=7)
    draw_diamond(ax, 6, 4.75, 2.2, 0.7, "KS42c Full\nVerification", C_RED, fontsize=7)
    draw_diamond(ax, 6, 3.25, 2.2, 0.7, "Human\nApproval", C_RED, fontsize=7)

    # Arrows: L0→Gate→L1→Gate→L2→Gate→L3
    draw_arrow(ax, 3.5, 7, 4.9, 6.4, C_GREEN, "promote?")
    draw_arrow(ax, 7.1, 6.1, 3.5, 5.7, C_GREEN, "PASS")
    draw_arrow(ax, 3.5, 5.3, 4.9, 4.9, C_PURPLE, "promote?")
    draw_arrow(ax, 7.1, 4.6, 3.5, 4.2, C_PURPLE, "PASS")
    draw_arrow(ax, 3.5, 3.8, 4.9, 3.4, C_PINK, "promote?")
    draw_arrow(ax, 7.1, 3.1, 3.5, 2.7, C_PINK, "PASS")

    # Quarantine (right)
    draw_box(ax, 10.5, 5.5, 2.8, 0.8, "🔒 Quarantine", C_RED,
             sublabel="隔離・人間承認のみ解除")

    # Arrows to quarantine
    draw_arrow(ax, 7.1, 6.5, 9.1, 5.7, C_RED, "TOXIC/FAIL")
    draw_arrow(ax, 7.1, 5, 9.1, 5.4, C_RED, "FAIL")

    # Homeostasis layers (right column)
    draw_box(ax, 10.5, 7.5, 2.8, 0.6, "① 汚染遮断層", C_CYAN, fontsize=8,
             sublabel="quarantine default")
    draw_box(ax, 10.5, 4.2, 2.8, 0.6, "② 反証探索層", C_CYAN, fontsize=8,
             sublabel="逆証拠必須探索")
    draw_box(ax, 10.5, 3.4, 2.8, 0.6, "③ 自己同一性層", C_CYAN, fontsize=8,
             sublabel="SOUL/ID矛盾→自動拒否")
    draw_box(ax, 10.5, 2.6, 2.8, 0.6, "④ 時間減衰層", C_CYAN, fontsize=8,
             sublabel="未確証記憶→自然劣化")
    draw_box(ax, 10.5, 1.8, 2.8, 0.6, "⑤ 行動検証層", C_CYAN, fontsize=8,
             sublabel="発話<行動結果で再採点")

    # Demotion arrow
    draw_arrow(ax, 2, 2.9, 2, 3.6, C_ORANGE, "demote\n(health<0.2)", style="<-")

    # HTLF axis labels
    ax.text(6, 7.5, "R_qualia", ha="center", fontsize=7, color=C_ORANGE, style="italic")
    ax.text(6, 5.8, "R_context", ha="center", fontsize=7, color=C_ORANGE, style="italic")
    ax.text(6, 4.3, "R_struct", ha="center", fontsize=7, color=C_ORANGE, style="italic")

    # Legend
    ax.text(0, 0.5, "HTLF翻訳: L0→L1=R_qualia, L1→L2=R_context, L2→L3=R_struct",
            fontsize=8, color=C_ACCENT)
    ax.text(0, 0, "health_score = 0.6×corroboration + 0.4×confidence | <0.2 → demotion",
            fontsize=7, color=C_BORDER)

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "shirokuma_memory_flow.png")
    fig.savefig(path, dpi=150, facecolor=C_BG, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ Memory flowchart: {path}")
    return path


# ══════════════════════════════════════════════
# CHART 2: Shirokuma System Flow
# ══════════════════════════════════════════════
def generate_system_flowchart():
    fig, ax = plt.subplots(figsize=(16, 10))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.set_xlim(-1, 15)
    ax.set_ylim(-1, 9)
    ax.axis("off")

    # Title
    ax.text(7, 8.5, "しろくまシステムフロー (Shirokuma Architecture)", ha="center",
            fontsize=16, fontweight="bold", color=C_ACCENT)
    ax.text(7, 8.1, "OpenClaw ↔ Katala連携 + Codingモード分岐", ha="center",
            fontsize=10, color=C_ORANGE)

    # Input layer (left)
    draw_box(ax, 1.5, 6.5, 2.5, 0.7, "📥 Discord/LINE", C_ACCENT, fontsize=9,
             sublabel="ユーザ入力")

    # OpenClaw core
    draw_box(ax, 5, 6.5, 2.5, 0.7, "🐾 OpenClaw", C_GREEN, fontsize=9,
             sublabel="Gateway + Agent")

    # ModeGate decision
    draw_diamond(ax, 8.5, 6.5, 2, 0.7, "ModeGate\nCodingモード?", C_ORANGE, fontsize=7)

    # Normal path (top)
    draw_box(ax, 12, 7.5, 2.5, 0.6, "通常フロー", C_ACCENT, fontsize=9,
             sublabel="LLM応答")

    # Coding mode path (bottom) — full pipeline
    draw_box(ax, 8.5, 4.8, 2, 0.6, "LLM生成", C_PURPLE, fontsize=9)
    draw_box(ax, 8.5, 3.8, 2, 0.6, "KS検証", C_GREEN, fontsize=9,
             sublabel="confidence/bias")
    draw_box(ax, 8.5, 2.8, 2, 0.6, "KCS検証", C_CYAN, fontsize=9,
             sublabel="code+text gate")
    draw_diamond(ax, 8.5, 1.8, 2.2, 0.6, "Approver\n承認?", C_RED, fontsize=7)
    draw_box(ax, 5, 1.8, 2.5, 0.6, "❌ Read-Only", C_RED, fontsize=9,
             sublabel="実行不可")
    draw_box(ax, 12, 1.8, 2.5, 0.6, "✅ Execute", C_GREEN, fontsize=9,
             sublabel="変更実行")

    # Arrows: Input → OpenClaw → ModeGate
    draw_arrow(ax, 2.75, 6.5, 3.75, 6.5, C_ACCENT)
    draw_arrow(ax, 6.25, 6.5, 7.5, 6.5, C_ACCENT)

    # ModeGate → Normal (top)
    draw_arrow(ax, 9.5, 6.85, 10.75, 7.5, C_ACCENT, "Normal")

    # ModeGate → Coding pipeline (bottom)
    draw_arrow(ax, 8.5, 6.15, 8.5, 5.1, C_ORANGE, "Codingモード")
    draw_arrow(ax, 8.5, 4.5, 8.5, 4.1, C_GREEN)
    draw_arrow(ax, 8.5, 3.5, 8.5, 3.1, C_CYAN)
    draw_arrow(ax, 8.5, 2.5, 8.5, 2.1, C_RED)

    # Approver → Execute / Read-only
    draw_arrow(ax, 7.4, 1.8, 6.25, 1.8, C_RED, "DENIED")
    draw_arrow(ax, 9.6, 1.8, 10.75, 1.8, C_GREEN, "GRANTED")

    # Katala connection (right side)
    draw_box(ax, 13, 4.8, 2.2, 2.8, "", C_PURPLE)
    ax.text(13, 5.8, "Katala", ha="center", fontsize=11, fontweight="bold",
            color=C_PURPLE, zorder=3)
    ax.text(13, 5.3, "KS42c (33 solvers)", ha="center", fontsize=7,
            color=C_TEXT, zorder=3)
    ax.text(13, 4.9, "KCS-1b (5-axis)", ha="center", fontsize=7,
            color=C_TEXT, zorder=3)
    ax.text(13, 4.5, "HTLF (翻訳損失)", ha="center", fontsize=7,
            color=C_TEXT, zorder=3)
    ax.text(13, 4.1, "KS Engine (Rust)", ha="center", fontsize=7,
            color=C_TEXT, zorder=3)
    ax.text(13, 3.7, "ModeGate (Rust)", ha="center", fontsize=7,
            color=C_ORANGE, zorder=3)

    # Connection arrows to Katala
    draw_arrow(ax, 9.5, 3.8, 11.9, 4.5, C_GREEN, "verify()")
    draw_arrow(ax, 9.5, 2.8, 11.9, 3.8, C_CYAN, "kcs_check()")

    # AuditLog
    draw_box(ax, 2, 3.5, 2.5, 0.6, "📋 AuditLog", C_ORANGE, fontsize=9,
             sublabel="append-only 監査")
    draw_arrow(ax, 7.4, 1.6, 3.25, 3.2, C_ORANGE, "log events")

    # Memory hierarchy connection
    draw_box(ax, 2, 5, 2.5, 0.6, "🧠 記憶階層", C_PURPLE, fontsize=9,
             sublabel="L0→L1→L2→L3")
    draw_arrow(ax, 3.75, 6.2, 3.25, 5.3, C_PURPLE, "memory write")

    # Approver IDs
    ax.text(5, 0.8, "Approvers: Youta (918103131538194452) + Nicolas (259231974760120321)",
            fontsize=8, color=C_ORANGE)
    ax.text(5, 0.3, "Trigger: メッセージに「Codingモード」含む → pipeline切替",
            fontsize=8, color=C_BORDER)

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "shirokuma_system_flow.png")
    fig.savefig(path, dpi=150, facecolor=C_BG, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ System flowchart: {path}")
    return path


if __name__ == "__main__":
    p1 = generate_memory_flowchart()
    p2 = generate_system_flowchart()
    print(f"\nDone. Files:\n  {p1}\n  {p2}")
