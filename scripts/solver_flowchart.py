"""Generate detailed solver flowchart with color-coded categories."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import numpy as np

# Japanese font
_jp_fonts = [f.fname for f in fm.fontManager.ttflist if 'Hiragino' in f.name or 'IPAex' in f.name or 'Noto Sans CJK' in f.name]
if _jp_fonts:
    plt.rcParams['font.family'] = fm.FontProperties(fname=_jp_fonts[0]).get_name()
else:
    plt.rcParams['font.family'] = 'sans-serif'

fig, ax = plt.subplots(1, 1, figsize=(24, 18))
ax.set_xlim(0, 24)
ax.set_ylim(0, 18)
ax.axis('off')

# Colors
C_INPUT = '#E3F2FD'
C_PARSE = '#FFF3E0'
C_SAT = '#C8E6C9'       # Green - structural SAT
C_LLM = '#B3E5FC'       # Blue - LLM consensus
C_SEMANTIC = '#FFCDD2'   # Red - semantic truth
C_ROUTER = '#E1BEE7'     # Purple - routing
C_QUALITY = '#FFE0B2'    # Orange - quality
C_OUTPUT = '#F3E5F5'
C_VOTE = '#FFF9C4'       # Yellow - voting
C_MULTI = '#B2DFDB'      # Teal - multimodal

def box(x, y, w, h, text, color, fontsize=7, bold=False):
    rect = mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                     facecolor=color, edgecolor='#37474F', linewidth=1)
    ax.add_patch(rect)
    weight = 'bold' if bold else 'normal'
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fontsize, fontweight=weight)

def arrow(x1, y1, x2, y2, color='#455A64', lw=1.2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw))

# ═══════════════════════════════════════════════════════════
# Title
# ═══════════════════════════════════════════════════════════
ax.text(12, 17.5, 'KS検証パイプライン — 33ソルバー詳細フローチャート', 
        fontsize=16, fontweight='bold', ha='center', color='#1A237E')
ax.text(12, 17.1, '入力 → 解析 → 33ソルバー投票 → 重み付け → 判定出力',
        fontsize=10, ha='center', color='#546E7A')

# ═══════════════════════════════════════════════════════════
# Step 1: INPUT
# ═══════════════════════════════════════════════════════════
box(9.5, 16.0, 5, 0.7, '入力テキスト\n"Water boils at 100°C" / "地球は平ら"', C_INPUT, 8, True)

arrow(12, 16.0, 12, 15.5)

# ═══════════════════════════════════════════════════════════
# Step 2: PARSING (_parse pipeline)
# ═══════════════════════════════════════════════════════════
ax.text(12, 15.4, '② _parse() パイプライン — 35特徴抽出', fontsize=10, fontweight='bold',
        ha='center', color='#E65100')

box(1, 14.2, 4.5, 1, '_parse() 35特徴\n• 品詞分布 (名詞/動詞/形容詞)\n• 数値リテラル検出\n• 引用パターン\n• 因果関係マーカー\n• 条件文検出', C_PARSE, 6.5)

box(6, 14.2, 4.5, 1, '命題抽出\n• テキスト → 命題集合 {p0, p1, ...}\n• 各命題にboolean値割当\n• SAT式構築\n• parse_bridge (Rust高速化)', C_PARSE, 6.5)

box(11, 14.2, 4.5, 1, 'HTLF 5軸測定\n• R_struct (構造保存)\n• R_context (文脈保存)\n• R_qualia (質感保存)\n• R_cultural (文化損失)\n• R_temporal (時間損失)', C_PARSE, 6.5)

box(16, 14.2, 4, 1, '多言語検出\n• 9言語自動判定\n  ja/zh/ko/fr/es/\n  pt/it/de/ar\n• 言語別トークナイズ', C_MULTI, 6.5)

box(20.5, 14.2, 3, 1, 'ドメイン分類\n• physics\n• biology\n• CS / math\n• 10ドメイン', C_ROUTER, 6.5)

# Arrows
arrow(12, 15.3, 3.25, 15.2)
arrow(12, 15.3, 8.25, 15.2)
arrow(12, 15.3, 13.25, 15.2)
arrow(12, 15.3, 18, 15.2)
arrow(12, 15.3, 22, 15.2)

# ═══════════════════════════════════════════════════════════
# Step 3: SOLVER POOL (33 solvers)
# ═══════════════════════════════════════════════════════════
ax.text(12, 13.4, '③ 33ソルバー並列投票', fontsize=11, fontweight='bold',
        ha='center', color='#1B5E20')

# --- S01-S09: Basic SAT ---
sat_y = 11.5
ax.text(2.5, 12.8, 'S01-S09: 基本SAT (構造)', fontsize=8, fontweight='bold', color='#2E7D32')
solvers_basic = [
    ('S01', 'DPLL\nSAT'), ('S02', 'WalkSAT\n確率的'), ('S03', 'Unit\nProp'),
    ('S04', 'Res\nProof'), ('S05', 'BCP\n伝播'), ('S06', 'CDCL\n学習'),
    ('S07', 'Table\nau法'), ('S08', 'Modal\n様相'), ('S09', 'Fuzzy\nファジー'),
]
for i, (name, desc) in enumerate(solvers_basic):
    x = 0.3 + i * 2.6
    box(x, sat_y, 2.3, 0.9, f'{name}\n{desc}', C_SAT, 6.5)

# --- S10-S18: Advanced SAT ---
ax.text(2.5, 11.0, 'S10-S18: 高度SAT (推論)', fontsize=8, fontweight='bold', color='#2E7D32')
sat_y2 = 9.7
solvers_adv = [
    ('S10', 'Prob\n確率論'), ('S11', 'Bayes\nベイズ'), ('S12', 'Geom\n幾何'),
    ('S13', 'Topo\n位相'), ('S14', 'Cat\n圏論'), ('S15', 'Info\n情報'),
    ('S16', 'Sympl\nシンプ'), ('S17', 'Alg\n代数'), ('S18', 'Diff\n微分'),
]
for i, (name, desc) in enumerate(solvers_adv):
    x = 0.3 + i * 2.6
    box(x, sat_y2, 2.3, 0.9, f'{name}\n{desc}', C_SAT, 6.5)

# --- S19-S27: Framework SAT ---
ax.text(2.5, 9.2, 'S19-S27: フレームワーク (構造)', fontsize=8, fontweight='bold', color='#2E7D32')
sat_y3 = 7.9
solvers_fw = [
    ('S19', 'Game\nゲーム'), ('S20', 'Net\nネット'), ('S21', 'Auto\nオートマタ'),
    ('S22', 'Lambda\nλ計算'), ('S23', 'Type\n型理論'), ('S24', 'Order\n順序'),
    ('S25', 'Graph\nグラフ'), ('S26', 'Code\n符号'), ('S27', 'Complex\n複雑'),
]
for i, (name, desc) in enumerate(solvers_fw):
    x = 0.3 + i * 2.6
    box(x, sat_y3, 2.3, 0.9, f'{name}\n{desc}', C_SAT, 6.5)

# --- S28: LLM Consensus ---
ax.text(12, 7.2, 'S28: LLM合意', fontsize=9, fontweight='bold', color='#01579B')
box(9, 6.2, 6, 0.8, 'S28: LLM Consensus\nGemini / Ollama (qwen3:8b) に問い合わせ\n多数決で真偽判定', C_LLM, 7, True)

# --- S29-S33: Semantic Truth ---
ax.text(12, 5.5, 'S29-S33: 意味的真理 (内容検証)', fontsize=9, fontweight='bold', color='#B71C1C')
sem_y = 4.3
box(0.3, sem_y, 4.5, 1, 'S29: 事実検証\n• 12個のknown-false\n  (地球平ら,ワクチン自閉症...)\n• 10個のknown-true\n  (光速,DNA二重らせん...)', C_SEMANTIC, 6.5, True)

box(5.2, sem_y, 4.2, 1, 'S30: 自己矛盾検出\n• 文内の論理矛盾\n• 主語-述語不一致\n• 量化子矛盾\n  (全て+例外=矛盾)', C_SEMANTIC, 6.5)

box(9.8, sem_y, 4.2, 1, 'S31: 信頼性シグナル\n• 曖昧語検出\n  (多くの,ある程度...)\n• 引用品質評価\n• ヘッジ語カウント', C_SEMANTIC, 6.5)

box(14.4, sem_y, 4.2, 1, 'S32: データ支持\n• 数値の具体性\n• 単位の存在\n• 統計指標\n  (p値,信頼区間...)', C_SEMANTIC, 6.5)

box(19, sem_y, 4.5, 1, 'S33: 事実整合\n• 既知事実との一致\n• 科学的コンセンサス\n• 時系列整合性\n• ドメイン知識照合', C_SEMANTIC, 6.5)

# ═══════════════════════════════════════════════════════════
# Step 4: VOTING & WEIGHTING
# ═══════════════════════════════════════════════════════════
ax.text(12, 3.6, '④ 重み付け投票', fontsize=10, fontweight='bold', ha='center', color='#F57F17')

box(2, 2.4, 6.5, 1, '構造スコア (50%)\n• S01-S27の通過率\n• 33ソルバー中の多数決\n• フレームワーク直交性で重み調整\n• ESS (有効サンプルサイズ) = 10.5', C_VOTE, 6.5)

box(9, 2.4, 6, 1, '意味スコア (25%)\n• S29-S33の通過率\n• known-false → 即FAIL\n  (スコア0.40にキャップ)\n• known-true → 高信頼\n• 多言語パターン照合', C_VOTE, 6.5)

box(15.5, 2.4, 6.5, 1, 'LLMスコア (25%)\n• S28の結果\n• Fallback: skip_s28=True\n• Ollama/Gemini合意\n• 到達不能時はheuristic fallback\n→ 最終スコア = 構造50% + 意味25% + LLM25%', C_VOTE, 6.5)

# ═══════════════════════════════════════════════════════════
# Step 5: OUTPUT
# ═══════════════════════════════════════════════════════════
box(4, 1.0, 16, 1, '⑤ 最終出力: PASS (>=0.7) / FAIL (<0.5) / UNVERIFIED (0.5-0.7)\n'
    '+ 5軸スコア (Rs/Rc/Rq/Rcl/Rt) + ソルバー通過率 + known-false理由 + 改善提案 + 目標生成\n'
    '例: "Earth is flat" → FAIL (0.347) known_false=True | "Water 100°C" → PASS (0.818)', 
    C_OUTPUT, 7, True)

# ═══════════════════════════════════════════════════════════
# Arrows from solvers to voting
# ═══════════════════════════════════════════════════════════
for i in range(9):
    x = 0.3 + i * 2.6 + 1.15
    arrow(x, sat_y, x, sat_y + 0.05)  # Visual connection
    
arrow(5.25, 6.2, 5.25, 3.4)  # Structural → vote
arrow(12, 6.2, 12, 3.4)      # LLM → vote
arrow(12, 4.3, 12, 3.4)      # Semantic → vote

# Voting to output
arrow(12, 2.4, 12, 2.0)

# ═══════════════════════════════════════════════════════════
# Legend
# ═══════════════════════════════════════════════════════════
legend_items = [
    (C_SAT, 'S01-S27: 構造SAT (27個)'),
    (C_LLM, 'S28: LLM合意 (1個)'),
    (C_SEMANTIC, 'S29-S33: 意味的真理 (5個)'),
    (C_ROUTER, 'ドメイン分類'),
    (C_MULTI, '多言語'),
    (C_VOTE, '重み付け投票'),
]
for i, (color, label) in enumerate(legend_items):
    x = 0.5 + i * 4.0
    rect = mpatches.FancyBboxPatch((x, 0.2), 0.5, 0.4, boxstyle="round,pad=0.05",
                                     facecolor=color, edgecolor='#37474F', linewidth=0.8)
    ax.add_patch(rect)
    ax.text(x + 0.65, 0.4, label, fontsize=7, va='center')

plt.tight_layout()
plt.savefig('/Users/nicolas/work/katala/ks_solver_flowchart.png', dpi=150, bbox_inches='tight')
print("✅ Solver flowchart saved")
