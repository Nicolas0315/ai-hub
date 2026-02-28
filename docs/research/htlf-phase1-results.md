# HTLF Phase 1 Results (Auto vs Manual)

Generated: 2026-02-28T22:46:55

## Correlation

- Pearson(manual R_struct, auto R_struct): **0.2181**
- Pearson(manual R_context, auto R_context): **-0.2010**

## Aggregate Means

- Manual mean R_struct: 0.2600
- Auto mean R_struct: 0.4105
- Manual mean R_context: 0.4750
- Auto mean R_context: 0.2229

## Per-case

| Case | Title | Manual R_struct | Auto R_struct | Manual R_context | Auto R_context | Profile | Total Loss |
|---|---|---:|---:|---:|---:|---|---:|
| 1 | LIGO重力波検出 | 0.45 | 1.00 | 0.55 | 0.50 | P07_struct_sum | 0.00 |
| 2 | ヒッグス粒子発見 | 0.30 | 1.00 | 0.40 | 0.50 | P07_struct_sum | 0.00 |
| 3 | ブラックホール初撮影（M87*） | 0.25 | 0.00 | 0.45 | 0.00 | P01_struct_context_sum | 1.00 |
| 4 | ペレルマンによるポアンカレ予想の証明 | 0.10 | 0.00 | 0.50 | 0.00 | P01_struct_context_sum | 1.00 |
| 5 | CRISPR-Cas9 遺伝子編集 | 0.35 | 1.00 | 0.35 | 0.50 | P07_struct_sum | 0.00 |
| 6 | 量子超越性（Google Sycamore） | 0.30 | 0.00 | 0.35 | 0.15 | P09_context_sum | 0.85 |
| 7 | ワイルズによるフェルマーの最終定理の証明 | 0.05 | 1.00 | 0.55 | 0.50 | P07_struct_sum | 0.00 |
| 8 | 超伝導体LK-99騒動 | 0.20 | 0.00 | 0.65 | 0.00 | P01_struct_context_sum | 1.00 |
| 9 | AlphaFold2によるタンパク質構造予測 | 0.35 | 0.11 | 0.50 | 0.08 | P07_struct_sum | 0.89 |
| 10 | 暗黒エネルギーの発見（加速膨張） | 0.25 | 0.00 | 0.45 | 0.00 | P01_struct_context_sum | 1.00 |

## Notes

- Parser in this run uses mock mode by default unless OPENAI_API_KEY is provided and --no-mock-parser is set.
- URL fetch may fail due paywalls; fallback uses dataset summaries.
