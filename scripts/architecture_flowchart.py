"""Generate KS architecture flowchart — visual overview of 78K lines."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm

# Japanese font
_jp_fonts = [f.fname for f in fm.fontManager.ttflist if 'Hiragino' in f.name or 'IPAex' in f.name or 'Noto Sans CJK' in f.name]
if _jp_fonts:
    plt.rcParams['font.family'] = fm.FontProperties(fname=_jp_fonts[0]).get_name()
else:
    plt.rcParams['font.family'] = 'sans-serif'

fig, ax = plt.subplots(1, 1, figsize=(22, 16))
ax.set_xlim(0, 22)
ax.set_ylim(0, 16)
ax.axis('off')

# Colors
C_INPUT = '#E3F2FD'     # Light blue
C_CORE = '#FFF3E0'      # Light orange
C_ENGINE = '#E8F5E9'    # Light green
C_RUST = '#FCE4EC'      # Light pink
C_OUTPUT = '#F3E5F5'    # Light purple
C_MULTI = '#E0F7FA'     # Light cyan
C_AGENT = '#FFF8E1'     # Light yellow
C_ARROW = '#455A64'

def box(x, y, w, h, text, color, fontsize=8, bold=False):
    rect = mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                                     facecolor=color, edgecolor='#37474F', linewidth=1.2)
    ax.add_patch(rect)
    weight = 'bold' if bold else 'normal'
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fontsize, fontweight=weight, wrap=True)

def arrow(x1, y1, x2, y2, style='->', color=C_ARROW, lw=1.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw))

def section_label(x, y, text, fontsize=11):
    ax.text(x, y, text, fontsize=fontsize, fontweight='bold', color='#1A237E',
            ha='center', va='center')

# ═══════════════════════════════════════════════════════════
# Title
# ═══════════════════════════════════════════════════════════
ax.text(11, 15.5, 'Katala Samurai — 全体アーキテクチャ (78,000行)', 
        fontsize=16, fontweight='bold', ha='center', va='center', color='#1A237E')
ax.text(11, 15.1, 'commit f13ef08 | Python 178モジュール + Rust 2,584行 | 18軸AGIベンチマーク',
        fontsize=9, ha='center', va='center', color='#546E7A')

# ═══════════════════════════════════════════════════════════
# Layer 1: INPUT (top)
# ═══════════════════════════════════════════════════════════
section_label(11, 14.5, '① 入力層')

box(1, 13.7, 3.5, 0.7, 'テキスト入力\n(claim / document)', C_INPUT, 8, True)
box(5.5, 13.7, 3.5, 0.7, 'コード入力\n(design + code)', C_INPUT, 8, True)
box(10, 13.7, 3.5, 0.7, '多言語入力\n(9言語自動検出)', C_INPUT, 8, True)
box(14.5, 13.7, 3.5, 0.7, '数式入力\n(LaTeX / Unicode)', C_INPUT, 8, True)
box(19, 13.7, 2.5, 0.7, '長文入力\n(論文等)', C_INPUT, 8, True)

# ═══════════════════════════════════════════════════════════
# Layer 2: PARSING & DETECTION
# ═══════════════════════════════════════════════════════════
section_label(11, 13, '② 解析層 — HTLF 5軸パイプライン')

box(0.5, 11.8, 3, 1, 'parser.py\nDAG構築\n(概念→辺)', C_CORE, 7)
box(4, 11.8, 3, 1, 'matcher.py\n概念マッチング\n(BERT embedding)', C_CORE, 7)
box(7.5, 11.8, 3, 1, 'scorer.py\n5軸スコア\nRs/Rc/Rq/Rcl/Rt', C_CORE, 7)
box(11, 11.8, 3, 1, 'classifier.py\n12プロファイル\n自動分類', C_CORE, 7)
box(14.5, 11.8, 3, 1, 'multilingual\n言語検出\nトークナイズ', C_MULTI, 7)
box(18, 11.8, 3.5, 1, 'math_proof.py\n式パース\nSymPy/Z3', C_MULTI, 7)

# Arrows from input to parsing
arrow(2.75, 13.7, 2, 12.8)
arrow(7.25, 13.7, 5.5, 12.8)
arrow(11.75, 13.7, 16, 12.8)
arrow(16.25, 13.7, 19.75, 12.8)
arrow(20.25, 13.7, 19.75, 12.8)

# ═══════════════════════════════════════════════════════════
# Layer 3: VERIFICATION ENGINE (MRO chain)
# ═══════════════════════════════════════════════════════════
section_label(11, 11.1, '③ 検証エンジン — KS MROチェーン (22クラス)')

# MRO chain boxes
mro_y = 9.8
box(0.3, mro_y, 2.2, 0.9, 'KS31e\nBase\nVerifier', C_ENGINE, 7)
box(2.8, mro_y, 1.5, 0.9, '...', C_ENGINE, 9)
box(4.6, mro_y, 2.2, 0.9, 'KS39b\nSelf-Other\nBoundary', C_ENGINE, 7)
box(7.1, mro_y, 2.2, 0.9, 'KS40b\nHTLF\n5軸統合', C_ENGINE, 7, True)
box(9.6, mro_y, 2.2, 0.9, 'KS41b\nGoal\nPlanning', C_ENGINE, 7)
box(12.1, mro_y, 2.2, 0.9, 'KS42a\nEvolutionary\nAbstract', C_ENGINE, 7)
box(14.6, mro_y, 2.2, 0.9, 'KS42b\nSelf-\nReflective', C_ENGINE, 7)
box(17.1, mro_y, 2.5, 0.9, 'KS42c ★\n統合検証\n(最新)', C_ENGINE, 7, True)
box(20, mro_y, 1.7, 0.9, 'Axis96\nBoost', C_ENGINE, 7)

# MRO arrows
for x in [2.5, 4.3, 6.8, 9.3, 11.8, 14.3, 16.8, 19.6]:
    arrow(x, mro_y + 0.45, x + 0.3, mro_y + 0.45, '->', C_ARROW, 1)

# Connection from parsing to MRO
arrow(5, 11.8, 8.2, 10.7)
arrow(9, 11.8, 10.7, 10.7)

# ═══════════════════════════════════════════════════════════
# Layer 4: SOLVERS (33 total)
# ═══════════════════════════════════════════════════════════
section_label(11, 9.2, '④ ソルバー層 — 33ソルバー (10種フレームワーク)')

sol_y = 8.0
box(0.3, sol_y, 4, 0.9, 'S01-S27: 構造SAT\n(Boolean充足可能性)\n27ソルバー', '#E8EAF6', 7)
box(4.8, sol_y, 4, 0.9, 'S28: LLM Consensus\n(Gemini/Ollama)\n1ソルバー', '#E8EAF6', 7)
box(9.3, sol_y, 4, 0.9, 'S29-S33: 意味的真理\n(known-false/true/矛盾)\n5ソルバー', '#E8EAF6', 7, True)
box(13.8, sol_y, 3.8, 0.9, 'Solver Router\n適応的ルーティング\nドメイン分類', '#E8EAF6', 7)
box(18, sol_y, 3.5, 0.9, 'Solver Quality\n直交性測定\nESS計算', '#E8EAF6', 7)

# Connection from MRO to solvers
arrow(18.35, mro_y, 11.3, 8.9)

# ═══════════════════════════════════════════════════════════
# Layer 5: AGENT & SELF-IMPROVEMENT
# ═══════════════════════════════════════════════════════════
section_label(5, 7.3, '⑤ エージェント層')

agent_y = 6.0
box(0.3, agent_y, 2.8, 1, 'PEV Loop\nPredict→\nExecute→Verify', C_AGENT, 7)
box(3.4, agent_y, 2.8, 1, 'HDEL\n仮説駆動\n探索ループ', C_AGENT, 7)
box(6.5, agent_y, 2.8, 1, 'Session\nState\nManager', C_AGENT, 7)

# Agent sub-engines
box(0.3, 4.7, 2.8, 1, 'Subgoal\nResolver\n(失敗→分解)', C_AGENT, 7)
box(3.4, 4.7, 2.8, 1, 'Goal\nEmergence\n(新目標発見)', C_AGENT, 7)
box(6.5, 4.7, 2.8, 1, 'Anticipatory\nEngine\n(予測→先制)', C_AGENT, 7)

arrow(1.7, agent_y, 1.7, 5.7)
arrow(4.8, agent_y, 4.8, 5.7)
arrow(7.9, agent_y, 7.9, 5.7)

# ═══════════════════════════════════════════════════════════
# Layer 5b: MULTIMODAL ENGINES (right side)
# ═══════════════════════════════════════════════════════════
section_label(16.5, 7.3, '⑥ マルチモーダル層')

mm_y = 6.0
box(10, mm_y, 3, 1, 'Code Gen\nEngine\n(KCSフィードバック)', C_MULTI, 7, True)
box(13.3, mm_y, 3, 1, 'Long Context\nEngine\n(chunk→verify)', C_MULTI, 7, True)
box(16.6, mm_y, 2.8, 1, 'Math Proof\nEngine\n(SymPy+Z3)', C_MULTI, 7, True)
box(19.7, mm_y, 2, 1, 'Multilingual\nVerifier\n(9言語)', C_MULTI, 7, True)

# ═══════════════════════════════════════════════════════════
# Layer 5c: MEMORY & LEARNING
# ═══════════════════════════════════════════════════════════
section_label(16.5, 4.5, '⑦ 記憶・学習層')

mem_y = 3.3
box(10, mem_y, 2.8, 1, 'Episodic\nMemory\n(成功パターン)', '#FFF9C4', 7)
box(13.1, mem_y, 2.8, 1, 'Expert\nReasoning\n(10ドメイン)', '#FFF9C4', 7)
box(16.2, mem_y, 2.8, 1, 'Cross-Domain\nTransfer\n(構造同型)', '#FFF9C4', 7)
box(19.3, mem_y, 2.4, 1, 'Semantic\nCache\n(n-gram)', '#FFF9C4', 7)

# ═══════════════════════════════════════════════════════════
# Layer 6: RUST ENGINE (bottom)
# ═══════════════════════════════════════════════════════════
section_label(11, 2.5, '⑧ Rust高速化層')

rust_y = 1.2
box(0.3, rust_y, 5, 1, 'rust_accel (PyO3)\n43関数 | 1,690行\nHTLF+parser+cultural+temporal', C_RUST, 7, True)
box(5.8, rust_y, 5, 1, 'ks_engine (Binary)\n33ソルバー | 894行\nHTTP server | ~5μs/claim', C_RUST, 7, True)
box(11.3, rust_y, 5, 1, 'KCS\nKCS-1a (forward) + KCS-1b (統合)\nKCS-2a (reverse inference)', C_CORE, 7, True)
box(16.8, rust_y, 4.8, 1, 'KS Live\n常時稼働エンドポイント\nper-channel ON/OFF', '#FFCDD2', 7, True)

# Connection arrows from KS42c down to Rust
arrow(18.35, mro_y, 2.8, 2.2)
arrow(18.35, mro_y, 8.3, 2.2)
arrow(18.35, mro_y, 13.8, 2.2)

# ═══════════════════════════════════════════════════════════
# Output indicator
# ═══════════════════════════════════════════════════════════
box(0.3, 0.1, 21.4, 0.7, '出力: PASS/FAIL/UNVERIFIED + 5軸スコア (Rs/Rc/Rq/Rcl/Rt) + 信頼度 + 修正提案 + 目標生成', 
    C_OUTPUT, 9, True)

# ═══════════════════════════════════════════════════════════
# Legend
# ═══════════════════════════════════════════════════════════
legend_items = [
    (C_INPUT, '入力'), (C_CORE, 'コア'), (C_ENGINE, 'KS検証'),
    (C_MULTI, 'マルチモーダル'), (C_AGENT, 'エージェント'),
    (C_RUST, 'Rust'), ('#FFF9C4', '記憶'), (C_OUTPUT, '出力'),
]
for i, (color, label) in enumerate(legend_items):
    x = 0.5 + i * 2.7
    rect = mpatches.FancyBboxPatch((x, 15.8), 0.4, 0.3, boxstyle="round,pad=0.05",
                                     facecolor=color, edgecolor='#37474F', linewidth=0.8)
    ax.add_patch(rect)
    ax.text(x + 0.55, 15.95, label, fontsize=7, va='center')

plt.tight_layout()
plt.savefig('/Users/nicolas/work/katala/ks_architecture.png', dpi=150, bbox_inches='tight')
print("✅ Architecture flowchart saved to ks_architecture.png")
