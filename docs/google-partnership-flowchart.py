"""
Katala × Google Partnership — Architecture Flowchart
Youtaさん向け: 3つの道のデータフロー + 統合アーキテクチャ
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, axes = plt.subplots(3, 1, figsize=(18, 28))
fig.suptitle('Katala × Google Partnership — 3つの道のフローチャート',
             fontsize=18, fontweight='bold', y=0.98,
             fontfamily='Hiragino Sans')

# Color scheme
C_GOOGLE = '#4285F4'
C_KATALA = '#E85D26'
C_OUTPUT = '#34A853'
C_EXTERNAL = '#9E9E9E'
C_USER = '#FBBC05'
C_BG = '#FAFAFA'

def draw_box(ax, x, y, w, h, text, color, fontsize=10, textcolor='white'):
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                          boxstyle="round,pad=0.1",
                          facecolor=color, edgecolor='#333', linewidth=1.5,
                          alpha=0.9)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            fontweight='bold', color=textcolor, fontfamily='Hiragino Sans',
            wrap=True)

def draw_arrow(ax, x1, y1, x2, y2, label='', color='#333'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=2))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my + 0.3, label, ha='center', va='bottom', fontsize=8,
                color=color, fontfamily='Hiragino Sans', fontstyle='italic')

# ═══════════════════════════════════════════════════
# 道① KS Verification API
# ═══════════════════════════════════════════════════
ax1 = axes[0]
ax1.set_xlim(-1, 17)
ax1.set_ylim(-1, 8)
ax1.set_aspect('equal')
ax1.axis('off')
ax1.set_title('道① KS Verification API（第三者検証サービス）\n再現性: ★★★★☆ | 期間: 1〜2ヶ月',
              fontsize=14, fontweight='bold', fontfamily='Hiragino Sans', pad=15)

# Enterprise User
draw_box(ax1, 1.5, 6, 2.5, 1.2, 'Enterprise\nUser', C_USER, textcolor='#333')
# Gemini API
draw_box(ax1, 5.5, 6, 2.5, 1.2, 'Gemini API\n(Google)', C_GOOGLE)
# KS Verification API
draw_box(ax1, 10, 6, 3, 1.2, 'KS Verification\nAPI (FastAPI)', C_KATALA)
# Verified Response
draw_box(ax1, 14.5, 6, 2.5, 1.2, 'Verified\nResponse', C_OUTPUT)

# Solver Diversity Layer
draw_box(ax1, 7, 3, 2.5, 1.2, 'Gemini\nSolver', C_GOOGLE)
draw_box(ax1, 10, 3, 2.5, 1.2, 'Grok API\nSolver', '#1DA1F2')
draw_box(ax1, 13, 3, 2.5, 1.2, 'Ollama Local\nSolver', C_EXTERNAL, textcolor='white')

# Ensemble
draw_box(ax1, 10, 1, 3.5, 1.2, 'Solver Diversity\nEnsemble (多数決)', C_KATALA)

# Arrows
draw_arrow(ax1, 2.75, 6, 4.25, 6, 'Query')
draw_arrow(ax1, 6.75, 6, 8.5, 6, 'LLM Response')
draw_arrow(ax1, 11.5, 6, 13.25, 6, 'KS Score')

draw_arrow(ax1, 10, 5.4, 7, 3.6, '')
draw_arrow(ax1, 10, 5.4, 10, 3.6, '')
draw_arrow(ax1, 10, 5.4, 13, 3.6, '')

draw_arrow(ax1, 7, 2.4, 10, 1.6, '')
draw_arrow(ax1, 10, 2.4, 10, 1.6, '')
draw_arrow(ax1, 13, 2.4, 10, 1.6, '')

draw_arrow(ax1, 10, 0.4, 10, -0.2, '')
ax1.text(10, -0.5, 'フィルターバイアス検出\n全員OK→高信頼 / 1社拒否→バイアス / 全社拒否→危険',
         ha='center', va='top', fontsize=9, fontfamily='Hiragino Sans',
         color=C_KATALA, style='italic')

# ═══════════════════════════════════════════════════
# 道② Data Quality Partner
# ═══════════════════════════════════════════════════
ax2 = axes[1]
ax2.set_xlim(-1, 17)
ax2.set_ylim(-1, 8)
ax2.set_aspect('equal')
ax2.axis('off')
ax2.set_title('道② Data Quality Partner（データクリーンアップ）★推奨★\n再現性: ★★★★★ | 期間: 今週〜2週間',
              fontsize=14, fontweight='bold', fontfamily='Hiragino Sans', pad=15)

# Pipeline
draw_box(ax2, 1.5, 6, 2.5, 1.2, 'Google Search\nAPI', C_GOOGLE)
draw_box(ax2, 5, 6, 2.5, 1.2, 'Top 10\n検索結果', C_EXTERNAL, textcolor='white')
draw_box(ax2, 9, 6, 3, 1.2, 'KS Quality\nPipeline', C_KATALA)
draw_box(ax2, 13, 6, 2.5, 1.2, 'Quality\nReport', C_OUTPUT)

# 3-layer verification
draw_box(ax2, 5.5, 3, 2.5, 1.2, '①ソース評価\n(domain trust)', C_KATALA)
draw_box(ax2, 9, 3, 2.8, 1.2, '②内容検証\n(KS fact-check)', C_KATALA)
draw_box(ax2, 12.5, 3, 2.8, 1.2, '③クロスリファレンス\n(cross-source)', C_KATALA)

# Output
draw_box(ax2, 9, 0.5, 5, 1.4, 'Search Quality Score Card\n各結果: 信頼度/根拠/フラグ', C_OUTPUT)

# Arrows
draw_arrow(ax2, 2.75, 6, 3.75, 6, 'crawl')
draw_arrow(ax2, 6.25, 6, 7.5, 6, 'raw HTML')
draw_arrow(ax2, 10.5, 6, 11.75, 6, 'scored')

draw_arrow(ax2, 9, 5.4, 5.5, 3.6, '')
draw_arrow(ax2, 9, 5.4, 9, 3.6, '')
draw_arrow(ax2, 9, 5.4, 12.5, 3.6, '')

draw_arrow(ax2, 5.5, 2.4, 9, 1.2, '')
draw_arrow(ax2, 9, 2.4, 9, 1.2, '')
draw_arrow(ax2, 12.5, 2.4, 9, 1.2, '')

# ═══════════════════════════════════════════════════
# 統合: 3つの道の時系列
# ═══════════════════════════════════════════════════
ax3 = axes[2]
ax3.set_xlim(-1, 17)
ax3.set_ylim(-1, 8)
ax3.set_aspect('equal')
ax3.axis('off')
ax3.set_title('統合ロードマップ（時系列）',
              fontsize=14, fontweight='bold', fontfamily='Hiragino Sans', pad=15)

# Timeline
ax3.plot([1, 15], [4, 4], color='#333', linewidth=2, zorder=1)
for x in [2, 6, 10, 14]:
    ax3.plot(x, 4, 'o', color='#333', markersize=8, zorder=2)

# Time labels
ax3.text(2, 3.3, '今週', ha='center', fontsize=10, fontfamily='Hiragino Sans', fontweight='bold')
ax3.text(6, 3.3, '2週間後', ha='center', fontsize=10, fontfamily='Hiragino Sans', fontweight='bold')
ax3.text(10, 3.3, '1〜2ヶ月', ha='center', fontsize=10, fontfamily='Hiragino Sans', fontweight='bold')
ax3.text(14, 3.3, '3〜6ヶ月', ha='center', fontsize=10, fontfamily='Hiragino Sans', fontweight='bold')

# Step boxes
draw_box(ax3, 2, 6, 3, 1.2, 'Step 1\n道② PoC開発', C_KATALA)
draw_box(ax3, 6, 6, 3, 1.2, 'Step 1.5\nGitHub公開\nデモ動画', C_OUTPUT)
draw_box(ax3, 10, 6, 3, 1.2, 'Step 2\n道① API化\nSolver Diversity', C_KATALA)
draw_box(ax3, 14, 6, 3, 1.2, 'Step 3\n道③ 論文化\nGoogle応募', C_GOOGLE)

# Sub-items
ax3.text(2, 1.5, 'web_search + KS40c\n検索結果検証デモ\nベンチマーク100件',
         ha='center', va='center', fontsize=9, fontfamily='Hiragino Sans',
         bbox=dict(boxstyle='round', facecolor='#FFF3E0', edgecolor=C_KATALA))

ax3.text(6, 1.5, 'katala-verify-demo\nリポ公開\n投資家/パートナー向け',
         ha='center', va='center', fontsize=9, fontfamily='Hiragino Sans',
         bbox=dict(boxstyle='round', facecolor='#E8F5E9', edgecolor=C_OUTPUT))

ax3.text(10, 1.5, 'FastAPI + Docker\nGrok + Ollama統合\nベンチマーク1,000件',
         ha='center', va='center', fontsize=9, fontfamily='Hiragino Sans',
         bbox=dict(boxstyle='round', facecolor='#FFF3E0', edgecolor=C_KATALA))

ax3.text(14, 1.5, 'arXiv投稿\nGoogle AI Awards\nfor Startups応募',
         ha='center', va='center', fontsize=9, fontfamily='Hiragino Sans',
         bbox=dict(boxstyle='round', facecolor='#E3F2FD', edgecolor=C_GOOGLE))

# Arrows from timeline to boxes
for x in [2, 6, 10, 14]:
    draw_arrow(ax3, x, 4.4, x, 5.4, '', '#666')
    draw_arrow(ax3, x, 2.8, x, 2.2, '', '#666')

plt.tight_layout(rect=[0, 0, 1, 0.96])

outpath = '/Users/nicolas/work/katala/docs/google-partnership-flowchart.png'
plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor='white')
print(f"Saved: {outpath}")
plt.close()
