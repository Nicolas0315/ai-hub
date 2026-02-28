# HTLF Phase 3: R_qualia 行動主義的計測プロトコル

> 目的: `R_qualia` を「主観の言語化」ではなく、観測可能な行動・生理反応に還元して推定する。

## 0. 要約

Phase 2 の `R_qualia` は LLM 代理評定ベースで相関が低い（~0.01）。
本プロトコルでは、**行動主義的測定**（選択行動・反応時間・生理反応）を導入し、

- 元コンテンツ提示時の反応ベクトル `B_source`
- 翻訳後コンテンツ提示時の反応ベクトル `B_target`

の差分で qualia 損失を定義する。

---

## 1. 理論的基盤（行動主義）

### 1.1 Russell の circumplex model

感情を 2 次元（価: valence / 覚醒: arousal）で配置する古典モデル。  
HTLF における質感差を「感情空間上の変位」として扱える。

- 参考: Russell, J. A. (1980). *A circumplex model of affect.* Journal of Personality and Social Psychology.

### 1.2 生理指標（行動の一部として扱う）

自己報告を補助する客観信号:

- GSR / EDA（皮膚電気活動）
- 心拍変動（HRV; RMSSD, LF/HF）
- 心拍（BPM）
- 呼吸数
- 任意: pupil dilation, facial EMG

音楽心理実験では chills/frisson と自律神経反応の関連が報告される。

- 参考: Rickard (2004), Blood & Zatorre (2001), Salimpoor et al. (2011)

### 1.3 Forced Choice Paradigm

「どちらが近いか」「どちらが強いか」など二択/多肢選択課題は、
言語報告より再現性が高く、反応時間も情報を持つ。

- 例: A/B が元刺激に近い方を選ぶ
- 例: valence high/low, arousal high/low を選択

---

## 2. 実験プロトコル設計

## 2.1 被験者内比較（within-subject）

1. 元コンテンツ提示（音楽/視覚芸術）
2. 行動反応の記録（選択 + RT + 生理）
3. 翻訳先コンテンツ提示（自然言語説明など）
4. 同一課題で再測定

### 2.2 観測ベクトル定義

各刺激 `x` に対して:

```text
B(x) = [
  choice_distribution,
  reaction_time_stats,
  valence_arousal_rating,
  GSR_features,
  HRV_features,
  optional_features...
]
```

### 2.3 qualia 損失

```text
ΔB = D(B_source, B_target)
R_qualia = exp(-λ · ΔB)
L_qualia = 1 - R_qualia
```

- `D` は標準化後の重み付き距離（Mahalanobis / cosine / Wasserstein）
- `λ` はキャリブレーション係数

### 2.4 実験デザイン上の注意

- 刺激順序カウンターバランス
- carry-over を避けるための washout interval
- 疲労・順序効果を mixed-effects model で補正
- 前提知識差（音楽訓練年数など）を共変量化

---

## 3. オンライン代替プロトコル（被験者なし近似）

実被験者実験が困難なケース向け近似。

### 3.1 LLM アンサンブル × 心理データベース

1. 既存心理実験データ（音楽感情、審美評価）から
   `刺激特徴 -> 反応分布` のベースモデルを構築
2. 複数 LLM を「仮想被験者」として条件付き forced-choice を実施
3. 反応分布を実データ統計に正則化して推定バイアスを抑制

### 3.2 文脈条件付き R_qualia

```text
R_qualia = f(behavioral_delta | R_context)
```

`R_context` が低いほど、qualia 推定の信頼区間を広げる。

実装例:

```text
R_qualia_adj = R_qualia_raw * (0.5 + 0.5 * R_context)
```

---

## 4. R_context 依存構造

質感反応は文脈依存度が高い。特に音楽・創作→自然言語翻訳では、
背景知識共有の欠落が qualia 低下を誘発する。

### 4.1 因果図（簡略）

```text
Source stimulus
   ├─> Structural cues ------------┐
   ├─> Context comprehension ----┐  │
   └─> Direct affective channel -┴-> Behavioral response (B)

Translation
   ├─> Context loss -----------> reduces affective reconstruction
   └─> Structural preservation -> partly rescues affect
```

### 4.2 モデル化

- 主モデル: `B ~ struct + context + interaction`
- 補助: `qualia_delta ~ context_delta + struct_delta + subject_random_effect`

---

## 5. 5レイヤー×5レイヤー適用可能性マトリクス

凡例:

- **High**: 直接適用しやすい
- **Mid**: 条件付きで適用
- **Low**: 直接適用困難（代理設計が必要）

### 5.1 マトリクス

- 数学→数学: Low（qualia 成分ほぼなし）
- 数学→形式言語: Low
- 数学→自然言語: Mid（驚き/納得の情動は測定可能）
- 数学→音楽: Low
- 数学→創作: Low

- 形式言語→数学: Low
- 形式言語→形式言語: Low
- 形式言語→自然言語: Mid
- 形式言語→音楽: Low
- 形式言語→創作: Low

- 自然言語→数学: Mid
- 自然言語→形式言語: Mid
- 自然言語→自然言語: Mid-High
- 自然言語→音楽: Mid
- 自然言語→創作: Mid

- 音楽→数学: Low
- 音楽→形式言語: Low
- 音楽→自然言語: High（主対象）
- 音楽→音楽: High
- 音楽→創作: High

- 創作→数学: Low
- 創作→形式言語: Low
- 創作→自然言語: High（主対象）
- 創作→音楽: High
- 創作→創作: High

### 5.2 実装優先度

1. 音楽→自然言語
2. 創作→自然言語
3. 音楽↔創作
4. 自然言語↔自然言語（比較用ベースライン）

---

## 6. HTLF 実装への接続（Phase 3）

- `R_qualia` を「LLM主観評定」から「行動反応差分」へ移行
- 被験者データがない場合は online approximation を使用
- 最終スコアは `R_context` 条件付きで補正

```text
R_qualia_final = g(ΔB, R_context)
```

---

## 7. 参考文献（抜粋）

- Russell, J. A. (1980). A circumplex model of affect.
- Juslin, P. N., & Västfjäll, D. (2008). Emotional responses to music.
- Blood, A. J., & Zatorre, R. J. (2001). Intensely pleasurable responses to music.
- Salimpoor, V. N., et al. (2011). Dopamine release during anticipation/experience.
- Zentner, M., Grandjean, D., & Scherer, K. R. (2008). GEMS.
- Schindler, I., et al. (2017). Measuring aesthetic emotions review.

（詳細は `docs/research/htlf-literature-survey.md` を参照）
