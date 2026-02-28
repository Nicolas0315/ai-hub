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
