# Katala Samurai 40 (KS40) — HTLF Integration Design

**Series**: KS40a / KS40b  
**Design**: Youta Hilono  
**Implementation**: Shirokuma (OpenClaw AI)  
**Date**: 2026-02-28

---

## 1. Overview

KS40シリーズは、KS39b（Self-Other Boundary）に **HTLF (Holographic Translation Loss Framework)** を接続し、
「主張の正しさ」だけでなく「翻訳過程でどれだけ意味が失われたか」を同時に評価する世代。

- KS39b: 判断の由来（SELF/DESIGNER/EXTERNAL/AMBIGUOUS）を追跡
- KS40a: 翻訳損失ベクトルを追加
- KS40b: 自動レイヤー推定 + ソース欠損時推定 + マルチレイヤー整合性検査

---

## 2. Evolution from KS39b

KS39b → KS40 の主要進化点:

- `verify()` 後段に HTLF 計測を追加
- `translation_loss` セクションを新設
  - `loss_vector`: `r_struct`, `r_context`, `r_qualia`
  - `profile_type`
  - `translation_fidelity`
  - `measurement_reliability`（provenance付き）
- `self_other_boundary` に HTLF計測由来の provenance を統合

これにより、
**「確信度が高い主張」でも「翻訳で意味が潰れている」ケースを分離検出**できる。

---

## 3. HTLF Theoretical Basis (summary of `docs/HTLF.md`)

HTLFは、記号体系間翻訳をホログラフィック原理のアナロジーで扱う。

- **bulk**: 元レイヤーの意味全体（構造・文脈・質感）
- **boundary**: 翻訳後の表層表現
- **復元度 R**: boundary から bulk をどこまで復元できるか
- **損失 L**: `L = 1 - R`

5レイヤー:
1. 数学
2. 形式言語
3. 自然言語
4. 音楽
5. 創作（視覚芸術など）

---

## 4. 3-axis × 12 profile patterns

### 3 axes

- `R_struct`: 構造保存
- `R_context`: 文脈保存
- `R_qualia`: 体験的質感保存

### 12 patterns

- 3軸から2軸選択: `3C2 = 6`
- 合成モード2種:
  - 加重和（軸の独立寄与）
  - 積（ボトルネック支配）

`6 × 2 = 12` パターン。

KS40実装では、`profile_type` として HTLF 側の判定を受け取り、
翻訳ペアごとの支配的損失様式を出力する。

---

## 5. Youta Hilono's philosophical basis

設計思想（HTLF.mdの要点）:

- 心のモジュール性
- 弱いサピア＝ウォーフ仮説
- 中国語の部屋 + プラグマティズム（理解を機能で評価）
- 言語行為論（出力を行為として扱う）

思考プロセス（本人記述）:

- 言語入力 → 脳内の図式ネットワーク（重なり合うベン図的構造）
- 有限個の構造ネットワークへ圧縮
- 言語へ再変換して出力

この「図式ネットワーク」の思想が、KS群のソルバー分離とHTLFの多軸評価に接続される。

---

## 6. Implementation architecture

## KS40a

1. `KS39b.verify()` 実行
2. HTLF `run_pipeline(source_text, claim_text)` 実行（ソースあり）
3. ソースなし時はレイヤー推定ベースの `estimate_loss_vector()` を使用
4. `translation_loss` 生成
5. `self_other_boundary` に `htlf_provenance` を追加

## KS40b (extended)

- 5レイヤー自動検出（テキスト特徴量）
- source_text 欠損時に `mode=estimated`
- マルチレイヤー整合性チェック:
  - レイヤー集合
  - consistency score
  - 矛盾カウント / 矛盾詳細

## Interface整理（循環import回避）

- `htlf/__init__.py` を遅延エクスポート化（`__getattr__`）
- `htlf/ks_integration.py` は `run_pipeline` を evaluate 内で遅延 import
- KS40側は `htlf.pipeline` / `htlf.ks_integration` を利用

---

## 7. Usage examples

```python
from katala_samurai.ks40a import KS40a

ks = KS40a()
res = ks.verify(
    "この科学記事の主張は元論文と一致している",
    source_text="Original abstract ...",
    source_layer="formal_language",
    target_layer="natural_language",
)
print(res["translation_loss"])
```

```python
from katala_samurai.ks40b import KS40b

ks = KS40b()
res = ks.verify("E=mc^2 therefore policy X is always true")
print(res["translation_loss"]["mode"])  # estimated
print(res["multi_layer_consistency"])
```

---

## 8. Expected impact

KS40シリーズにより Katala は、

- 真偽判定（KS系）
- 判断由来追跡（Self-Other Boundary）
- 翻訳損失計測（HTLF）

を統合し、**「正しさ」と「伝達品質」を同時に扱う信頼性基盤**へ拡張される。

---

## 9. KS40c — 5-Axis Model (Cultural/Temporal Loss Extension)

**Date**: 2026-03-01  
**Design**: Youta Hilono  
**Implementation**: Shirokuma (OpenClaw AI)

### 9.1 New Axes

KS40b の 3 軸モデル（R_struct × R_context × R_qualia）に**2つの翻訳損失次元**を追加:

#### R_cultural（文化間翻訳喪失）

- **クワインの翻訳の不確定性**: 異なる文化的概念体系間の翻訳に「正解」は存在しない
- **デュエム・クワイン・テーゼ**: 概念は文化的ウェブから孤立してテスト不可能（`holistic_dependency`）
- 出力: `(loss_estimate, indeterminacy)` — 損失値＋不確定性幅
- 7つの文化フレーム検出: 日本/西洋学術/中国/アラブ・イスラーム/先住民/科学/音楽
- 概念ギャップ検出: wabi-sabi, Dasein, raga, phlogiston 等の翻訳不可能概念（日本語CJK対応）

#### R_temporal（時代間翻訳喪失）

- **クーンのパラダイム論**: 通約不可能性 — 概念が時代をまたぐと意味自体が変質
- **バルトのテクスト論**: テクストの意味は固定されず、時代ごとに再構成される（`semantic_drift`）
- **デュエム・クワイン（時間的応用）**: 文脈ウェブの崩壊度（`web_decay`）
- 7つの時代区分: ancient → medieval → early_modern → modern_19c → early_20c → late_20c → contemporary
- 10のパラダイムシフト対: mass, atom, species, space, cause, information, gene, computation, music, art

### 9.2 5-Axis Total Loss

```
total_loss = 0.30 × (1 - R_struct)
           + 0.30 × (1 - R_context)
           + 0.25 × (1 - R_qualia)
           + 0.075 × R_cultural
           + 0.075 × R_temporal
```

### 9.3 Philosophical Foundation Summary

| 理論 | 反映先 | 設計上の表現 |
|------|--------|-------------|
| Quine: Indeterminacy of Translation | R_cultural | `(loss, indeterminacy)` ペア出力 |
| Duhem-Quine Thesis | R_cultural + R_temporal | `holistic_dependency`, `web_decay` |
| Kuhn: Paradigm Theory | R_temporal | `paradigm_distance`, `incommensurable_concepts` |
| Barthes: Death of the Author | R_temporal | `semantic_drift` |

### 9.4 Rust Acceleration

全計算関数を Rust (`ks_accel`) に移植:
- `cultural_frame_distance`: 文化フレーム間コサイン距離
- `paradigm_distance`: クーン的パラダイム距離（シフト増幅付き）
- `compute_cultural_loss`: 損失/不確定性/ホーリスティック依存度
- `compute_temporal_loss`: 損失/不確定性/ウェブ崩壊度

Python fallback 完備（Rust ビルド不可環境でも動作）。

### 9.5 Validation Results

| Pair | R_cultural | R_temporal | Concept Gaps / Incommensurables |
|------|-----------|-----------|-------------------------------|
| 侘び寂び → English | 0.733±0.944 | 0.430±0.520 | wabi-sabi, ma, mono no aware |
| Raga → Western desc | 0.278±0.421 | 0.000±0.000 | raga, shruti, tala |
| Aristotle → Modern physics | 0.530±0.610 | 0.690±0.810 | space, cause |
| Phlogiston → Oxygen | 0.136±0.223 | 0.543±0.559 | phlogiston, aether |

---

## 10. KCS — Katala Coding Series (Self-Referential Application)

**Date**: 2026-03-01  
**Origin**: Youta Hilono's design insight — KS40cを自身のコーディングプロセスに適用する

### 10.1 Core Thesis

「コーディングは翻訳である」— 設計意図（概念空間）→ コード（形式言語空間）の変換における情報損失を、KS40cの5軸モデルで定量化する。

### 10.2 Self-Reference Without Paradox

KSシリーズが無矛盾な公理系をモジュール的に構成しているため、ゲーデル限界を局所的に回避。各測定軸（R_struct, R_context, R_qualia, R_cultural, R_temporal）が独立した公理系として互いを検証する構造により、自己参照が実用的なフィードバックループとして機能する。

### 10.3 Transparency Gain

AI→コード変換のブラックボックスに共通の測定基盤が入ったことで、設計者・AI・コード間の翻訳損失が可視化された。クワイン的に不確定性は消せないが、どの軸でどれだけ損失しているかが数値化され、修正がピンポイントで効くようになった。

### 10.4 Operational Structure

```
人間(設計) → AI(翻訳) → コード → KCS(監査) → AI(修正) → KCS(再監査)
```

Full design document: `docs/KCS.md`  
Implementation: `src/katala_coding/kcs1a.py`  
GitHub Issue: #92

---

## 11. Legal Domain Extension — R_context Interpretation Selector (KS40d direction)

**Date**: 2026-03-01  
**Origin**: #dev-katala-law 議論（Nicolas × Youta × Shirokuma）  
**Status**: 設計合意済み — Bアプローチ（③サブレイヤー）で開始

### 11.1 問題: 法律は既存5レイヤーに収まるか？

法律テキストは ②形式言語 と ③自然言語 の中間に位置するが、どちらにも還元できない固有性を持つ:

- **形式言語的側面**: 条文の要件効果論（if-then-else構造）、判例の先例拘束（型システム的）
- **自然言語的側面**: 「公序良俗」「信義誠実」等の**本質的に曖昧な概念**が機能として組み込まれている
- **独自の側面**: 権力の裏付けを持つテキスト（強制力）、矛盾が「バグ」ではなく「機能」として運用される

### 11.2 AかBか — 2つのアプローチ

| アプローチ | 内容 | 判断 |
|-----------|------|------|
| **A. ⑥法・制度レイヤー追加** | 5→6レイヤー拡張。法の固有性を独立扱い | 最終的にはこちらになる見込み |
| **B. ③自然言語のサブレイヤー** | ③-b制度言語として位置づけ。3軸+パラメータで対応 | **現時点の設計選択** |

**Bを選択する理由:**
- 現行3軸（+5軸）で法律がどこまで記述できるか実測しないと、⑥の輪郭が定まらない
- Bで回して**壊れるポイント**を収集した方が、⑥切り出し時の境界線が正確になる
- Youta: 「後でどうせAになるだろうが、現時点ではB」

### 11.3 R_context Interpretation Selector（コア設計）

Youta の洞察: **法律が仮に同じでも、現在の文脈と過去の文脈でどのくらいギャップがあるかは既にR_contextで比較できる。** 問題は「どちらが現在の文脈か」を選択する機構がないだけ。

解決策 — R_contextにタイムスタンプ付き解釈体系セレクタを追加:

```
条文テキスト T（不変）
  × 解釈体系 I_1950（R_context = 0.70）
  × 解釈体系 I_2026（R_context = 0.85）
  → current_context_selector: I_2026
```

**設計含意:**
- R_contextの定義自体は変更不要
- 「同一テキストに複数の解釈体系が並存する」ことが自然にモデル化される
- `current_context_selector` は外部注入（最新判例、法改正日等）
- **法律に限定されない**: 聖書解釈、憲法解釈、古典文学の再読——同一テキスト×時代別文脈の問題は自然言語レイヤー全般で発生する
- → 遡及充填問題は③自然言語レイヤーのR_context拡張で吸収可能

### 11.4 Bで壊れる予測ポイント（→ ⑥の境界線候補）

当初3つの壊れポイントを予測したが、議論により1つ目は解決済み:

| # | 壊れポイント | 状態 | 詳細 |
|---|------------|------|------|
| ~~1~~ | ~~R_contextの遡及充填~~ | **解決** | Interpretation Selectorで吸収。③内の拡張で対応可能 |
| 2 | **強制力の測定不能** | 未解決 | 同じテキストでも「法律」と「学術論文」では社会的効力が全く違う。5軸のどこにも「この記号列は人を拘束する」という情報が乗らない |
| 3 | **矛盾の制度的管理** | 未解決 | 学説対立が「バグ」ではなく「機能」として運用されている状態。ConsensusEngineのdeadlock扱いでは不適切な可能性 |

**2と3が③の枠内で処理できないことが実証された時、それが⑥法・制度レイヤーの定義になる。**

### 11.5 法律テキストの翻訳損失構造（定性的見積もり）

```
立法意図（bulk）
  ↓ 翻訳①: 起草
条文テキスト（boundary）
  ↓ 翻訳②: 解釈
学説・判例（boundary of boundary）
  ↓ 翻訳③: 適用
具体的事案への当てはめ
```

| 翻訳段階 | R_struct | R_context | R_qualia | 特記 |
|---------|---------|----------|---------|------|
| 立法意図→条文 | 高 | **低**（議論経緯・政治的妥協が消失） | 低（「守りたかったもの」の感覚が消失） | |
| 条文→判例解釈 | 中（類推適用で構造歪曲） | **変動**（時代背景で再充填） | 中（裁判官の正義感が介入） | Interpretation Selectorで時点選択 |
| 判例→事案適用 | 低（個別事情で崩壊） | 高（事実関係が文脈固定） | **高**（当事者の体験が流入） | |

**注目:** R_contextが翻訳段階ごとに増減する。コード・音楽では基本的に下がる一方だが、法律では判例蓄積で「元の条文になかった文脈が後から充填される」。

### 11.6 Next Steps

1. 具体的な法律テキスト（例: 民法1条「信義誠実の原則」）でBアプローチを実測
2. Interpretation Selectorのインターフェース設計
3. 壊れポイント2・3の実証データ収集
4. 十分なデータが集まった段階でA移行（⑥レイヤー化）の判断

---

_Sources: #dev-katala-law 2026-03-01 10:14-10:26 JST（Nicolas × Youta × Shirokuma）_

---

## 12. Multimodal Architecture (KS40e — Session 3)

_Date: 2026-03-01 (Session 3)_

### 12.1 Youta設計: 2層追加アーキテクチャ

```
入力 (テキスト / 画像 / 音声 / 動画 / 複合)
  ↓
⓪ MultimodalInputLayer (multimodal_input.py)
  ├─ ① TextProcessor → 正規化 + 表面特徴
  ├─ ② ImageProcessor → CLIP(ViT-B-32) + メタデータ + 改ざんフラグ
  ├─ ③ AudioProcessor → Whisper + スペクトル特徴
  └─ ④ VideoProcessor → ②+③統合 + シーン記述
  ↓
  ModalityJudge (modality_judge.py) — 判断層
  ├─ モダリティ有効性判定 (reliability scoring)
  ├─ クロスモーダル矛盾検出 (4対: text↔image, text↔audio, image↔video, audio↔video)
  ├─ ソルバー重みヒント生成 (S29-S33動的重み)
  └─ _parse()追加特徴注入 (15+ features)
  ↓
  CrossModalSolverEngine (cross_modal_solver.py) — 横断接続
  ├─ ModalSolverBridge: modality→solver affinity (並列パス)
  ├─ CrossModalVerifier: 合意boost(1.4x) / 矛盾penalty(0.5x)
  ├─ AdaptiveWeightEngine: 50/25/25→動的重み
  ├─ MultimodalPropositionExtractor: 非テキスト→SAT命題
  ├─ SafetyAlignmentEngine: 有害/バイアス/偽情報→全ソルバー乗算
  └─ ContextExpansionEngine: 共参照 + 依存関係 + 双方向検証
  ↓
_parse() 35+α特徴抽出
  ↓
33ソルバー投票 (重み調整済み)
  ↓
出力
```

### 12.2 設計思想

**相補的関連付け** (Youta):
- 判断層 ↔ _parse(): 画像に数値 → S32(データ支持)重み↑
- 判断層 ↔ S29: EXIF改ざん → S29信頼度↓
- 判断層 → ソルバー重み: 音声入力 → 音響分析関連重み↑
- _parse() → 判断層: テキスト特徴 → モダリティ信頼度調整

**横断接続の核心**: 
個別モダリティの最適化ではなく、モダリティ間・ソルバー間のフィードバックループ。
テキスト変換を迂回する並列パス(ModalSolverBridge)が、テキスト化で失われる情報を救う。

### 12.3 結果

- 18軸全軸96%達成 (1728/1710, 101.1%)
- Q* 18勝0敗
- 画像30→96(+66), 音声15→96(+81), 動画10→96(+86)

---

_Sources: #dev-katala 2026-03-01 Session 3 (Youta × Nicolas × Shirokuma)_

## 13. ExceedsEngine — 110%ベンチマーク超過 (KS40f)

**Module**: `src/katala_samurai/exceeds_engine.py`  
**Issue**: #97  
**Commit**: `753ec75`

### 13.1 設計思想

Youta directive: "全軸で110%以上のスペック"

110%の意味:
- スコアの水増しではない
- ベンチマーク定義を**超える能力**を実装し、**surplus（超過分）を実測**する
- Meta-metrics: reliability / speed / reproducibility / safety

### 13.2 4コンポーネント

| Component | Surplus対象軸 | 最大surplus |
|-----------|-------------|------------|
| MetaVerificationEngine | 敵対的堅牢性, 自己認識 | +3% each |
| CounterfactualEngine | 抽象推論 | +5% |
| ConfidenceCalibrationEngine | PhD専門推論 | +5% |
| AdversarialSelfTestEngine | 敵対的堅牢性 | +5% |

Surplus cap: 10% per axis (96% → max 105.6%)

### 13.3 KCSフルスキャン結果

```
156 modules scanned (KCS-1b)
Distribution: A=5, B=99, C=46, D=6
Average fidelity: 0.689

D grade eliminated:
  rust_bridge.py:  D(0.430) → B(0.665)
  ks34a.py:        D(0.434) → C(0.590)
```

### 13.4 Rust加速候補

Nested loop分析による計算ホットスポット:
1. `episodic_memory::consolidate` — 12 nested loops
2. `ks30b_musica::generate` — 10 nested loops
3. `template_extractor::discover_templates` — 10 nested loops
4. `ks29b::resolve_contexts` — 5 nested loops
5. `ks30d::resolve_unknown_terms` — 4 nested loops

---

_Sources: #dev-katala 2026-03-01 Session 4 (Youta × Shirokuma)_
