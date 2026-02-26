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
- **Source**: Polymarket ($21M Vol)
- **Market Odds**: Anthropic 97% / Google 2%
- **Shirokuma Prediction**: ✅ Yes (Anthropic)
- **Confidence**: 90%
- **Rationale**: Opus 4.6がベンチマーク首位を維持。ただし97%は高すぎ、Gemini 3 Proの実力は過小評価
- **Verification Date**: 2026-02-28
- **Status**: ⏳ Pending

### P-006: BTC All-Time High by March 31, 2026
- **Source**: Polymarket ($3M Vol)
- **Market Odds**: Yes 1%
- **Shirokuma Prediction**: ❌ No
- **Confidence**: 95%
- **Rationale**: 現在$68K付近、ATH圏から大幅下落。関税不確実性+Fed据え置きで上値重い。CryptoHayesの「マネープリンティング」は2026後半以降
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
- **Market Odds**: Yes 2% (2/26時点)
- **Shirokuma Prediction**: ❌ No
- **Confidence**: 92%
- **Rationale**: 短期的にはNo。出来高$424Mが世界の不安を可視化。台湾$111B武器売却と合わせ地政学リスク上昇中
- **Verification Date**: 2026-02-28
- **Status**: ⏳ Pending

### P-009: GPT-5.3 Released by March 8
- **Source**: Polymarket
- **Market Odds**: By 2/28: 27% / By 3/8: 74%
- **Shirokuma Prediction**: ✅ Yes (by 3/8)
- **Confidence**: 70%
- **Rationale**: OpenAIのリリースパターン的に3月初旬濃厚。Codex既にAPI提供中
- **Verification Date**: 2026-03-08
- **Status**: ⏳ Pending

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
- **Market Odds**: Yes 27%
- **Shirokuma Prediction**: ❌ No
- **Confidence**: 70%
- **Rationale**: Anthropic RSP v3.0の自律兵器禁止原則と衝突。部分的利用制限はあり得るが全面禁止はNo
- **Verification Date**: 2026-03-31
- **Status**: ⏳ Pending

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
- Resolved: 1
- Correct: 1
- Accuracy: 100% (n=1, insufficient sample)

### By Category
- Earnings: 1/1 (100%)
- Tech/AI: 0/0
- Crypto/Finance: 0/0
- Geopolitics: 0/0
- Politics: 0/0

### Calibration Analysis
(Predictions grouped by confidence level — to be updated as sample grows)
- 90-100% confidence: 0 resolved
- 70-89% confidence: 1 resolved, 1 correct
- 50-69% confidence: 0 resolved

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
