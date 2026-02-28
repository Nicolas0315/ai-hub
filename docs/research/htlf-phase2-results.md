# HTLF Phase 2 Results (Auto vs Manual)

Generated: 2026-02-28T23:00:14

## Correlation

- Pearson(manual R_struct, auto R_struct): **0.3522**
- Pearson(manual R_context, auto R_context): **-0.3474**
- Pearson(manual R_qualia, auto R_qualia): **0.0142**

## Phase Comparison (1 -> 1.5 -> 2)

| Axis | Phase 1 | Phase 1.5 | Phase 2 | Δ(1.5→2) |
|---|---:|---:|---:|---:|
| R_struct corr | 0.2181 | 0.3522 | 0.3522 | -0.0000 |
| R_context corr | -0.2010 | -0.2245 | -0.3474 | -0.1229 |
| R_qualia corr | n/a | n/a | 0.0142 | n/a |

## Aggregate Means

- Manual mean R_struct: 0.2600
- Auto mean R_struct: 0.5000
- Manual mean R_context: 0.4750
- Auto mean R_context: 0.0937
- Manual mean R_qualia: 0.2150
- Auto mean R_qualia: 0.2059

## Per-case

| Case | Title | Manual R_struct | Auto R_struct | Manual R_context | Auto R_context | Manual R_qualia | Auto R_qualia | Profile | Total Loss |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | LIGO重力波検出 | 0.45 | 1.00 | 0.55 | 0.13 | 0.25 | 0.29 | P07_struct_sum | 0.00 |
| 2 | ヒッグス粒子発見 | 0.30 | 1.00 | 0.40 | 0.00 | 0.20 | 0.25 | P07_struct_sum | 0.00 |
| 3 | ブラックホール初撮影（M87*） | 0.25 | 0.00 | 0.45 | 0.09 | 0.25 | 0.18 | P11_qualia_sum | 0.82 |
| 4 | ペレルマンによるポアンカレ予想の証明 | 0.10 | 0.00 | 0.50 | 0.00 | 0.15 | 0.10 | P11_qualia_sum | 0.90 |
| 5 | CRISPR-Cas9 遺伝子編集 | 0.35 | 1.00 | 0.35 | 0.23 | 0.20 | 0.32 | P07_struct_sum | 0.00 |
| 6 | 量子超越性（Google Sycamore） | 0.30 | 0.00 | 0.35 | 0.16 | 0.15 | 0.12 | P09_context_sum | 0.84 |
| 7 | ワイルズによるフェルマーの最終定理の証明 | 0.05 | 1.00 | 0.55 | 0.10 | 0.20 | 0.28 | P07_struct_sum | 0.00 |
| 8 | 超伝導体LK-99騒動 | 0.20 | 0.00 | 0.65 | 0.01 | 0.30 | 0.10 | P11_qualia_sum | 0.90 |
| 9 | AlphaFold2によるタンパク質構造予測 | 0.35 | 1.00 | 0.50 | 0.22 | 0.25 | 0.17 | P07_struct_sum | 0.00 |
| 10 | 暗黒エネルギーの発見（加速膨張） | 0.25 | 0.00 | 0.45 | 0.00 | 0.20 | 0.25 | P11_qualia_sum | 0.75 |

## 12-Pattern Profile Classification Check

- Case 1 [P07_struct_sum] — LIGO重力波検出: 構造優位分類。R_struct=1.00 が相対的に高く、技術主張の骨格保持が優勢。
- Case 2 [P07_struct_sum] — ヒッグス粒子発見: 構造優位分類。R_struct=1.00 が相対的に高く、技術主張の骨格保持が優勢。
- Case 3 [P11_qualia_sum] — ブラックホール初撮影（M87*）: qualia単軸分類。R_qualia=0.18 が相対的優位。
- Case 4 [P11_qualia_sum] — ペレルマンによるポアンカレ予想の証明: qualia単軸分類。R_qualia=0.10 が相対的優位。
- Case 5 [P07_struct_sum] — CRISPR-Cas9 遺伝子編集: 構造優位分類。R_struct=1.00 が相対的に高く、技術主張の骨格保持が優勢。
- Case 6 [P09_context_sum] — 量子超越性（Google Sycamore）: 文脈優位分類。R_context=0.16 が中心で、背景説明の保持が主。
- Case 7 [P07_struct_sum] — ワイルズによるフェルマーの最終定理の証明: 構造優位分類。R_struct=1.00 が相対的に高く、技術主張の骨格保持が優勢。
- Case 8 [P11_qualia_sum] — 超伝導体LK-99騒動: qualia単軸分類。R_qualia=0.10 が相対的優位。
- Case 9 [P07_struct_sum] — AlphaFold2によるタンパク質構造予測: 構造優位分類。R_struct=1.00 が相対的に高く、技術主張の骨格保持が優勢。
- Case 10 [P11_qualia_sum] — 暗黒エネルギーの発見（加速膨張）: qualia単軸分類。R_qualia=0.25 が相対的優位。

## Notes

- R_context is now implemented as LLM-as-reader protocol: source prerequisite extraction -> target-only definition reconstruction -> embedding similarity weighted average.
- Backend fallback chain: OpenAI -> Gemini (GOOGLE_API_KEY/GEMINI_API_KEY) -> heuristic scorer.
- R_qualia is a proxy metric from 3 LLM ratings (median/5.0), with heuristic fallback when API keys are unavailable.
- Parser in this run uses mock mode by default unless --no-mock-parser is set and API key exists.
