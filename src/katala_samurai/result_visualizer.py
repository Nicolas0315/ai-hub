"""
Result Visualizer — Auto-generate PNG charts from verification results.

When no explicit format is requested, outputs visual PNG instead of text tables.
Dark theme, clean layout, designed for Discord embed readability.

Design: Youta Hilono, 2026-02-28
"""

import os
import tempfile
from typing import Dict, Any, Optional, List

def _ensure_matplotlib():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'DejaVu Sans'
    return plt


def render_verdict(result: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """Render a single verification result as a visual PNG.
    
    Returns path to generated PNG.
    """
    plt = _ensure_matplotlib()
    
    verdict = result.get("verdict", "UNKNOWN")
    confidence = result.get("confidence", 0)
    version = result.get("version", "KS")
    claim = result.get("claim", result.get("text", ""))[:80]
    
    # Layer results
    l6 = result.get("L6_statistical", {})
    l7 = result.get("L7_adversarial", {})
    deep = result.get("deep_causal", {})
    pipeline = result.get("pipeline", {})
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), facecolor='#0d1117',
                              gridspec_kw={'width_ratios': [1, 2, 1]})
    
    # ── Left: Confidence gauge ──
    ax = axes[0]
    ax.set_facecolor('#0d1117')
    
    colors_map = {
        'VERIFIED': '#3fb950', 'EXPLORING': '#f0883e',
        'PARTIALLY_VERIFIED': '#d29922', 'UNVERIFIED': '#f85149', 'ERROR': '#da3633',
    }
    color = colors_map.get(verdict, '#8b949e')
    
    # Circular gauge
    theta = [0, confidence * 360]
    ax.pie([confidence, 1-confidence], colors=[color, '#21262d'], startangle=90,
           counterclock=False, wedgeprops={'width': 0.3, 'edgecolor': '#0d1117'})
    ax.text(0, 0, f'{confidence:.0%}', ha='center', va='center', color='white',
            fontsize=24, weight='bold')
    ax.text(0, -0.35, verdict, ha='center', va='center', color=color, fontsize=10, weight='bold')
    ax.set_title('Confidence', color='#8b949e', fontsize=9, pad=10)
    
    # ── Center: Layer breakdown ──
    ax2 = axes[1]
    ax2.set_facecolor('#0d1117')
    
    layers = []
    scores = []
    colors_bar = []
    
    # Core layers
    layers.append('L1-L5 Core')
    core_conf = result.get("confidence", 0.5) - l6.get("modifier", 0) - l7.get("modifier", 0)
    core_conf -= deep.get("adjustment", deep.get("confidence_adjustment", 0))
    scores.append(max(0, min(1, core_conf)))
    colors_bar.append('#58a6ff')
    
    if deep.get("status") == "enhanced":
        layers.append('Deep Causal')
        adj = deep.get("adjustment", deep.get("confidence_adjustment", 0))
        scores.append(max(0, min(1, 0.5 + adj)))
        colors_bar.append('#f0883e')
    
    layers.append('L6 Statistical')
    scores.append(max(0, min(1, 0.5 + l6.get("modifier", 0))))
    colors_bar.append('#3fb950' if l6.get("modifier", 0) >= 0 else '#f85149')
    
    layers.append('L7 Adversarial')
    scores.append(max(0, min(1, 0.5 + l7.get("modifier", 0))))
    colors_bar.append('#d2a8ff' if l7.get("modifier", 0) >= 0 else '#f85149')
    
    y_pos = range(len(layers))
    bars = ax2.barh(y_pos, scores, color=colors_bar, alpha=0.85, height=0.5, edgecolor='#333')
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(layers, color='white', fontsize=9)
    ax2.set_xlim(0, 1)
    ax2.set_xlabel('Score', color='#8b949e', fontsize=8)
    ax2.tick_params(colors='#8b949e')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['bottom'].set_color('#333')
    ax2.spines['left'].set_color('#333')
    ax2.grid(axis='x', color='#21262d', linewidth=0.5)
    ax2.set_title('Layer Breakdown', color='#8b949e', fontsize=9, pad=10)
    
    for bar, score in zip(bars, scores):
        ax2.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f'{score:.2f}', va='center', color='white', fontsize=8)
    
    # ── Right: Info panel ──
    ax3 = axes[2]
    ax3.set_facecolor('#0d1117')
    ax3.axis('off')
    
    info_lines = [
        (version, '#58a6ff', 12, 'bold'),
        ('', '#0d1117', 6, 'normal'),
        (f'L6: {l6.get("verdict", "N/A")}', '#3fb950' if 'SOUND' in str(l6.get("verdict","")) else '#8b949e', 9, 'normal'),
        (f'L7: {l7.get("verdict", "N/A")}', '#d2a8ff' if 'PASS' in str(l7.get("verdict","")) else '#8b949e', 9, 'normal'),
        (f'Causal: {deep.get("status", "N/A")}', '#f0883e', 9, 'normal'),
        ('', '#0d1117', 6, 'normal'),
        (f'Time: {pipeline.get("total", "?")}s', '#8b949e', 9, 'normal'),
    ]
    
    for i, (text, color, size, weight) in enumerate(info_lines):
        ax3.text(0.5, 0.9 - i*0.12, text, ha='center', va='center',
                color=color, fontsize=size, weight=weight, transform=ax3.transAxes)
    
    # Title
    fig.suptitle(f'"{claim}"' if claim else 'Verification Result',
                 color='white', fontsize=10, y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), 'ks_result.png')
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    plt.close()
    
    return output_path


def render_comparison(results: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
    """Render multiple verification results as a comparison chart."""
    plt = _ensure_matplotlib()
    
    n = len(results)
    if n == 0:
        return ""
    
    fig, ax = plt.subplots(figsize=(max(8, n*2), 5), facecolor='#0d1117')
    ax.set_facecolor('#0d1117')
    
    claims = [r.get("claim", r.get("text", f"Claim {i}"))[:40] for i, r in enumerate(results)]
    confs = [r.get("confidence", 0) for r in results]
    verdicts = [r.get("verdict", "?") for r in results]
    
    colors_map = {
        'VERIFIED': '#3fb950', 'EXPLORING': '#f0883e',
        'PARTIALLY_VERIFIED': '#d29922', 'UNVERIFIED': '#f85149',
    }
    colors = [colors_map.get(v, '#8b949e') for v in verdicts]
    
    bars = ax.bar(range(n), confs, color=colors, alpha=0.85, edgecolor='#333')
    
    for bar, conf, verdict in zip(bars, confs, verdicts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{conf:.0%}\n{verdict}', ha='center', color='white', fontsize=8)
    
    ax.set_xticks(range(n))
    ax.set_xticklabels(claims, color='white', fontsize=8, rotation=30, ha='right')
    ax.set_ylim(0, 1.15)
    ax.set_ylabel('Confidence', color='#8b949e')
    ax.tick_params(colors='#8b949e')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#333')
    ax.spines['left'].set_color('#333')
    ax.grid(axis='y', color='#21262d', linewidth=0.5)
    
    fig.suptitle('Verification Comparison', color='white', fontsize=12, weight='bold')
    plt.tight_layout()
    
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), 'ks_comparison.png')
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    plt.close()
    return output_path
