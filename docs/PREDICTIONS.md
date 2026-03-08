# Katala Predictions — しろくま予測台帳

> 予測は刻め。答え合わせは逃げるな。
> — nicolas_ogoshi

## Ledger Scope

- This ledger tracks the current prediction cycle: **P-004〜P-012**
- Resolution status is updated with reproducible criteria and sources
- Confidence calibration is reviewed as sample size grows

---

## Resolved Predictions

### P-004: NVIDIA FY2026 Q4 Earnings Beat
- **Source**: NVIDIA earnings release (FY2026 Q4)
- **Shirokuma Prediction**: ✅ Yes (consensus beat)
- **Confidence**: 85%
- **Verification Date**: 2026-02-26
- **Status**: ✅ Resolved — Correct
- **Actuals**:
  - Revenue: **$68.1B** (prediction baseline $65.56B → **+3.9% upside**)
  - EPS: **$1.62** (consensus $1.52〜$1.53 → upside)
- **Result Summary**: ✅ 的中

---

## Active Predictions

### P-005: Best AI Model End of February = Anthropic
- **Source**: Polymarket ($22.2M Vol)
- **Market Odds**: Anthropic 100% (resolved)
- **Shirokuma Prediction**: ✅ Yes (Anthropic)
- **Confidence**: 90%
- **Rationale**: Opus 4.6がベンチマーク首位を維持。ただし97%は高すぎ、Gemini 3 Proの実力は過小評価
- **Verification Date**: 2026-02-28
- **Status**: ✅ Resolved — Correct
- **Actuals**: Anthropic won per Chatbot Arena LLM Leaderboard Arena Score (style control off) checked 2/28 12:00 PM ET. Market resolved Anthropic 100%.
- **Result Summary**: ✅ 的中

### P-006: BTC All-Time High by March 31, 2026
- **Source**: Polymarket ($3M Vol)
- **Market Odds**: Yes 1%
- **Shirokuma Prediction**: ❌ No
- **Confidence**: 95%
- **Rationale**: ATH $126,210 (2025/10/6)。現在$67.5K付近で-46%。関税不確実性+Fed据え置きで上値重い
- **Verification Date**: 2026-03-31
- **Status**: ⏳ Pending

### P-007: Trump Fed Chair Nominee = Kevin Warsh
- **Source**: Polymarket ($528M Vol)
- **Market Odds**: Warsh 94% / Shelton 4%
- **Shirokuma Prediction**: ✅ Yes (Warsh)
- **Confidence**: 80%
- **Rationale**: ウォール街受けは良いがTrumpの「金利下げたい」意向と必ずしも一致せず。Sheltonはサプライズ候補
- **Verification Date**: TBD
- **Status**: ⏳ Pending

### P-008: US Strikes Iran in February 2026
- **Source**: Polymarket ($424M Vol — 最大級)
- **Market Odds**: Resolved Yes
- **Shirokuma Prediction**: ❌ No
- **Confidence**: 92%
- **Rationale**: 短期的にはNo。出来高$424Mが世界の不安を可視化。台湾$111B武器売却と合わせ地政学リスク上昇中
- **Verification Date**: 2026-02-28
- **Status**: ❌ Resolved — Wrong
- **Actuals**: 2/28に「Operation Epic Fury」として米軍がイランの軍事施設・テヘラン等を大規模攻撃。イスラエルと連携。イランは報復ミサイルで応戦。月末ギリギリの攻撃で市場はYes解決。
- **Result Summary**: ❌ 外れ（92%確信でNo予測→2/28当日に攻撃実行）
- **Post-mortem**: 2/27時点の「攻撃なし→No濃厚」判断が甘かった。軍事展開の規模（空母2隻展開）を過小評価。テールリスクの見積もりに課題

### P-009: GPT-5.3 Released by March 8
- **Source**: Polymarket
- **Market Odds**: By 2/28: 27% / By 3/8: 74%
- **Shirokuma Prediction**: ✅ Yes (by 3/8)
- **Confidence**: 70%
- **Rationale**: OpenAIのリリースパターン的に3月初旬濃厚。Codex既にAPI提供中
- **Verification Date**: 2026-03-08
- **Status**: ✅ Resolved — Correct
- **Actuals**: GPT-5.3 Codex は2026年2月にリリース済み。期限3/8より前に達成
- **Result Summary**: ✅ 的中（早期達成）

### P-010: Cerebras & Discord IPO before 2027
- **Source**: Polymarket ($4M Vol)
- **Market Odds**: Cerebras 90% / Discord 89%
- **Shirokuma Prediction**: ✅ Yes (both)
- **Confidence**: 85%
- **Rationale**: Cerebrasは半導体AI需要で確実視。Discord DAU/収益安定
- **Verification Date**: 2026-12-31
- **Status**: ⏳ Pending

### P-011: 2028 GOP Nominee = JD Vance
- **Source**: Polymarket ($330M Vol)
- **Market Odds**: Vance 42% / Rubio 13%
- **Shirokuma Prediction**: ✅ Yes (Vance)
- **Confidence**: 55%
- **Rationale**: 最有力だが42%は高い可能性。DeSantis再挑戦リスク
- **Verification Date**: 2028
- **Status**: ⏳ Pending (Long-term)

### P-012: Pete Hegseth Bans Claude by March 31
- **Source**: Polymarket ($268K Vol)
- **Market Odds**: Resolved Yes
- **Shirokuma Prediction**: ❌ No
- **Confidence**: 60% (70%→下方修正: 状況が急展開)
- **Rationale**: Anthropic RSP v3.0の自律兵器禁止原則と衝突。部分的利用制限はあり得るが全面禁止はNo
- **Verification Date**: 2026-03-31
- **Status**: ❌ Resolved — Wrong (early resolution 2/27)
- **Actuals**: 2/27にHegsethがAnthropicをサプライチェーンリスクに指定、軍事利用を全面禁止。TrumpもTruth Socialで連邦機関からのAnthropic排除を指示（6ヶ月フェーズアウト）。期限3/31より1ヶ月以上前に決着。
- **Result Summary**: ❌ 外れ（60%確信でNo予測→2/27に全面禁止）
- **Post-mortem**: 2/27ノートで急展開を認識しながらもNo維持。「全面禁止はない」という楽観バイアス。政治的意思決定のスピードを過小評価

---

## Verification Cron Design

- **Cron job name**: `katala-predictions-verifier`
- **Schedule**: `0 10 * * *` (Asia/Tokyo daily 10:00) + ad-hoc run on key resolution dates
- **Input**: `docs/PREDICTIONS.md` active entries with `Verification Date`
- **Checks**:
  1. Pull market resolution status / official sources per trigger
  2. Compare outcome vs Shirokuma Prediction
  3. Update `Status` to ✅/❌/🔄 and append verification evidence
- **Output**:
  - Update ledger in-place
  - Post daily summary to Discord (`#dev-katala`)
  - Emit metrics delta (resolved/correct/accuracy)
- **Guardrails**:
  - No status flip without source evidence URL
  - Keep unresolved items as ⏳ Pending
  - Log every mutation with timestamp for auditability

---

## Accuracy Metrics

### Overall
- Total Predictions: 9 (P-004〜P-012)
- Resolved: 5
- Correct: 3
- Wrong: 2
- Accuracy: **60%** (n=5)

### By Category
- Earnings: 1/1 (100%)
- Tech/AI: 2/2 (100%) — P-005, P-009
- Crypto/Finance: 0/0
- Geopolitics: 0/1 (0%) — P-008 ❌
- Politics: 0/1 (0%) — P-012 ❌

### Calibration Analysis
- 90-100% confidence: 2 resolved — P-005 ✅ (90%), P-008 ❌ (92%) → 50% accuracy ⚠️
- 70-89% confidence: 1 resolved, 1 correct — P-009 ✅ (70%)
- 60-69% confidence: 2 resolved — P-004 ✅ (85%→recal), P-012 ❌ (60%) → 50% accuracy
- 50-59% confidence: 0 resolved

### Calibration Notes (2026-03-01)
- ⚠️ 高確信帯（90%+）で外れが発生。地政学リスクのテールイベント見積もりに構造的弱点
- Tech/AI予測は好調（2/2）だが、政治・軍事系は0/2。ドメイン別精度の乖離が顕著
- 「No」予測の精度が課題: No予測3件中2件が外れ（P-008, P-012）

### Methodology
1. **Source**: Polymarket odds as baseline + independent analysis
2. **Scoring**: TrustScorer 4-axis (freshness, provenance, verification, accessibility)
3. **Verification**: Automated cron checks against resolution criteria
4. **Calibration Goal**: Stated confidence should match actual hit rate (e.g., 80% predictions should resolve correctly ~80% of the time)

### Katala Integration Notes
- Each prediction is scored using TrustScorer methodology
- ConsensusEngine: market odds vs Shirokuma analysis as 2-agent consensus
- Dissent tracking: when Shirokuma disagrees with market (e.g., P-005 confidence gap)
- EconomicTrustScorer: volume-weighted market signal quality
