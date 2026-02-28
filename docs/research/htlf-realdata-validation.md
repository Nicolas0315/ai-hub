# HTLF Real-data Validation

Generated: 2026-02-28T23:39:18

## Correlation (manual vs auto)
- Pearson R_struct: **0.3522**
- Pearson R_context: **-0.3824**
- Pearson R_qualia: **-0.0216**

## Per-case results

| Case | Title | Source | Target | Manual R_struct | Auto R_struct | Manual R_context | Auto R_context | Manual R_qualia | Auto R_qualia | Profile | Total Loss |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | LIGO重力波検出 | fallback | fallback | 0.45 | 1.00 | 0.55 | 0.13 | 0.25 | 0.57 | P07_struct_sum | 0.00 |
| 2 | ヒッグス粒子発見 | url | fallback | 0.30 | 1.00 | 0.40 | 0.00 | 0.20 | 0.50 | P07_struct_sum | 0.00 |
| 3 | ブラックホール初撮影（M87*） | url | url | 0.25 | 0.00 | 0.45 | 0.11 | 0.25 | 0.56 | P11_qualia_sum | 0.44 |
| 4 | ペレルマンによるポアンカレ予想の証明 | url | fallback | 0.10 | 0.00 | 0.50 | 0.00 | 0.15 | 0.50 | P11_qualia_sum | 0.50 |
| 5 | CRISPR-Cas9 遺伝子編集 | fallback | fallback | 0.35 | 1.00 | 0.35 | 0.24 | 0.20 | 0.62 | P07_struct_sum | 0.00 |
| 6 | 量子超越性（Google Sycamore） | url | url | 0.30 | 0.00 | 0.35 | 0.22 | 0.15 | 0.61 | P11_qualia_sum | 0.39 |
| 7 | ワイルズによるフェルマーの最終定理の証明 | fallback | fallback | 0.05 | 1.00 | 0.55 | 0.11 | 0.20 | 0.55 | P07_struct_sum | 0.00 |
| 8 | 超伝導体LK-99騒動 | url | fallback | 0.20 | 0.00 | 0.65 | 0.01 | 0.30 | 0.51 | P11_qualia_sum | 0.49 |
| 9 | AlphaFold2によるタンパク質構造予測 | url | url | 0.35 | 1.00 | 0.50 | 0.26 | 0.25 | 0.63 | P07_struct_sum | 0.00 |
| 10 | 暗黒エネルギーの発見（加速膨張） | url | fallback | 0.25 | 0.00 | 0.45 | 0.00 | 0.20 | 0.50 | P11_qualia_sum | 0.50 |

## Runtime benchmark
- Rust total: 9.821s
- Python total: 9.820s
- Speedup: 1.00x
