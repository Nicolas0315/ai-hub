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
